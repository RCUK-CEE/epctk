import math
import numpy
from .pcdf import VentilationTypes
# from . import sap_tables
from .sap_tables import DAYS_PER_MONTH, MONTHLY_HOT_WATER_FACTORS, MONTHLY_HOT_WATER_TEMPERATURE_RISE, GlazingTypes, \
    HeatingSystem, ELECTRICITY_SOLD, ELECTRICITY_OFFSET, TABLE_H5, HeatingTypes


class HeatLossElementTypes:
    EXTERNAL_WALL = 1
    PARTY_WALL = 2
    EXTERNAL_FLOOR = 3
    EXTERNAL_ROOF = 4
    OPAQUE_DOOR = 5
    GLAZING = 6


class HeatLossElement:
    def __init__(self, area, Uvalue, is_external, element_type, name=""):
        self.area = area
        self.Uvalue = Uvalue
        self.is_external = is_external
        self.name = name
        self.element_type = element_type


class ThermalMassElement:
    def __init__(self, area, kvalue, name=""):
        self.area = area
        self.kvalue = kvalue
        self.name = name


def light_transmittance_from_glazing_type(glazing_type):
    if glazing_type == GlazingTypes.SINGLE:
        return 0.9
    elif glazing_type == GlazingTypes.DOUBLE:
        return 0.8
    elif glazing_type == GlazingTypes.TRIPLE:
        return 0.7
    elif glazing_type == GlazingTypes.SECONDARY:
        return .8
    else:
        raise RuntimeError("unknown glazing type %s" % glazing_type)


class OpeningType:
    def __init__(self, glazing_type, gvalue, frame_factor, Uvalue, roof_window, bfrc_data=False):
        self.gvalue = gvalue
        self.light_transmittance = light_transmittance_from_glazing_type(
            glazing_type)
        self.frame_factor = frame_factor
        self.Uvalue = Uvalue
        self.roof_window = roof_window
        self.bfrc_data = bfrc_data
        self.glazing_type = glazing_type


class Opening:
    def __init__(self, area, orientation_degrees, opening_type, name=""):
        self.area = area
        self.orientation_degrees = orientation_degrees
        self.opening_type = opening_type
        self.name = name


def monthly_to_annual(var):
    return sum(var * DAYS_PER_MONTH) / 365.


def convert_old_style_openings(dwelling):
    # This gives behaviour consistent with the old way of doing
    # things, BUT it means that the door is treated as glazed for the
    # solar gain calc!
    opening_type = OpeningType(gvalue=dwelling.gvalue,
                               frame_factor=dwelling.frame_factor,
                               light_transmittance=dwelling.light_transmittance,
                               roof_window=False)
    dwelling.openings = [
        Opening(dwelling.Aglazing_front, dwelling.orientation,
                opening_type),
        Opening(dwelling.Aglazing_back, dwelling.orientation + 180,
                opening_type),
        Opening(dwelling.Aglazing_left, dwelling.orientation - 90,
                opening_type),
        Opening(dwelling.Aglazing_right, dwelling.orientation + 90,
                opening_type),
    ]


def convert_old_style_heat_loss(dwelling):
    # Again, check treatment of glazing vs external door
    Aglazing_actual = max(0., dwelling.Aglazing - dwelling.Aextdoors)
    Aextdoor_actual = dwelling.Aglazing - Aglazing_actual
    assert Aglazing_actual >= 0
    assert Aextdoor_actual >= 0

    dwelling.heat_loss_elements = [
        HeatLossElement(Aglazing_actual, dwelling.Uglazing,
                        HeatLossElementTypes.GLAZING, True),
        HeatLossElement(Aextdoor_actual, dwelling.Uextdoor,
                        HeatLossElementTypes.OPAQUE_DOOR, True),
        HeatLossElement(dwelling.Aroof, dwelling.Uroof,
                        HeatLossElementTypes.EXTERNAL_ROOF, True),
        HeatLossElement(dwelling.Aextwall, dwelling.Uextwall,
                        HeatLossElementTypes.EXTERNAL_WALL, True),
        HeatLossElement(dwelling.Agndfloor, dwelling.Ugndfloor,
                        HeatLossElementTypes.EXTERNAL_FLOOR, True),
        HeatLossElement(dwelling.Apartywall, dwelling.Uparty_wall,
                        HeatLossElementTypes.PARTY_WALL, False),
        HeatLossElement(dwelling.Abasementfloor, dwelling.Ubasementfloor,
                        HeatLossElementTypes.EXTERNAL_FLOOR, True),
        HeatLossElement(dwelling.Abasementwall, dwelling.Ubasementwall,
                        HeatLossElementTypes.EXTERNAL_WALL, True),
    ]
    if dwelling.get('Aexposedfloor'):
        dwelling.heat_loss_elements.append(
            HeatLossElement(dwelling.Aexposedfloor, dwelling.Uexposedfloor, HeatLossElementTypes.EXTERNAL_FLOOR, True))

    if dwelling.get('Aroominroof'):
        dwelling.heat_loss_elements.append(
            HeatLossElement(dwelling.Aroominroof, dwelling.Uroominroof, HeatLossElementTypes.EXTERNAL_ROOF, True))


def convert_old_style_geometry(dwelling):
    if not dwelling.get('openings'):
        convert_old_style_openings(dwelling)
    if not dwelling.get('heat_loss_elements'):
        convert_old_style_heat_loss(dwelling)


def geometry(dwelling):
    if not dwelling.get('Aglazing'):
        dwelling.Aglazing = dwelling.GFA * dwelling.glazing_ratio
        dwelling.Aglazing_front = dwelling.glazing_asymmetry * \
                                  dwelling.Aglazing
        dwelling.Aglazing_back = (
                                     1. - dwelling.glazing_asymmetry) * dwelling.Aglazing
        dwelling.Aglazing_left = 0
        dwelling.Aglazing_right = 0
    elif not dwelling.get('Aglazing_front'):
        dwelling.Aglazing_front = dwelling.Aglazing / 2
        dwelling.Aglazing_back = dwelling.Aglazing / 2
        dwelling.Aglazing_left = 0
        dwelling.Aglazing_right = 0

    if dwelling.get('hlp'):
        return

    if dwelling.get('aspect_ratio'):
        # This is for converting for the parametric SAP style
        # dimensions to the calculation dimensions
        width = math.sqrt(dwelling.GFA / dwelling.Nstoreys / dwelling.aspect_ratio)

        depth = math.sqrt(dwelling.GFA / dwelling.Nstoreys * dwelling.aspect_ratio)

        dwelling.volume = width * depth * (dwelling.room_height * dwelling.Nstoreys +
                                           dwelling.internal_floor_depth * (dwelling.Nstoreys - 1))

        dwelling.Aextwall = 2 * (dwelling.room_height * dwelling.Nstoreys + dwelling.internal_floor_depth * (
            dwelling.Nstoreys - 1)) * (width + depth * (1 - dwelling.terrace_level)) - dwelling.Aglazing

        dwelling.Apartywall = 2 * \
                              (dwelling.room_height * dwelling.Nstoreys + dwelling.internal_floor_depth *
                               (dwelling.Nstoreys - 1)) * (depth * dwelling.terrace_level)

        if dwelling.type == "House":
            dwelling.Aroof = width * depth
            dwelling.Agndfloor = width * depth
        elif dwelling.type == "MidFlat":
            dwelling.Aroof = 0
            dwelling.Agndfloor = 0
        else:
            raise RuntimeError('Unknown dwelling type: %s' % (dwelling.type,))
    else:
        if not dwelling.get('volume'):
            dwelling.volume = dwelling.GFA * dwelling.storey_height

        if not dwelling.get('Aextwall'):
            if dwelling.get('wall_ratio'):
                dwelling.Aextwall = dwelling.GFA * dwelling.wall_ratio
            else:
                dwelling_height = dwelling.storey_height * dwelling.Nstoreys
                Atotalwall = dwelling_height * dwelling.average_perimeter
                if dwelling.get('Apartywall'):
                    dwelling.Aextwall = Atotalwall - dwelling.Apartywall
                elif dwelling.get('party_wall_fraction'):
                    dwelling.Aextwall = Atotalwall * (
                        1 - dwelling.party_wall_fraction)
                else:
                    dwelling.Aextwall = Atotalwall - \
                                        dwelling.party_wall_ratio * dwelling.GFA

        if not dwelling.get('Apartywall'):
            if dwelling.get('party_wall_ratio'):
                dwelling.Apartywall = dwelling.GFA * dwelling.party_wall_ratio
            else:
                dwelling.Apartywall = dwelling.Aextwall * \
                                      dwelling.party_wall_fraction / \
                                      (1 - dwelling.party_wall_fraction)

        if not dwelling.get('Aroof'):
            dwelling.Aroof = dwelling.GFA / dwelling.Nstoreys
            dwelling.Agndfloor = dwelling.GFA / dwelling.Nstoreys


