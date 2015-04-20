from . import rdsap
from . import tables
from . import worksheet
from sap.tables import CylinderInsulationTypes, GlazingTypes


def perform_demand_calc(dwelling):
    worksheet.ventilation(dwelling)
    worksheet.heat_loss(dwelling)
    worksheet.hot_water_use(dwelling)
    worksheet.internal_heat_gain(dwelling)
    worksheet.solar(dwelling)
    worksheet.heating_requirement(dwelling)
    worksheet.cooling_requirement(dwelling)
    worksheet.water_heater_output(dwelling)


def perform_full_calc(dwelling):
    perform_demand_calc(dwelling)
    worksheet.systems(dwelling)
    worksheet.pv(dwelling)
    worksheet.wind_turbines(dwelling)
    worksheet.hydro(dwelling)
    worksheet.chp(dwelling)
    worksheet.fuel_use(dwelling)



class CalculationReport(object):

    def __init__(self):
        self.txt = ""

    def start_section(self, number, title):
        title_str = "%s %s\n" % (number, title)
        self.txt += "\n"
        self.txt += title_str
        self.txt += "=" * len(title_str) + "\n"

    def add_annotation(self, label):
        self.txt += "%s\n" % (label,)

    def add_single_result(self, label, code, values):
        self.add_monthly_result(label, code, values)

    def add_monthly_result(self, label, code, values):
        if code != None:
            self.txt += "%s %s (%s)\n" % (label, values, code)
        else:
            self.txt += "%s %s\n" % (label, values)

    def print_report(self):
        return self.txt