def ventilation(dwelling):
    if dwelling.get('hlp'):
        return

    if not dwelling.get('Nfansandpassivevents'):
        dwelling.Nfansandpassivevents = dwelling.Nintermittentfans + \
                                        dwelling.Npassivestacks

    inf_chimneys_ach = (dwelling.Nchimneys * 40 + dwelling.Nflues * 20 +
                        dwelling.Nfansandpassivevents * 10 + dwelling.Nfluelessgasfires * 40) / dwelling.volume
    dwelling.inf_chimneys_ach = inf_chimneys_ach

    if dwelling.get('pressurisation_test_result'):
        base_infiltration_rate = dwelling.pressurisation_test_result / \
                                 20. + inf_chimneys_ach
    elif dwelling.get('pressurisation_test_result_average'):
        base_infiltration_rate = (
                                     dwelling.pressurisation_test_result_average + 2) / 20. + inf_chimneys_ach
    else:
        additional_infiltration = (dwelling.Nstoreys - 1) * 0.1
        draught_infiltration = 0.05 if not dwelling.has_draught_lobby else 0
        dwelling.window_infiltration = 0.25 - 0.2 * dwelling.draught_stripping

        base_infiltration_rate = (additional_infiltration
                                  + dwelling.structural_infiltration
                                  + dwelling.floor_infiltration
                                  + draught_infiltration
                                  + dwelling.window_infiltration
                                  + inf_chimneys_ach)
    dwelling.base_infiltration_rate = base_infiltration_rate

    shelter_factor = 1 - 0.075 * dwelling.Nshelteredsides
    adjusted_infiltration_rate = shelter_factor * base_infiltration_rate

    effective_inf_rate = adjusted_infiltration_rate * dwelling.wind_speed / 4.

    if dwelling.ventilation_type == VentilationTypes.NATURAL:
        dwelling.infiltration_ach = numpy.where(
            effective_inf_rate < 1.,
            0.5 + (effective_inf_rate ** 2) * 0.5,
            effective_inf_rate)
    elif dwelling.ventilation_type == VentilationTypes.MV:
        system_ach = 0.5
        dwelling.infiltration_ach = effective_inf_rate + system_ach
    elif dwelling.ventilation_type in [VentilationTypes.MEV_CENTRALISED,
                                       VentilationTypes.MEV_DECENTRALISED,
                                       VentilationTypes.PIV_FROM_OUTSIDE]:
        system_ach = 0.5
        dwelling.infiltration_ach = numpy.where(
            effective_inf_rate < 0.5 * system_ach,
            system_ach,
            effective_inf_rate + 0.5 * system_ach)
    elif dwelling.ventilation_type == VentilationTypes.MVHR:
        system_ach = 0.5
        dwelling.infiltration_ach = (
            effective_inf_rate + system_ach * (1 - dwelling.mvhr_effy / 100)
        )

    if (dwelling.get('appendix_q_systems') and
                dwelling.appendix_q_systems is not None):
        for s in dwelling.appendix_q_systems:
            if 'ach_rates' in s:
                # !!! Should really check that we don't get two sets
                # !!! of ach rates
                dwelling.infiltration_ach = numpy.array(s['ach_rates'])

    dwelling.infiltration_ach_annual = monthly_to_annual(
        dwelling.infiltration_ach)


def heat_loss(dwelling):
    if dwelling.get('hlp'):
        dwelling.h = dwelling.hlp * dwelling.GFA
        return

    UA = sum(e.Uvalue * e.area for e in dwelling.heat_loss_elements)
    Abridging = sum(
        e.area for e in dwelling.heat_loss_elements if e.is_external)
    if dwelling.get("Uthermalbridges"):
        h_bridging = dwelling.Uthermalbridges * Abridging
    else:
        h_bridging = sum(x['length'] * x['y'] for x in dwelling.y_values)

    h_vent = 0.33 * dwelling.infiltration_ach * dwelling.volume
    dwelling.h = UA + h_bridging + h_vent
    dwelling.hlp = dwelling.h / dwelling.GFA

    dwelling.h_fabric = UA
    dwelling.h_bridging = h_bridging
    dwelling.h_vent = h_vent

    dwelling.h_vent_annual = monthly_to_annual(h_vent)


def solar_system_output(dwelling, hw_energy_content, daily_hot_water_use):
    performance_ratio = dwelling.collector_heat_loss_coeff / \
                        dwelling.collector_zero_loss_effy
    annual_radiation = dwelling.collector_Igh
    overshading_factor = dwelling.collector_overshading_factor
    available_energy = dwelling.solar_collector_aperture * \
                       dwelling.collector_zero_loss_effy * \
                       annual_radiation * overshading_factor
    solar_to_load = available_energy / sum(hw_energy_content)
    utilisation = 1 - math.exp(-1 / solar_to_load)

    if dwelling.water_sys.system_type in [
        HeatingTypes.regular_boiler,
        HeatingTypes.room_heater,  # must be back boiler
    ] and not dwelling.has_cylinderstat:
        utilisation *= .9

    performance_factor = 0.97 - 0.0367 * performance_ratio + 0.0006 * \
                                                             performance_ratio ** 2 if performance_ratio < 20 else 0.693 - \
                                                                                                                   0.0108 * performance_ratio

    effective_solar_volume = dwelling.solar_effective_storage_volume

    volume_ratio = effective_solar_volume / daily_hot_water_use
    storage_volume_factor = numpy.minimum(
        1., 1 + 0.2 * numpy.log(volume_ratio))
    Qsolar_annual = available_energy * utilisation * \
                    performance_factor * storage_volume_factor

    Qsolar = -Qsolar_annual * \
             dwelling.monthly_solar_hw_factors * DAYS_PER_MONTH / 365
    return Qsolar