class CalculationResults(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.report = CalculationReport()


# TODO: could probably rather subclass Dwelling
# FIXME: seems that worksheet in any case depends on the dwelling object having report object. May better to just merge this into Dwelling
class DwellingResultsWrapper(object):
    def __init__(self, dwelling):
        self.dwelling = dwelling

        self.results = CalculationResults()  # just use a Dict, don't really need CalculationResults for now
        self.report = self.results.report
        # self.report = CalculationReport()
        # self.results['report']

    # FIXME: hack to allow using setattr without messing with the attrs set in __init__. Would be better to acces results explicitly
    # This is really fragile...
    def __setattr__(self, key, value):
        if key not in ['dwelling', 'results', 'report']:
            self.results[key] = value
        else:
            self.__dict__[key]= value


    def __getattr__(self, item):
        """
        return from results if k exists, otherwise return from wrapped
        dwelling
        """
        try:
            return self.dwelling.__getattr__(item)
        except AttributeError:
            try:
                return self.results[item]
            except KeyError:
                raise AttributeError(item)

    def true_and_not_missing(self, name):
        return hasattr(self, name) and getattr(self, name)



def run_sap(input_dwelling):
    """
    Run SAP on the input dwelling
    :param input_dwelling:
    :return:
    """
    dwelling = DwellingResultsWrapper(input_dwelling)
    dwelling.reduced_gains = False

    tables.do_sap_table_lookups(dwelling)
    perform_full_calc(dwelling)
    worksheet.sap(dwelling)
    worksheet.build_report(dwelling)

    input_dwelling.er_results = dwelling.results


def run_fee(input_dwelling):
    dwelling = DwellingResultsWrapper(input_dwelling)
    dwelling.reduced_gains = True

    dwelling.cooled_area = input_dwelling.GFA
    dwelling.low_energy_bulb_ratio = 1
    dwelling.ventilation_type = tables.VentilationTypes.NATURAL
    dwelling.water_heating_type_code = 907
    dwelling.fghrs = None

    if input_dwelling.GFA <= 70:
        dwelling.Nfansandpassivevents = 2
    elif input_dwelling.GFA <= 100:
        dwelling.Nfansandpassivevents = 3
    else:
        dwelling.Nfansandpassivevents = 4

    if dwelling.overshading == tables.OvershadingTypes.VERY_LITTLE:
        dwelling.overshading = tables.OvershadingTypes.AVERAGE

    dwelling.main_heating_pcdf_id = None
    dwelling.main_heating_type_code = 191
    dwelling.main_sys_fuel = tables.fuel_from_code(1)
    dwelling.heating_emitter_type = tables.HeatEmitters.RADIATORS
    dwelling.control_type_code = 2106
    dwelling.sys1_delayed_start_thermostat = False
    dwelling.use_immersion_heater_summer = False
    dwelling.immersion_type = None
    dwelling.solar_collector_aperture = None
    dwelling.cylinder_is_thermal_store = False
    dwelling.thermal_store_type = None
    dwelling.sys1_sedbuk_2005_effy = None
    dwelling.sys1_sedbuk_2009_effy = None

    # Don't really need to set these, but sap_tables isn't happy if we don't
    dwelling.cooling_packaged_system = True
    dwelling.cooling_energy_label = "A"
    dwelling.cooling_compressor_control = ""
    dwelling.water_sys_fuel = dwelling.electricity_tariff
    dwelling.main_heating_fraction = 1
    dwelling.main_heating_2_fraction = 0

    tables.do_sap_table_lookups(dwelling)

    dwelling.pump_gain = 0
    dwelling.heating_system_pump_gain = 0

    perform_demand_calc(dwelling)
    worksheet.fee(dwelling)
    worksheet.build_report(dwelling)

    input_dwelling.fee_results = dwelling.results


def run_der(dwelling):
    wrapped_dwelling = DwellingResultsWrapper(dwelling)
    wrapped_dwelling.reduced_gains = True

    if wrapped_dwelling.overshading == tables.OvershadingTypes.VERY_LITTLE:
        wrapped_dwelling.overshading = tables.OvershadingTypes.AVERAGE

    tables.do_sap_table_lookups(wrapped_dwelling)
    perform_full_calc(wrapped_dwelling)
    worksheet.der(wrapped_dwelling)
    worksheet.build_report(wrapped_dwelling)

    dwelling.der_results = wrapped_dwelling.results
    if (wrapped_dwelling.main_sys_fuel.is_mains_gas or
            (hasattr(wrapped_dwelling, 'main_sys_2_fuel') and
                 wrapped_dwelling.main_sys_2_fuel.is_mains_gas)):
        dwelling.ter_fuel = tables.fuel_from_code(1)
    elif sum(wrapped_dwelling.Q_main_1) >= sum(wrapped_dwelling.Q_main_2):
        dwelling.ter_fuel = wrapped_dwelling.main_sys_fuel
    else:
        dwelling.ter_fuel = wrapped_dwelling.main_sys_2_fuel


def element_type_area(etype, els):
    return sum(e.area for e in els if e.element_type == etype)


def run_ter(dwelling):
    wrapped_dwelling = DwellingResultsWrapper(dwelling)

    wrapped_dwelling.reduced_gains = True

    net_wall_area = element_type_area(worksheet.HeatLossElementTypes.EXTERNAL_WALL,
                                      wrapped_dwelling.heat_loss_elements)
    opaque_door_area = element_type_area(worksheet.HeatLossElementTypes.OPAQUE_DOOR,
                                         wrapped_dwelling.heat_loss_elements)
    window_area = sum(o.area for o in wrapped_dwelling.openings if o.opening_type.roof_window == False)
    roof_window_area = sum(o.area for o in wrapped_dwelling.openings if o.opening_type.roof_window == True)
    gross_wall_area = net_wall_area + window_area + opaque_door_area

    new_opening_area = min(wrapped_dwelling.GFA * .25, gross_wall_area)
    new_window_area = max(new_opening_area - 1.85, 0)

    floor_area = element_type_area(worksheet.HeatLossElementTypes.EXTERNAL_FLOOR,
                                   wrapped_dwelling.heat_loss_elements)
    net_roof_area = element_type_area(worksheet.HeatLossElementTypes.EXTERNAL_ROOF,
                                      wrapped_dwelling.heat_loss_elements)
    roof_area = net_roof_area + roof_window_area

    new_heat_loss_elements = []
    new_heat_loss_elements.append(worksheet.HeatLossElement(
        area=gross_wall_area - new_window_area - 1.85,
        Uvalue=.35,
        is_external=True,
        element_type=worksheet.HeatLossElementTypes.EXTERNAL_WALL,
    ))
    new_heat_loss_elements.append(worksheet.HeatLossElement(
        area=1.85,
        Uvalue=2,
        is_external=True,
        element_type=worksheet.HeatLossElementTypes.OPAQUE_DOOR,
    ))
    new_heat_loss_elements.append(worksheet.HeatLossElement(
        area=floor_area,
        Uvalue=.25,
        is_external=True,
        element_type=worksheet.HeatLossElementTypes.EXTERNAL_FLOOR,
    ))
    new_heat_loss_elements.append(worksheet.HeatLossElement(
        area=roof_area,
        Uvalue=.16,
        is_external=True,
        element_type=worksheet.HeatLossElementTypes.EXTERNAL_ROOF,
    ))
    new_heat_loss_elements.append(worksheet.HeatLossElement(
        area=new_window_area,
        Uvalue=1. / (1. / 2 + .04),
        is_external=True,
        element_type=worksheet.HeatLossElementTypes.GLAZING,
    ))

    wrapped_dwelling.heat_loss_elements = new_heat_loss_elements

    ter_opening_type = worksheet.OpeningType(
        glazing_type=GlazingTypes.DOUBLE,
        gvalue=.72,
        frame_factor=0.7,
        Uvalue=2,
        roof_window=False)

    new_openings = [worksheet.Opening(
        area=new_window_area,
        orientation_degrees=90,
        opening_type=ter_opening_type)
    ]

    wrapped_dwelling.openings = new_openings

    wrapped_dwelling.thermal_mass_parameter = 250
    wrapped_dwelling.overshading = tables.OvershadingTypes.AVERAGE

    wrapped_dwelling.Nshelteredsides = 2
    wrapped_dwelling.Uthermalbridges = .11
    wrapped_dwelling.ventilation_type = tables.VentilationTypes.NATURAL
    wrapped_dwelling.pressurisation_test_result = 10
    wrapped_dwelling.Nchimneys = 0
    wrapped_dwelling.Nflues = 0
    if dwelling.GFA > 80:
        wrapped_dwelling.Nfansandpassivevents = 3
    else:
        wrapped_dwelling.Nfansandpassivevents = 2

    wrapped_dwelling.main_heating_type_code = 102
    wrapped_dwelling.main_heating_pcdf_id = None
    wrapped_dwelling.heating_emitter_type = tables.HeatEmitters.RADIATORS
    wrapped_dwelling.heating_emitter_type2 = None
    wrapped_dwelling.main_heating_fraction = 1
    wrapped_dwelling.main_heating_2_fraction = 0
    wrapped_dwelling.main_sys_fuel = tables.fuel_from_code(1)
    wrapped_dwelling.main_heating_oil_pump_inside_dwelling = None
    wrapped_dwelling.main_heating_2_oil_pump_inside_dwelling = None
    wrapped_dwelling.control_type_code = 2106
    wrapped_dwelling.sys1_has_boiler_interlock = True
    wrapped_dwelling.sys1_load_compensator = None
    wrapped_dwelling.central_heating_pump_in_heated_space = True
    wrapped_dwelling.appendix_q_systems = None

    wrapped_dwelling.has_hw_time_control = True
    wrapped_dwelling.water_heating_type_code = 901
    wrapped_dwelling.use_immersion_heater_summer = False
    wrapped_dwelling.has_hw_cylinder = True
    wrapped_dwelling.hw_cylinder_volume = 150
    wrapped_dwelling.cylinder_in_heated_space = True
    wrapped_dwelling.hw_cylinder_insulation_type = CylinderInsulationTypes.FOAM
    wrapped_dwelling.hw_cylinder_insulation = 35
    wrapped_dwelling.primary_pipework_insulated = False
    wrapped_dwelling.has_cylinderstat = True
    wrapped_dwelling.hwsys_has_boiler_interlock = True
    wrapped_dwelling.measured_cylinder_loss = None
    wrapped_dwelling.solar_collector_aperture = None
    wrapped_dwelling.has_electric_shw_pump = False
    wrapped_dwelling.solar_storage_combined_cylinder = False
    wrapped_dwelling.wwhr_systems = None
    wrapped_dwelling.fghrs = None
    wrapped_dwelling.cylinder_is_thermal_store = False
    wrapped_dwelling.thermal_store_type = None
    wrapped_dwelling.sys1_sedbuk_2005_effy = None
    wrapped_dwelling.sys1_sedbuk_2009_effy = None

    wrapped_dwelling.sys1_delayed_start_thermostat = False

    wrapped_dwelling.low_water_use = False
    wrapped_dwelling.secondary_sys_fuel = wrapped_dwelling.electricity_tariff
    wrapped_dwelling.secondary_heating_type_code = 691
    wrapped_dwelling.secondary_hetas_approved = False
    wrapped_dwelling.low_energy_bulb_ratio = .3

    wrapped_dwelling.cooled_area = 0

    # Need to make sure no summer immersion and no renewables 

    tables.do_sap_table_lookups(wrapped_dwelling)
    wrapped_dwelling.main_sys_1.heating_effy_winter = 78 + .9
    wrapped_dwelling.main_sys_1.heating_effy_summer = 78 - 9.2

    perform_full_calc(wrapped_dwelling)
    worksheet.ter(wrapped_dwelling, dwelling.ter_fuel)
    worksheet.build_report(wrapped_dwelling)
    dwelling.ter_results = wrapped_dwelling.results


def apply_low_energy_lighting(base, d):
    if ((hasattr(d, 'low_energy_bulb_ratio') and d.low_energy_bulb_ratio == 1) or
                d.lighting_outlets_low_energy == d.lighting_outlets_total):
        return False

    d.low_energy_bulb_ratio = 1
    return True


def needs_separate_solar_cylinder(base, d):
    if base.water_sys.system_type in [
        tables.HeatingSystem.TYPES.cpsu,
        tables.HeatingSystem.TYPES.combi,
        tables.HeatingSystem.TYPES.storage_combi,
        tables.HeatingSystem.TYPES.heat_pump,
        tables.HeatingSystem.TYPES.pcdf_heat_pump,
    ]:
        return True
    if (hasattr(base, 'instantaneous_pou_water_heating') and
            base.instantaneous_pou_water_heating):
        return True
    if (base.water_sys.system_type == tables.HeatingSystem.TYPES.community
        and not hasattr(d, 'hw_cylinder_volume')):
        return True
    if (base.water_sys.system_type == tables.HeatingSystem.TYPES.microchp
        and base.water_sys.has_integral_store):
        return True

    return False


def apply_solar_hot_water(base, d):
    if d.is_flat:
        return False
    if hasattr(d, 'solar_collector_aperture') and d.solar_collector_aperture > 0:
        return False
    d.solar_collector_aperture = 3
    d.collector_zero_loss_effy = .7
    d.collector_heat_loss_coeff = 1.8
    d.collector_orientation = 180.
    d.collector_pitch = 30.
    d.collector_overshading = tables.PVOvershading.MODEST
    d.has_electric_shw_pump = True
    d.solar_dedicated_storage_volume = 75.

    if needs_separate_solar_cylinder(base, d):
        d.solar_storage_combined_cylinder = False
    else:
        assert d.hw_cylinder_volume > 0
        d.solar_storage_combined_cylinder = True
        if d.hw_cylinder_volume < 190 and hasattr(d, 'measured_cylinder_loss'):
            old_vol_fac = tables.hw_volume_factor(d.hw_cylinder_volume)
            new_vol_fac = tables.hw_volume_factor(190)
            d.measured_cylinder_loss *= new_vol_fac * 190 / (old_vol_fac * d.hw_cylinder_volume)
            d.hw_cylinder_volume = 190
        else:
            d.hw_cylinder_volume = max(d.hw_cylinder_volume, 190.)

    return True


def apply_pv(base, d):
    if d.is_flat:
        return False
    if hasattr(d, 'photovoltaic_systems') and len(d.photovoltaic_systems) > 0:
        return False

    pv_system = dict(
        kWp=2.5,
        pitch=30,
        orientation=180,
        overshading_category=tables.PVOvershading.MODEST
    )
    d.photovoltaic_systems = [pv_system, ]
    return True


def apply_wind(base, d):
    if d.is_flat:
        return False
    if hasattr(d, 'N_wind_turbines') and d.N_wind_turbines > 0:
        return False
    d.N_wind_turbines = 1
    d.wind_turbine_rotor_diameter = 2.0
    d.wind_turbine_hub_height = 2.0
    return True


IMPROVEMENTS = [
    ("E", .45, apply_low_energy_lighting),
    ("N", .95, apply_solar_hot_water),
    ("U", .95, apply_pv),
    ("V", .95, apply_wind),
]


class ImprovementResult:
    def __init__(self, tag, sap_change, cost_change, co2_change):
        self.tag = tag
        self.sap_change = sap_change
        self.co2_change = co2_change
        self.cost_change = cost_change


class ImprovementResults:
    def __init__(self):
        self.improvement_effects = []

    def add(self, i):
        self.improvement_effects.append(i)


def apply_previous_improvements(base, target, previous):
    for improvement in previous:
        name, min_val, improve = [x for x in IMPROVEMENTS if x[0] == improvement.tag][0]
        improve(base, target)
        improve(base, target)


def run_improvements(dwelling):
    # Need to run the dwelling twice: once with pcdf fuel prices to
    # get cost chage, once with normal SAP fuel prices to get change
    # in SAP rating
    base_dwelling_pcdf_prices = DwellingResultsWrapper(dwelling)
    base_dwelling_pcdf_prices.reduced_gains = False
    base_dwelling_pcdf_prices.use_pcdf_fuel_prices = True
    tables.do_sap_table_lookups(base_dwelling_pcdf_prices)
    perform_full_calc(base_dwelling_pcdf_prices)
    worksheet.sap(base_dwelling_pcdf_prices)

    base_results_pcdf_prices = base_dwelling_pcdf_prices.results
    base_results = dwelling.er_results

    dwelling.improvement_results = ImprovementResults()

    base_cost = base_results_pcdf_prices.fuel_cost
    base_sap = base_results.sap_value
    base_co2 = base_results.emissions
    for name, min_improvement, improve in IMPROVEMENTS:
        wrapped_dwelling_pcdf_prices = DwellingResultsWrapper(dwelling)
        wrapped_dwelling_pcdf_prices.reduced_gains = False
        wrapped_dwelling_pcdf_prices.use_pcdf_fuel_prices = True

        wrapped_dwelling = DwellingResultsWrapper(dwelling)
        wrapped_dwelling.reduced_gains = False
        wrapped_dwelling.use_pcdf_fuel_prices = False

        apply_previous_improvements(
            base_dwelling_pcdf_prices,
            wrapped_dwelling,
            dwelling.improvement_results.improvement_effects)
        apply_previous_improvements(
            base_dwelling_pcdf_prices,
            wrapped_dwelling_pcdf_prices,
            dwelling.improvement_results.improvement_effects)

        if not improve(base_dwelling_pcdf_prices, wrapped_dwelling_pcdf_prices):
            continue

        improve(base_dwelling_pcdf_prices, wrapped_dwelling)

        tables.do_sap_table_lookups(wrapped_dwelling_pcdf_prices)
        perform_full_calc(wrapped_dwelling_pcdf_prices)
        worksheet.sap(wrapped_dwelling_pcdf_prices)

        tables.do_sap_table_lookups(wrapped_dwelling)
        perform_full_calc(wrapped_dwelling)
        worksheet.sap(wrapped_dwelling)

        sap_improvement = wrapped_dwelling.sap_value - base_sap
        if sap_improvement > min_improvement:
            dwelling.improvement_results.add(ImprovementResult(
                name,
                sap_improvement,
                wrapped_dwelling_pcdf_prices.fuel_cost - base_cost,
                wrapped_dwelling.emissions - base_co2))

            base_cost = wrapped_dwelling_pcdf_prices.fuel_cost
            base_sap = wrapped_dwelling.sap_value
            base_co2 = wrapped_dwelling.emissions

    improved_dwelling = DwellingResultsWrapper(dwelling)
    improved_dwelling.reduced_gains = False
    improved_dwelling.use_pcdf_fuel_prices = False
    for improvement in dwelling.improvement_results.improvement_effects:
        name, min_val, improve = [x for x in IMPROVEMENTS if x[0] == improvement.tag][0]
        improve(base_dwelling_pcdf_prices, improved_dwelling)

    tables.do_sap_table_lookups(improved_dwelling)
    perform_full_calc(improved_dwelling)
    worksheet.sap(improved_dwelling)
    worksheet.build_report(improved_dwelling)
    # print improved_dwelling.report.print_report()

    dwelling.improved_results = improved_dwelling.results