def wwhr_savings(dwelling):
    savings = 0
    Nshower_with_bath = 1
    Nshower_without_bath = 0
    Nshower_and_bath = dwelling.wwhr_total_rooms_with_shower_or_bath

    S_sum = 0
    for sys in dwelling.wwhr_systems:
        effy = sys['pcdf_sys']['effy_mixer_shower'] / 100
        util = sys['pcdf_sys']['utilisation_mixer_shower']
        S_sum += (sys['Nshowers_with_bath'] * .635 * effy *
                  util + sys['Nshowers_without_bath'] * effy * util)

    Seff = S_sum / Nshower_and_bath
    Tcoldm = numpy.array(
        [11.1, 10.8, 11.8, 14.7, 16.1, 18.2, 21.3, 19.2, 18.8, 16.3, 13.3, 11.8])
    Awm = .33 * 25 * MONTHLY_HOT_WATER_TEMPERATURE_RISE / (41 - Tcoldm) + 26.1
    Bwm = .33 * 36 * MONTHLY_HOT_WATER_TEMPERATURE_RISE / (41 - Tcoldm)

    savings = (dwelling.Nocc * Awm + Bwm) * Seff * (35 - Tcoldm) * \
              4.18 * DAYS_PER_MONTH * MONTHLY_HOT_WATER_FACTORS / 3600.

    return savings


def hot_water_use(dwelling):
    dwelling.hw_use_daily = dwelling.daily_hot_water_use * \
                            MONTHLY_HOT_WATER_FACTORS
    dwelling.hw_energy_content = (4.19 / 3600.) * dwelling.hw_use_daily * \
                                 DAYS_PER_MONTH * \
                                 MONTHLY_HOT_WATER_TEMPERATURE_RISE

    if dwelling.get('instantaneous_pou_water_heating') and dwelling.instantaneous_pou_water_heating:
        dwelling.distribution_loss = 0
        dwelling.storage_loss = 0
    else:
        dwelling.distribution_loss = 0.15 * dwelling.hw_energy_content

        if dwelling.get('measured_cylinder_loss') and dwelling.measured_cylinder_loss != None:
            dwelling.storage_loss = dwelling.measured_cylinder_loss * \
                                    dwelling.temperature_factor * DAYS_PER_MONTH
        elif dwelling.get('hw_cylinder_volume'):
            cylinder_loss = dwelling.hw_cylinder_volume * dwelling.storage_loss_factor * \
                            dwelling.volume_factor * dwelling.temperature_factor
            dwelling.storage_loss = cylinder_loss * DAYS_PER_MONTH
        else:
            dwelling.storage_loss = 0

    if dwelling.get("solar_storage_combined_cylinder") and dwelling.solar_storage_combined_cylinder:
        dwelling.storage_loss *= (
                                     dwelling.hw_cylinder_volume - dwelling.solar_dedicated_storage_volume) / dwelling.hw_cylinder_volume

    if dwelling.get('primary_loss_override'):
        primary_circuit_loss_annual = dwelling.primary_loss_override
    else:
        primary_circuit_loss_annual = dwelling.primary_circuit_loss_annual

    dwelling.primary_circuit_loss = (
                                        primary_circuit_loss_annual / 365.) * DAYS_PER_MONTH
    if dwelling.get('combi_loss'):
        dwelling.combi_loss_monthly = dwelling.combi_loss(
            dwelling.hw_use_daily) * DAYS_PER_MONTH / 365
    else:
        dwelling.combi_loss_monthly = 0

    if dwelling.get('use_immersion_heater_summer'):
        if dwelling.use_immersion_heater_summer:
            for i in range(5, 9):
                dwelling.primary_circuit_loss[i] = 0

    if dwelling.get('wwhr_systems') and dwelling.wwhr_systems != None:
        dwelling.savings_from_wwhrs = wwhr_savings(dwelling)
    else:
        dwelling.savings_from_wwhrs = 0

    if dwelling.get('solar_collector_aperture') and dwelling.solar_collector_aperture != None:
        dwelling.input_from_solar = solar_system_output(
            dwelling, dwelling.hw_energy_content - dwelling.savings_from_wwhrs, dwelling.daily_hot_water_use)
        if primary_circuit_loss_annual > 0 and dwelling.hw_cylinder_volume > 0 and dwelling.has_cylinderstat:
            dwelling.primary_circuit_loss *= TABLE_H5
    else:
        dwelling.input_from_solar = 0

    if (dwelling.get('fghrs') and
                dwelling.fghrs != None and
            dwelling.fghrs['has_pv_module']):
        dwelling.fghrs_input_from_solar = fghrs_solar_input(dwelling,
                                                            dwelling.fghrs,
                                                            dwelling.hw_energy_content,
                                                            dwelling.daily_hot_water_use)
    else:
        dwelling.fghrs_input_from_solar = 0

    dwelling.total_water_heating = 0.85 * dwelling.hw_energy_content + dwelling.distribution_loss + \
                                   dwelling.storage_loss + dwelling.primary_circuit_loss + \
                                   dwelling.combi_loss_monthly

    # Assumes the cylinder is in the heated space if input is missing
    if dwelling.get('cylinder_in_heated_space') and not dwelling.cylinder_in_heated_space:
        dwelling.heat_gains_from_hw = 0.25 * (0.85 * dwelling.hw_energy_content + dwelling.combi_loss_monthly) + 0.8 * (
            dwelling.distribution_loss + dwelling.primary_circuit_loss)
    else:
        dwelling.heat_gains_from_hw = 0.25 * (0.85 * dwelling.hw_energy_content + dwelling.combi_loss_monthly) + 0.8 * (
            dwelling.distribution_loss + dwelling.storage_loss + dwelling.primary_circuit_loss)
    dwelling.heat_gains_from_hw = numpy.maximum(0, dwelling.heat_gains_from_hw)


def fghr_savings(dwelling):
    if dwelling.fghrs['heat_store'] == 1:
        # !!! untested
        assert False
        Kfl = dwelling.fghrs['direct_useful_heat_recovered']
        return Kfl * Kn * dwelling.total_water_heating

    equation_space_heats = [e['space_heating_requirement']
                            for e in dwelling.fghrs['equations']]

    # !!! Should only use heat provided by this system
    if dwelling.water_sys is dwelling.main_sys_1:
        space_heat_frac = (dwelling.fraction_of_heat_from_main *
                           dwelling.main_heating_fraction)
    elif dwelling.water_sys is dwelling.main_sys_2:
        space_heat_frac = (dwelling.fraction_of_heat_from_main *
                           dwelling.main_heating_2_fraction)
    else:
        # !!! Not allowed to have fghrs on secondary system?
        # !!! Are you even allowed fghrs on hw only systems?
        space_heat_frac = 0

    Qspm = dwelling.Q_required * space_heat_frac

    closest_below = [max(x for x in equation_space_heats
                         if x <= Qspm[month])
                     if Qspm[month] >= min(equation_space_heats)
                     else min(equation_space_heats)
                     for month in range(12)]
    closest_above = [min(x for x in equation_space_heats
                         if x >= Qspm[month])
                     if Qspm[month] <= max(equation_space_heats)
                     else max(equation_space_heats)
                     for month in range(12)]

    closest_below_eqns = [[e for e in dwelling.fghrs['equations']
                           if e['space_heating_requirement'] == Q_req][0]
                          for Q_req in closest_below]
    closest_above_eqns = [[e for e in dwelling.fghrs['equations']
                           if e['space_heating_requirement'] == Q_req][0]
                          for Q_req in closest_above]

    # !!! For some reason solar input from FGHRS doesn't reduce Qhwm
    Qhwm = (dwelling.hw_energy_content +
            dwelling.input_from_solar -
            dwelling.savings_from_wwhrs)

    def calc_S0(equations):
        a = numpy.array([e['a'] for e in equations])
        b = numpy.array([e['b'] for e in equations])
        c = numpy.array([e['c'] for e in equations])

        res = [0, ] * 12
        for month in range(12):
            Q = min(309, max(80, Qhwm[month]))
            res[month] = (a[month] * math.log(Q) +
                          b[month] * Q +
                          c[month]) * min(1, Qhwm[month] / Q)

        return res

    S0_below = calc_S0(closest_below_eqns)
    S0_above = calc_S0(closest_above_eqns)
    S0 = [0, ] * 12
    for month in range(12):
        if closest_above[month] != closest_below[month]:
            S0[month] = S0_below[month] + (S0_above[month] - S0_below[month]) * (
                Qspm[month] - closest_below[month]) / (closest_above[month] - closest_below[month])
        else:
            S0[month] = S0_below[month]

    # !!! Should exit here for intant combi without keep hot and no
    # !!! ext store - S0 is the result

    # !!! Needs factor of 1.3 for CPSU or primary storage combi
    Vk = (dwelling.hw_cylinder_volume if dwelling.get('hw_cylinder_volume')
          else dwelling.fghrs['heat_store_total_volume'])

    if Vk >= 144:
        Kn = 0
    elif Vk >= 75:
        Kn = .48 - Vk / 300.
    elif Vk >= 15:
        Kn = 1.1925 - .77 * Vk / 60.
    else:
        Kn = 1

    Kf2 = dwelling.fghrs['direct_total_heat_recovered']
    Sm = S0 + 0.5 * Kf2 * (dwelling.storage_loss +
                           dwelling.primary_circuit_loss +
                           dwelling.combi_loss_monthly -
                           (1 - Kn) * Qhwm)

    # !!! Need to use this for combi with keep hot
    # Sm=S0+0.5*Kf2*(dwelling.combi_loss_monthly-dwelling.water_sys.keep_hot_elec_consumption)

    savings = numpy.where(Qhwm > 0,
                          Sm,
                          0)
    return savings


def fghrs_solar_input(dwelling, fghrs, hw_energy_content, daily_hot_water_use):
    available_energy = (.84 *
                        fghrs['PV_kWp'] *
                        fghrs['Igh'] *
                        fghrs['overshading_factor'] *
                        (1 - fghrs['cable_loss']))

    solar_to_load = available_energy / sum(hw_energy_content)
    utilisation = 1 - math.exp(-1 / solar_to_load) if solar_to_load > 0 else 0

    store_volume = fghrs['heat_store_total_volume']
    effective_solar_volume = .76 * store_volume

    volume_ratio = effective_solar_volume / daily_hot_water_use
    storage_volume_factor = numpy.minimum(
        1., 1 + 0.2 * numpy.log(volume_ratio))
    Qsolar_annual = available_energy * utilisation * storage_volume_factor
    Qsolar = -Qsolar_annual * \
             dwelling.fghrs['monthly_solar_hw_factors'] * DAYS_PER_MONTH / 365

    return Qsolar


def water_heater_output(dwelling):
    if dwelling.get('fghrs') and dwelling.fghrs != None:
        dwelling.savings_from_fghrs = fghr_savings(dwelling)
    else:
        dwelling.savings_from_fghrs = 0

    dwelling.output_from_water_heater = numpy.maximum(0,
                                                      dwelling.total_water_heating
                                                      +
                                                      dwelling.input_from_solar
                                                      +
                                                      dwelling.fghrs_input_from_solar
                                                      -
                                                      dwelling.savings_from_wwhrs
                                                      - dwelling.savings_from_fghrs)


def GL_sum(openings):
    return sum(0.9 * o.area * o.opening_type.frame_factor * o.opening_type.light_transmittance for o in openings)


def lighting_consumption(dwelling):
    mean_light_energy = 59.73 * (dwelling.GFA * dwelling.Nocc) ** 0.4714

    if not dwelling.get('low_energy_bulb_ratio'):
        dwelling.low_energy_bulb_ratio = int(
            100 * float(dwelling.lighting_outlets_low_energy) / dwelling.lighting_outlets_total + .5) / 100.

    C1 = 1 - 0.5 * dwelling.low_energy_bulb_ratio
    GLwin = GL_sum(o for o in dwelling.openings if not o.opening_type.roof_window and not o.opening_type.bfrc_data) * \
            dwelling.light_access_factor / dwelling.GFA
    GLroof = GL_sum(
        o for o in dwelling.openings if o.opening_type.roof_window and not o.opening_type.bfrc_data) / dwelling.GFA

    # Use frame factor of 0.7 for bfrc rated windows
    GLwin_bfrc = GL_sum(o for o in dwelling.openings if not o.opening_type.roof_window and o.opening_type.bfrc_data) * \
                 .7 * .9 * dwelling.light_access_factor / dwelling.GFA
    GLroof_bfrc = GL_sum(
        o for o in dwelling.openings if
        o.opening_type.roof_window and o.opening_type.bfrc_data) * .7 * .9 / dwelling.GFA

    GL = GLwin + GLroof + GLwin_bfrc + GLroof_bfrc
    C2 = 52.2 * GL ** 2 - 9.94 * GL + 1.433 if GL <= 0.095 else 0.96
    EL = mean_light_energy * C1 * C2
    light_consumption = EL * \
                        (1 + 0.5 * numpy.cos((2. * math.pi / 12.) * ((numpy.arange(12) + 1) - 0.2))) * \
                        DAYS_PER_MONTH / 365
    dwelling.annual_light_consumption = sum(light_consumption)
    dwelling.full_light_gain = light_consumption * \
                               (0.85 * 1000 / 24.) / DAYS_PER_MONTH

    dwelling.lighting_C1 = C1
    dwelling.lighting_GL = GL
    dwelling.lighting_C2 = C2


def internal_heat_gain(dwelling):
    dwelling.losses_gain = -40 * dwelling.Nocc
    dwelling.water_heating_gains = (
                                       1000. / 24.) * dwelling.heat_gains_from_hw / DAYS_PER_MONTH

    lighting_consumption(dwelling)

    mean_appliance_energy = 207.8 * (dwelling.GFA * dwelling.Nocc) ** 0.4714
    appliance_consumption_per_day = (mean_appliance_energy / 365.) * (
        1 + 0.157 * numpy.cos((2. * math.pi / 12.) * (numpy.arange(12) - .78)))
    dwelling.appliance_consumption = appliance_consumption_per_day * \
                                     DAYS_PER_MONTH

    if dwelling.reduced_gains:
        dwelling.met_gain = 50 * dwelling.Nocc
        dwelling.cooking_gain = 23 + 5 * dwelling.Nocc
        dwelling.appliance_gain = (
                                      0.67 * 1000. / 24) * appliance_consumption_per_day
        dwelling.light_gain = 0.4 * dwelling.full_light_gain
    else:
        dwelling.met_gain = 60 * dwelling.Nocc
        dwelling.cooking_gain = 35 + 7 * dwelling.Nocc
        dwelling.appliance_gain = (1000. / 24) * appliance_consumption_per_day
        dwelling.light_gain = dwelling.full_light_gain

    dwelling.total_internal_gains = (dwelling.met_gain
                                     + dwelling.water_heating_gains
                                     + dwelling.light_gain
                                     + dwelling.appliance_gain
                                     + dwelling.cooking_gain
                                     + dwelling.pump_gain
                                     + dwelling.losses_gain)

    if dwelling.reduced_gains:
        summer_met_gain = 60 * dwelling.Nocc
        summer_cooking_gain = 35 + 7 * dwelling.Nocc
        summer_appliance_gain = (1000. / 24) * appliance_consumption_per_day
        summer_light_gain = dwelling.full_light_gain
        dwelling.total_internal_gains_summer = (summer_met_gain
                                                + dwelling.water_heating_gains
                                                + summer_light_gain
                                                + summer_appliance_gain
                                                + summer_cooking_gain
                                                + dwelling.pump_gain
                                                + dwelling.losses_gain
                                                - dwelling.heating_system_pump_gain)
    else:
        dwelling.total_internal_gains_summer = dwelling.total_internal_gains - \
                                               dwelling.heating_system_pump_gain


HEATING_LATITUDE = 53.4


class SolarConstants:
    def __init__(self, latitude):
        declination = numpy.array(
            [-20.7, -12.8, -1.8, 9.8, 18.8, 23.1, 21.2, 13.7, 2.9, -8.7, -18.4, -23])

        delta_lat = latitude - declination
        delta_lat_sq = delta_lat ** 2
        self.A = .702 - .0119 * (delta_lat) + 0.000204 * delta_lat_sq
        self.B = -.107 + 0.0081 * (delta_lat) - 0.000218 * delta_lat_sq
        self.C = .117 - 0.0098 * (delta_lat) + 0.000143 * delta_lat_sq


solar_constants_heating = SolarConstants(HEATING_LATITUDE)


def incident_solar(Igh, details, orientation, is_roof_window):
    if not is_roof_window:
        return incident_solar_vertical(Igh, details, orientation)
    elif orientation > 330 * math.pi / 180 or orientation < 30 * math.pi / 180:
        return incident_solar_vertical(Igh, details, 0)
    else:
        return Igh


def incident_solar_vertical(Igh, details, orientation):
    return Igh * (details.A + details.B * numpy.cos(orientation) + details.C * numpy.cos(2 * orientation))


def solar_access_factor_winter(dwelling, opening):
    if opening.opening_type.roof_window:
        return 1
    else:
        return dwelling.solar_access_factor_winter


def solar_access_factor_summer(dwelling, opening):
    if opening.opening_type.roof_window:
        return 1
    else:
        return dwelling.solar_access_factor_summer


def solar(dwelling):
    dwelling.solar_gain_winter = sum(
        0.9 * solar_access_factor_winter(dwelling, o) * o.opening_type.gvalue * o.opening_type.frame_factor * o.area *
        incident_solar(dwelling.Igh_heating,
                       solar_constants_heating,
                       o.orientation_degrees * math.pi / 180,
                       o.opening_type.roof_window)
        for o in dwelling.openings)

    """for o in dwelling.openings:
        flux=incident_solar(dwelling.Igh_heating,
                       solar_constants_heating,
                       o.orientation_degrees*math.pi/180,
                       o.opening_type.roof_window) 

        print o.area,o.orientation_degrees,flux,o.type.gvalue,o.type.frame_factor,solar_access_factor_winter(dwelling,o)"""

    dwelling.winter_heat_gains = dwelling.total_internal_gains + \
                                 dwelling.solar_gain_winter

    # !!! Really only want to do this if we have cooling
    dwelling.solar_gain_summer = sum(
        0.9 * solar_access_factor_summer(dwelling, o) * o.opening_type.gvalue * o.opening_type.frame_factor * o.area *
        incident_solar(dwelling.Igh_summer,
                       SolarConstants(dwelling.latitude),
                       o.orientation_degrees * math.pi / 180,
                       o.opening_type.roof_window)
        for o in dwelling.openings)

    dwelling.summer_heat_gains = dwelling.total_internal_gains_summer + \
                                 dwelling.solar_gain_summer


def heating_requirement(dwelling):
    if not dwelling.get('thermal_mass_parameter'):
        ka = 0
        for t in dwelling.thermal_mass_elements:
            ka += t.area * t.kvalue
        dwelling.thermal_mass_parameter = ka / dwelling.GFA

    dwelling.heat_calc_results = calc_heat_required(
        dwelling, dwelling.Texternal_heating, dwelling.winter_heat_gains)
    Q_required = dwelling.heat_calc_results['heat_required']
    for i in range(5, 9):
        Q_required[i] = 0
        dwelling.heat_calc_results['loss'][i] = 0
        dwelling.heat_calc_results['utilisation'][i] = 0
        dwelling.heat_calc_results['useful_gain'][i] = 0

    dwelling.Q_required = Q_required


def calc_heat_required(dwelling, Texternal, heat_gains):
    tau = dwelling.thermal_mass_parameter / (3.6 * dwelling.hlp)
    a = 1 + tau / 15.

    # These are for pcdf heat pumps - when heat pump is undersized it
    # can operator for longer hours on some days
    if dwelling.get('longer_heating_days'):
        N24_16_m, N24_9_m, N16_9_m = dwelling.longer_heating_days()
    else:
        N24_16_m, N24_9_m, N16_9_m = (None, None, None)

    L = dwelling.h * (dwelling.living_area_Theating - Texternal)
    util_living = heat_utilisation_factor(a, heat_gains, L)
    Tno_heat_living = temperature_no_heat(Texternal,
                                          dwelling.living_area_Theating,
                                          dwelling.heating_responsiveness,
                                          util_living,
                                          heat_gains,
                                          dwelling.h)

    Tmean_living_area = Tmean(
        Texternal, dwelling.living_area_Theating, Tno_heat_living,
        tau, dwelling.heating_control_type_sys1, N24_16_m, N24_9_m, N16_9_m, living_space=True)

    if dwelling.main_heating_fraction < 1 and hasattr(dwelling,
                                                      'heating_systems_heat_separate_areas') and dwelling.heating_systems_heat_separate_areas:
        if dwelling.main_heating_fraction > dwelling.living_area_fraction:
            # both systems contribute to rest of house
            weight_1 = 1 - dwelling.main_heating_2_fraction / \
                           (1 - dwelling.living_area_fraction)

            Tmean_other_1 = temperature_rest_of_dwelling(
                dwelling, Texternal, tau, a, L, heat_gains, dwelling.heating_control_type_sys1, N24_16_m, N24_9_m,
                N16_9_m)
            Tmean_other_2 = temperature_rest_of_dwelling(
                dwelling, Texternal, tau, a, L, heat_gains, dwelling.heating_control_type_sys2, N24_16_m, N24_9_m,
                N16_9_m)

            Tmean_other = Tmean_other_1 * \
                          weight_1 + Tmean_other_2 * (1 - weight_1)
        else:
            # only sys2 does rest of house
            Tmean_other = temperature_rest_of_dwelling(
                dwelling, Texternal, tau, a, L, heat_gains, dwelling.heating_control_type_sys2, N24_16_m, N24_9_m,
                N16_9_m)
    else:
        Tmean_other = temperature_rest_of_dwelling(
            dwelling, Texternal, tau, a, L, heat_gains, dwelling.heating_control_type_sys1, N24_16_m, N24_9_m, N16_9_m)

    if not dwelling.get('living_area_fraction'):
        dwelling.living_area_fraction = dwelling.living_area / dwelling.GFA

    meanT = dwelling.living_area_fraction * Tmean_living_area + \
            (1 - dwelling.living_area_fraction) * \
            Tmean_other + dwelling.temperature_adjustment
    L = dwelling.h * (meanT - Texternal)
    utilisation = heat_utilisation_factor(a, heat_gains, L)
    return dict(
        tau=tau,
        alpha=a,
        Texternal=Texternal,
        Tmean_living_area=Tmean_living_area,
        Tmean_other=Tmean_other,
        util_living=util_living,
        Tmean=meanT,
        loss=L,
        utilisation=utilisation,
        useful_gain=utilisation * heat_gains,
        heat_required=(range_cooker_factor(dwelling) *
                       0.024 * (
                           L - utilisation * heat_gains) * DAYS_PER_MONTH),
    )


def temperature_rest_of_dwelling(dwelling, Texternal, tau, a, L, heat_gains, control_type, N24_16_m, N24_9_m, N16_9_m):
    Theat_other = heating_temperature_other_space(dwelling.hlp, control_type)
    L = dwelling.h * (Theat_other - Texternal)
    Tno_heat_other = temperature_no_heat(Texternal,
                                         Theat_other,
                                         dwelling.heating_responsiveness,
                                         heat_utilisation_factor(
                                             a, heat_gains, L),
                                         heat_gains,
                                         dwelling.h)
    return Tmean(Texternal, Theat_other, Tno_heat_other, tau, control_type, N24_16_m, N24_9_m, N16_9_m,
                 living_space=False)


def Tmean(Texternal, Theat, Tno_heat, tau, control_type, N24_16_m, N24_9_m, N16_9_m, living_space):
    tc = 4 + 0.25 * tau
    dT = Theat - Tno_heat

    if control_type == 1 or control_type == 2 or living_space:
        # toff1=7
        # toff2=8
        # toff3=0
        # toff4=8
        # weekday
        u1 = temperature_reduction(dT, tc, 7)
        u2 = temperature_reduction(dT, tc, 8)
        Tweekday = Theat - (u1 + u2)

        # weekend
        u3 = 0  # (since Toff3=0)
        u4 = u2  # (since Toff4=Toff2)
        Tweekend = Theat - (u3 + u4)
    else:
        # toff1=9
        # toff2=8
        # toff3=9
        # toff4=8
        u1 = temperature_reduction(dT, tc, 9)
        u2 = temperature_reduction(dT, tc, 8)
        Tweekday = Theat - (u1 + u2)
        Tweekend = Tweekday

    if N24_16_m is None:
        return (5. / 7.) * Tweekday + (2. / 7.) * Tweekend
    else:
        WEm = numpy.array([9, 8, 9, 8, 9, 9, 9, 9, 8, 9, 8, 9])
        WDm = numpy.array([22, 20, 22, 22, 22, 21, 22, 22, 22, 22, 22, 22])
        return ((N24_16_m + N24_9_m) * Theat + (WEm - N24_16_m + N16_9_m) * Tweekend + (
            WDm - N16_9_m - N24_9_m) * Tweekday) / (WEm + WDm)


def temperature_reduction(delta_T, tc, time_off):
    return numpy.where(time_off <= tc,
                       (0.5 * time_off ** 2 / 24) * delta_T / tc,
                       delta_T * (time_off / 24. - (0.5 / 24.) * tc))


def temperature_no_heat(
        Texternal, Theat, responsiveness, heat_utilisation_factor,
        gains, h):
    return (1 - responsiveness) * (Theat - 2) + responsiveness * (Texternal + heat_utilisation_factor * gains / h)


def range_cooker_factor(dwelling):
    if dwelling.get('range_cooker_heat_required_scale_factor'):
        return dwelling.range_cooker_heat_required_scale_factor
    elif dwelling.main_sys_1.get('range_cooker_heat_required_scale_factor'):
        return dwelling.main_sys_1.range_cooker_heat_required_scale_factor
    elif dwelling.get("main_sys_2") and dwelling.main_sys_2.get('range_cooker_heat_required_scale_factor'):
        return dwelling.main_sys_2.range_cooker_heat_required_scale_factor
    else:
        return 1


def cooling_requirement(dwelling):
    fcool = dwelling.fraction_cooled
    if fcool == 0:
        dwelling.Q_cooling_required = numpy.array([0., ] * 12)
        return

    Texternal_summer = dwelling.external_temperature_summer
    L = dwelling.h * (dwelling.Tcooling - Texternal_summer)
    G = dwelling.summer_heat_gains

    gamma = G / L
    assert not 1 in gamma  # !!! Sort this out!

    tau = dwelling.thermal_mass_parameter / (3.6 * dwelling.hlp)
    a = 1 + tau / 15.
    utilisation = numpy.where(gamma <= 0,
                              1,
                              (1 - gamma ** -a) / (1 - gamma ** -(a + 1)))

    Qrequired = numpy.array([0., ] * 12)
    Qrequired[5:8] = (0.024 * (G - utilisation * L) * DAYS_PER_MONTH)[5:8]

    # No cooling in months where heating would be more than half of cooling
    heat_calc_results = calc_heat_required(
        dwelling, Texternal_summer, G + dwelling.heating_system_pump_gain)
    Qheat_summer = heat_calc_results['heat_required']
    Qrequired = numpy.where(3 * Qheat_summer < Qrequired,
                            Qrequired,
                            0)

    fintermittent = .25
    dwelling.Q_cooling_required = Qrequired * fcool * fintermittent


def heating_temperature_other_space(hlp, control_type):
    hlp = numpy.where(hlp < 6, hlp, 6)
    if control_type == 1:
        return 21. - 0.5 * hlp
    else:
        return 21. - hlp + 0.085 * hlp ** 2


def heat_utilisation_factor(a, heat_gains, heat_loss):
    gamma = heat_gains / heat_loss
    if 1 in gamma:
        # !!! Is this really right??
        raise Exception("Do we ever get here?")
        return numpy.where(gamma != 1,
                           (1 - gamma ** a) / (1 - gamma ** (a + 1)),
                           a / (a + 1))
    else:
        return (1 - gamma ** a) / (1 - gamma ** (a + 1))


def systems(dwelling):
    dwelling.Q_main_1 = dwelling.fraction_of_heat_from_main * \
                        dwelling.main_heating_fraction * dwelling.Q_required
    dwelling.sys1_space_effy = dwelling.main_sys_1.space_heat_effy(
        dwelling.Q_main_1)
    dwelling.Q_spaceheat_main = dwelling.Q_main_1 * \
                                100 / dwelling.sys1_space_effy

    if dwelling.get('main_sys_2'):
        dwelling.Q_main_2 = dwelling.fraction_of_heat_from_main * \
                            dwelling.main_heating_2_fraction * dwelling.Q_required
        dwelling.sys2_space_effy = dwelling.main_sys_2.space_heat_effy(
            dwelling.Q_main_2)
        dwelling.Q_spaceheat_main_2 = dwelling.Q_main_2 * \
                                      100 / dwelling.sys2_space_effy
    else:
        dwelling.Q_spaceheat_main_2 = numpy.zeros(12)
        dwelling.Q_main_2 = [0, ]
    if dwelling.fraction_of_heat_from_main < 1:
        Q_secondary = (
                          1 - dwelling.fraction_of_heat_from_main) * dwelling.Q_required
        dwelling.secondary_space_effy = dwelling.secondary_sys.space_heat_effy(
            Q_secondary)
        dwelling.Q_spaceheat_secondary = Q_secondary * \
                                         100 / dwelling.secondary_space_effy
    else:
        dwelling.Q_spaceheat_secondary = numpy.zeros(12)

    dwelling.water_effy = dwelling.water_sys.water_heat_effy(
        dwelling.output_from_water_heater)

    if hasattr(dwelling.water_sys, "keep_hot_elec_consumption"):
        dwelling.Q_waterheat = (
                                   dwelling.output_from_water_heater - dwelling.combi_loss_monthly) * 100 / dwelling.water_effy
    else:
        dwelling.Q_waterheat = dwelling.output_from_water_heater * \
                               100 / dwelling.water_effy

    dwelling.Q_spacecooling = dwelling.Q_cooling_required / \
                              dwelling.cooling_seer


def pv(dwelling):
    if dwelling.get('photovoltaic_systems'):
        dwelling.pv_electricity_onsite_fraction = 0.5
        dwelling.pv_electricity = 0
        for pv_system in dwelling.photovoltaic_systems:
            dwelling.pv_electricity += (0.8 * pv_system['kWp'] *
                                        pv_system['Igh'] *
                                        pv_system['overshading_factor'])
    else:
        dwelling.pv_electricity = 0
        dwelling.pv_electricity_onsite_fraction = 0.


def wind_turbines(dwelling):
    if dwelling.get('N_wind_turbines') and dwelling.N_wind_turbines > 0:
        wind_speed = 5 * dwelling.wind_turbine_speed_correction_factor
        PA = .6125 * wind_speed ** 3
        CP_G_IE = .24
        A = .25 * math.pi * dwelling.wind_turbine_rotor_diameter ** 2
        p_wind = A * PA * CP_G_IE

        dwelling.wind_electricity = dwelling.N_wind_turbines * \
                                    p_wind * 1.9 * 8766 * 0.001
        dwelling.wind_electricity_onsite_fraction = 0.7
    else:
        dwelling.wind_electricity = 0
        dwelling.wind_electricity_onsite_fraction = 0


def hydro(dwelling):
    if dwelling.get('hydro_electricity'):
        dwelling.hydro_electricity_onsite_fraction = 0.4
    else:
        dwelling.hydro_electricity = 0
        dwelling.hydro_electricity_onsite_fraction = 0.


def chp(dwelling):
    if dwelling.get('chp_water_elec'):
        e_summer = dwelling.chp_water_elec
        e_space = dwelling.chp_space_elec

        # !!! Can micro chp be a second main system??

        # !!! Need water heating only option
        if dwelling.water_sys is dwelling.main_sys_1:
            if dwelling.get('use_immersion_heater_summer') and dwelling.use_immersion_heater_summer:
                b64 = sum(x[0] for x in
                          zip(dwelling.output_from_water_heater,
                              dwelling.Q_required)
                          if x[1] > 0)
            else:
                b64 = sum(dwelling.output_from_water_heater)
        else:
            b64 = 0
            e_summer = 0

        b98 = sum(dwelling.Q_required)
        b204 = dwelling.fraction_of_heat_from_main * \
               dwelling.main_heating_fraction

        # !!! Need to check sign of result

        dwelling.chp_electricity = -(b98 * b204 * e_space + b64 * e_summer)
        dwelling.chp_electricity_onsite_fraction = 0.4
    else:
        dwelling.chp_electricity = 0
        dwelling.chp_electricity_onsite_fraction = 0


def sum_it(x):
    try:
        return sum(x)
    except TypeError:
        return x


def set_fuel_use(dwelling,
                 label,
                 regulated,
                 energy,
                 co2_factor,
                 cost,
                 primary_energy_factor):
    emissions = sum_it(energy * co2_factor)
    fuel_cost = sum_it(energy * cost)
    primary_energy = sum_it(energy * primary_energy_factor)

    if dwelling.get("energy_use_%s" % label):
        old_energy = dwelling["energy_use_%s" % label]
        old_emissions = dwelling["emissions_%s" % label]
        old_cost = dwelling["cost_%s" % label]
        old_pe = dwelling["primary_energy_%s" % label]
    else:
        old_energy = 0
        old_emissions = 0
        old_cost = 0
        old_pe = 0

    dwelling["energy_use_%s" % label] = sum_it(energy) + old_energy
    dwelling["emissions_%s" % label] = emissions + old_emissions
    dwelling["cost_%s" % label] = fuel_cost + old_cost
    dwelling["primary_energy_%s" % label] = primary_energy + old_pe

    # Offset energy is always regulated?
    if sum_it(energy) < 0:
        dwelling.energy_use_offset += sum_it(energy)
        dwelling.emissions_offset += emissions
        dwelling.cost_offset += fuel_cost
        dwelling.primary_energy_offset += primary_energy

    if regulated:
        dwelling.energy_use += sum_it(energy)
        dwelling.emissions += emissions
        dwelling.fuel_cost += fuel_cost
        dwelling.primary_energy += primary_energy


def fuel_use(dwelling):
    cost_export = ELECTRICITY_SOLD.unit_price() / 100
    C_el_offset = ELECTRICITY_OFFSET.co2_factor
    primary_el_offset = ELECTRICITY_OFFSET.primary_energy_factor

    C_el = dwelling.general_elec_co2_factor
    cost_el = dwelling.general_elec_price / 100.
    PE_el = dwelling.general_elec_PE

    dwelling.energy_use = 0
    dwelling.energy_use_offset = 0
    dwelling.emissions = 0
    dwelling.emissions_offset = 0
    dwelling.fuel_cost = dwelling.cost_standing
    dwelling.cost_offset = 0
    dwelling.primary_energy = 0
    dwelling.primary_energy_offset = 0

    immersion_months = numpy.array([0, ] * 12)
    if dwelling.get('use_immersion_heater_summer') and dwelling.use_immersion_heater_summer:
        for i in range(5, 9):
            immersion_months[i] = 1

        Q_summer_immersion = dwelling.Q_waterheat * immersion_months
        set_fuel_use(dwelling, "water_summer_immersion", True,
                     Q_summer_immersion,
                     C_el,
                     dwelling.water_fuel_price_immersion / 100.,
                     PE_el)

    else:
        Q_summer_immersion = dwelling.Q_waterheat * immersion_months
        set_fuel_use(dwelling, "water_summer_immersion", True,
                     0, 0, 0, 0)

    Q_water_heater = dwelling.Q_waterheat - Q_summer_immersion
    set_fuel_use(dwelling, "water", True,
                 Q_water_heater,
                 dwelling.water_sys.co2_factor(),
                 dwelling.water_sys.water_fuel_price(dwelling) / 100.,
                 dwelling.water_sys.primary_energy_factor())

    set_fuel_use(dwelling, "heating_main", True,
                 dwelling.Q_spaceheat_main,
                 dwelling.main_sys_1.co2_factor(),
                 dwelling.main_sys_1.fuel_price(dwelling) / 100.,
                 dwelling.main_sys_1.primary_energy_factor())

    chp_elec = 0
    # !!! Can main sys 2 be community heating?
    if hasattr(dwelling.main_sys_1, 'heat_to_power_ratio'):
        if dwelling.main_sys_1.heat_to_power_ratio != 0:
            chp_elec += (sum(dwelling.Q_spaceheat_main)
                         ) / dwelling.main_sys_1.heat_to_power_ratio

    if hasattr(dwelling.water_sys, 'heat_to_power_ratio'):
        if dwelling.water_sys.heat_to_power_ratio != 0:
            chp_elec += (sum(Q_water_heater)
                         ) / dwelling.water_sys.heat_to_power_ratio

    if chp_elec > 0:
        set_fuel_use(dwelling, "community_elec_credits", True,
                     -chp_elec,
                     C_el_offset,
                     0,
                     primary_el_offset)

    community_distribution_elec = 0
    # !!! Can main sys 2 be community heating?
    if dwelling.main_sys_1.system_type == HeatingTypes.community:
        community_distribution_elec += 0.01 * sum(dwelling.Q_spaceheat_main)
    if dwelling.water_sys.system_type == HeatingTypes.community:
        community_distribution_elec += 0.01 * sum(Q_water_heater)
    if community_distribution_elec > 0:
        # !!! Fuel costs should come from sap_tables
        set_fuel_use(dwelling, "community_distribution", True,
                     community_distribution_elec,
                     .517,
                     0,
                     2.92)

        total_community_emissions = (
            (dwelling.emissions_heating_main
             if dwelling.main_sys_1.system_type == HeatingTypes.community
             else 0) +
            (dwelling.emissions_water
             if dwelling.water_sys.system_type == HeatingTypes.community
             else 0) +
            dwelling.emissions_community_distribution +
            (dwelling.emissions_community_elec_credits
             if dwelling.get('emissions_community_elec_credits') else 0))
        if total_community_emissions < 0:
            set_fuel_use(dwelling,
                         "negative_community_emissions_correction", True,
                         1,
                         -total_community_emissions,
                         0,
                         0)

    if dwelling.get('main_sys_2'):
        set_fuel_use(dwelling, "heating_main_2", True,
                     dwelling.Q_spaceheat_main_2,
                     dwelling.main_sys_2.co2_factor(),
                     dwelling.main_sys_2.fuel_price(dwelling) / 100,
                     dwelling.main_sys_2.primary_energy_factor())
    else:
        set_fuel_use(dwelling, "heating_main_2", True,
                     0, 0, 0, 0)

    if dwelling.get('secondary_sys'):
        set_fuel_use(dwelling, "heating_secondary", True,
                     dwelling.Q_spaceheat_secondary,
                     dwelling.secondary_sys.co2_factor(),
                     dwelling.secondary_sys.fuel_price(dwelling) / 100.,
                     dwelling.secondary_sys.primary_energy_factor())
    else:
        set_fuel_use(dwelling, "heating_secondary", True,
                     0, 0, 0, 0)

    set_fuel_use(dwelling, "cooling", True,
                 dwelling.Q_spacecooling, C_el, cost_el, PE_el)

    set_fuel_use(dwelling, "fans_and_pumps", True,
                 dwelling.Q_fans_and_pumps, C_el, cost_el, PE_el)

    set_fuel_use(dwelling, "mech_vent_fans", True,
                 dwelling.Q_mech_vent_fans, C_el,
                 dwelling.mech_vent_elec_price / 100,
                 PE_el)

    set_fuel_use(dwelling, "lighting", True,
                 dwelling.annual_light_consumption, C_el, cost_el, PE_el)

    set_fuel_use(dwelling, "appliances", False,
                 sum(dwelling.appliance_consumption), C_el, cost_el, PE_el)

    # For cooking cost, assume that 40% of cooking is by gas, 60% by
    # electric (matches the emissions calc)
    cost_cooking_fuel = .4 * .031 + .6 * cost_el
    pe_cooking_fuel = .4 * 1.02 + .6 * PE_el
    cooking_fuel_kWh = (35 + 7 * dwelling.Nocc) * 8.76
    C_cooking = (119 + 24 * dwelling.Nocc) / dwelling.GFA / cooking_fuel_kWh
    set_fuel_use(dwelling, "cooking", False,
                 cooking_fuel_kWh, C_cooking, cost_cooking_fuel, pe_cooking_fuel)

    set_fuel_use(dwelling, "pv", True,
                 -dwelling.pv_electricity, C_el_offset,
                 (cost_el * dwelling.pv_electricity_onsite_fraction +
                  cost_export * (1 - dwelling.pv_electricity_onsite_fraction)),
                 primary_el_offset)

    set_fuel_use(dwelling, "wind", True,
                 -dwelling.wind_electricity, C_el_offset,
                 (cost_el * dwelling.wind_electricity_onsite_fraction +
                  cost_export * (
                      1 - dwelling.wind_electricity_onsite_fraction)),
                 primary_el_offset)

    set_fuel_use(dwelling, "hydro", True,
                 -dwelling.hydro_electricity, C_el_offset,
                 (cost_el * dwelling.hydro_electricity_onsite_fraction +
                  cost_export * (
                      1 - dwelling.hydro_electricity_onsite_fraction)),
                 primary_el_offset)

    set_fuel_use(dwelling, "chp", True,
                 -dwelling.chp_electricity, C_el_offset,
                 (cost_el * dwelling.chp_electricity_onsite_fraction +
                  cost_export * (
                      1 - dwelling.chp_electricity_onsite_fraction)),
                 primary_el_offset)

    if (dwelling.get('appendix_q_systems') and
                dwelling.appendix_q_systems != None):
        for sys in dwelling.appendix_q_systems:
            if 'fuel_saved' in sys:
                set_fuel_use(dwelling, "appendix_q_generated", True,
                             -sys['generated'],
                             sys['fuel_saved'].co2_factor,
                             sys['fuel_saved'].unit_price() / 100,
                             sys['fuel_saved'].primary_energy_factor)
            else:
                set_fuel_use(dwelling, "appendix_q_generated", True,
                             -sys['generated'],
                             C_el,
                             cost_el,
                             PE_el)

            if 'fuel_used' in sys:
                set_fuel_use(dwelling, "appendix_q_used", True,
                             sys['used'],
                             sys['fuel_used'].co2_factor,
                             sys['fuel_used'].unit_price() / 100,
                             sys['fuel_used'].primary_energy_factor)
            else:
                set_fuel_use(dwelling, "appendix_q_used", True,
                             sys['used'],
                             C_el,
                             cost_el,
                             PE_el)


def sap(dwelling):
    sap_rating_energy_cost = dwelling.fuel_cost
    ecf = 0.47 * sap_rating_energy_cost / (dwelling.GFA + 45)
    dwelling.sap_energy_cost_factor = ecf
    dwelling.sap_value = 117 - 121 * \
                               math.log10(ecf) if ecf >= 3.5 else 100 - 13.95 * ecf

    r = dwelling.report
    r.start_section("", "SAP Calculation")
    r.add_single_result("SAP value", "258", dwelling.sap_value)


def fee(dwelling):
    dwelling.fee_rating = (
                              sum(dwelling.Q_required) + sum(dwelling.Q_cooling_required)) / dwelling.GFA

    r = dwelling.report
    r.start_section("", "FEE Calculation")
    r.add_single_result(
        "Fabric energy efficiency (kWh/m2)", "109", dwelling.fee_rating)


def der(dwelling):
    dwelling.der_rating = dwelling.emissions / dwelling.GFA

    r = dwelling.report
    r.start_section("", "DER Calculation")
    r.add_single_result(
        "Dwelling emissions (kg/yr)", "272", dwelling.emissions)
    r.add_single_result("DER rating (kg/m2/year)", "273", dwelling.der_rating)


def ter(dwelling, heating_fuel):
    # Need to convert from 2010 emissions factors used in the calc to
    # 2006 factors
    C_h = ((dwelling.emissions_water +
            dwelling.emissions_heating_main) / dwelling.main_sys_1.fuel.emission_factor_adjustment +
           (dwelling.emissions_heating_secondary +
            dwelling.emissions_fans_and_pumps) / dwelling.electricity_tariff.emission_factor_adjustment)
    C_l = dwelling.emissions_lighting / \
          dwelling.electricity_tariff.emission_factor_adjustment

    FF = heating_fuel.fuel_factor
    EFA_h = heating_fuel.emission_factor_adjustment
    EFA_l = dwelling.electricity_tariff.emission_factor_adjustment
    dwelling.ter_rating = (C_h * FF * EFA_h + C_l * EFA_l) * (
        1 - 0.2) * (1 - 0.25) / dwelling.GFA

    r = dwelling.report
    r.start_section("", "TER Calculation")
    r.add_single_result(
        "Emissions per m2 for space and water heating", "272a", C_h / dwelling.GFA)
    r.add_single_result(
        "Emissions per m2 for lighting", "272b", C_l / dwelling.GFA)
    r.add_single_result("Heating fuel factor", None, FF)
    r.add_single_result("Heating fuel emission factor adjustment", None, EFA_h)
    r.add_single_result("Electricity emission factor adjustment", None, EFA_l)
    r.add_single_result("TER", 273, dwelling.ter_rating)
