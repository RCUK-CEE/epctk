"""
Defining heating systems

Encorporates parts of SAP main body and appendicies


"""
import logging

from .elements import HeatingSystem, HeatingTypes, ThermalStoreTypes, CylinderInsulationTypes, ImmersionTypes, FuelTypes
from .appendix import appendix_f, appendix_g, appendix_j, appendix_n
from .constants import USE_TABLE_4D_FOR_RESPONSIVENESS
from .fuels import ELECTRICITY_7HR, ELECTRICITY_10HR
from .io.pcdf import (get_boiler, get_solid_fuel_boiler, get_twin_burner_cooker_boiler, get_heat_pump, get_microchp)
from .tables import (combi_loss_table_3a, combi_loss_instant_without_keep_hot,
                     combi_loss_instant_with_timed_heat_hot,
                     combi_loss_instant_with_untimed_heat_hot, TABLE_D7, get_seasonal_effy_offset)
from .utils import SAPCalculationError


def pcdf_heating_system(dwelling, pcdf_id,
                        fuel, use_immersion_in_summer):
    """
    Get the PCDF heating system for the dwelling

    Try each type in turn until we get a heating system that is not None
    Args:
        dwelling:
        pcdf_id:
        fuel:
        use_immersion_in_summer:

    Raises:
        SAPCalculationError: if no PCDF heating system is found for the given code
    Returns:

    """
    pcdf_data = get_boiler(pcdf_id)

    if pcdf_data is not None:
        return gas_boiler_from_pcdf(dwelling, pcdf_data, fuel, use_immersion_in_summer)

    pcdf_data = get_solid_fuel_boiler(pcdf_id)

    if pcdf_data is not None:
        return appendix_j.solid_fuel_boiler_from_pcdf(pcdf_data, fuel, use_immersion_in_summer)

    pcdf_data = get_twin_burner_cooker_boiler(pcdf_id)
    if pcdf_data is not None:
        return twin_burner_cooker_boiler_from_pcdf(pcdf_data, fuel, use_immersion_in_summer)

    pcdf_data = get_heat_pump(pcdf_id)
    if pcdf_data is not None:
        return appendix_n.heat_pump_from_pcdf(dwelling, pcdf_data, fuel, use_immersion_in_summer)

    pcdf_data = get_microchp(pcdf_id)
    if pcdf_data is not None:
        return appendix_n.micro_chp_from_pcdf(dwelling, pcdf_data, fuel, use_immersion_in_summer)

    raise SAPCalculationError("Could not find a heating system in PCDF file for id {}".format(pcdf_id))


def gas_boiler_from_pcdf(dwelling, pcdf_data, fuel, use_immersion_in_summer):
    """
    Generate a gas boiler heating system from dwelling data


    Args:
        dwelling:
        pcdf_data:
        fuel:
        use_immersion_in_summer:

    Returns:
        HeatingSystem gas boiler heating system

    """
    # TODO: Refactor gas_boiler_from_pcdf into smaller easier to audit chunks

    if pcdf_data['main_type'] == "Combi":
        system_type = HeatingTypes.combi
    elif pcdf_data['main_type'] == "CPSU":
        system_type = HeatingTypes.cpsu
    else:
        system_type = HeatingTypes.regular_boiler

    sys = HeatingSystem(system_type,
                        pcdf_data['winter_effy'],
                        pcdf_data['summer_effy'],
                        False,  # summer immersion
                        pcdf_data['fan_assisted_flue'] == 'True',
                        True,  # ch pump
                        -1,
                        0.1,
                        fuel)  # Assumes 10% secondary fraction

    sys.has_warm_air_fan = False
    sys.sap_appendixD_eqn = pcdf_data['sap_appendixD_eqn']
    sys.is_condensing = pcdf_data['condensing']

    if pcdf_data['subsidiary_type'] == "with integral PFGHRD":
        if (pcdf_data['subsidiary_type_table'] == "" and
                    pcdf_data['subsidiary_type_index'] == ""):
            # integral PFGHRD, performance data included in boilerl data
            assert not dwelling.get('fghrs')
        else:
            if (dwelling.get('fghrs') and
                        dwelling.fghrs is None):
                # inputs expliticly say there is no fghrs, so don't
                # add one even if boiler specifies one
                pass
            else:
                if dwelling.get('fghrs'):
                    assert dwelling.fghrs['pcdf_id'] == pcdf_data['subsidiary_type_index']
                else:
                    dwelling.fghrs = dict(pcdf_id=pcdf_data['subsidiary_type_index'])

    if pcdf_data['storage_type'] != "Unknown":
        # Shouldn't have cylinder data specified if we are going to use pcdf cylinder info
        # FIXME: this assert should be re-enabled, but causes a failure since some tests sites do have this data
        # assert dwelling.get("hw_cylinder_volume") is None
        logging.warning("Cylinder vol given even though using pcdf cylinder info")

    if pcdf_data['main_type'] == 'Regular':
        # TODO: Also need to allow this for table 4a systems?
        if dwelling.get('cylinder_is_thermal_store'):
            if dwelling.thermal_store_type == ThermalStoreTypes.HW_ONLY:
                sys.table2b_row = 6
            else:
                sys.table2b_row = 7
            dwelling.has_cylinderstat = True
        else:
            sys.table2b_row = 2  # !!! Assumes not electric

    elif pcdf_data['main_type'] == 'Combi':

        # TODO: introduce a type for storage types
        if pcdf_data['storage_type'] in ['storage combi with primary store', 'storage combi with secondary store']:
            # TODO: Should only do this if combi is the hw system
            #  - this check for having a defined ins type works for now, but will need improving

            if not dwelling.get('hw_cylinder_insulation_type'):
                dwelling.hw_cylinder_volume = pcdf_data["store_boiler_volume"]
                dwelling.hw_cylinder_insulation = pcdf_data["store_insulation_mms"]
                dwelling.hw_cylinder_insulation_type = CylinderInsulationTypes.FOAM

                # Force calc to use the data from pcdf, don't use a user entered cylinder loss
                dwelling.measured_cylinder_loss = None

        if pcdf_data['storage_type'] == 'storage combi with primary store':
            sys.table2b_row = 3
            dwelling.has_cylinderstat = True

        elif pcdf_data['storage_type'] == 'storage combi with secondary store':
            sys.table2b_row = 4
            dwelling.has_cylinderstat = True

        if 'keep_hot_facility' not in pcdf_data or pcdf_data['keep_hot_facility'] == 'None':
            sys.has_no_keep_hot = True
            sys.table3a_fn = combi_loss_instant_without_keep_hot

        elif pcdf_data['keep_hot_timer']:
            sys.table3a_fn = combi_loss_instant_with_timed_heat_hot
            if pcdf_data['keep_hot_facility'] == "elec" or pcdf_data['keep_hot_facility'] == "gas/oil and elec":
                # !!! or mixed?
                sys.keep_hot_elec_consumption = 600

        else:
            sys.table3a_fn = combi_loss_instant_with_untimed_heat_hot
            if pcdf_data['keep_hot_facility'] == "elec" or pcdf_data['keep_hot_facility'] == "gas/oil and elec":
                # TODO: or mixed?
                sys.keep_hot_elec_consumption = 900

    elif pcdf_data['main_type'] == 'CPSU':
        sys.table2b_row = 7  # !!! Assumes gas-fired
        dwelling.has_cylinderstat = True
        sys.cpsu_Tw = dwelling.cpsu_Tw
        sys.cpsu_not_in_airing_cupboard = dwelling.get('cpsu_not_in_airing_cupboard', False)

    else:
        # !!! What about other table rows?
        raise ValueError("Unknown system type")

    if sys.system_type == HeatingTypes.combi:
        appendix_g.configure_combi_loss(dwelling, sys, pcdf_data)
    # !!! Assumes gas/oil boiler
    sys.responsiveness = USE_TABLE_4D_FOR_RESPONSIVENESS
    return sys


def twin_burner_cooker_boiler_from_pcdf(pcdf_data, fuel,
                                        use_immersion_in_summer):
    winter_effy = pcdf_data['winter_effy']
    summer_effy = pcdf_data['summer_effy']

    sys = HeatingSystem(HeatingTypes.regular_boiler,  # !!!
                        winter_effy,
                        summer_effy,
                        summer_immersion=use_immersion_in_summer,
                        has_flue_fan=False,  # !!!
                        has_ch_pump=True,
                        table2b_row=2,  # !!! Solid fuel boilers can only have indirect boiler?
                        default_secondary_fraction=0.1,  # !!! Assumes 10% secondary fraction
                        fuel=fuel)

    sys.range_cooker_heat_required_scale_factor = 1 - (
        pcdf_data['case_loss_at_full_output'] / pcdf_data['full_output_power'])

    # !!! Assumes we have a heat emitter - is that always the case?
    sys.responsiveness = USE_TABLE_4D_FOR_RESPONSIVENESS

    # !!!
    sys.has_warm_air_fan = False
    return sys


def dhw_fuel_cost(dwelling):
    if dwelling.water_sys.fuel.is_electric and dwelling.get('immersion_type') is not None:
        # !!! Are there other places that should use non-solar cylinder volume?
        non_solar_cylinder_volume = dwelling.hw_cylinder_volume - (
            dwelling.solar_dedicated_storage_volume
            if dwelling.get('solar_dedicated_storage_volume')
            else 0)
        on_peak = immersion_on_peak_fraction(dwelling.Nocc,
                                             dwelling.electricity_tariff,
                                             non_solar_cylinder_volume,
                                             dwelling.immersion_type)
        return dwelling.water_sys.fuel.unit_price(on_peak)

    elif dwelling.water_sys.fuel.is_electric:
        on_peak = dhw_on_peak_fraction(dwelling.water_sys, dwelling)
        return dwelling.water_sys.fuel.unit_price(on_peak)

    else:
        return dwelling.water_sys.fuel.unit_price()


def dhw_on_peak_fraction(water_sys, dwelling):
    """
    Function equivalent to Table 12a, describing the fraction of district hot water on
    peak
    :param water_sys: type of hot water system
    :param dwelling:
    :return:
    """
    # !!! Need to complete this table
    if water_sys.system_type == HeatingTypes.cpsu:
        return appendix_f.cpsu_on_peak(water_sys, dwelling)
    elif water_sys.system_type == HeatingTypes.heat_pump:
        # !!! Need off-peak immersion option
        return .7
    elif water_sys.system_type in [HeatingTypes.pcdf_heat_pump,
                                   HeatingTypes.microchp]:
        return .7
    else:
        return water_sys.fuel.general_elec_on_peak_fraction


def immersion_on_peak_fraction(N_occ, elec_tariff, cylinder_volume, immersion_type):
    """

    :param N_occ: number of occupants
    :param elec_tariff:
    :param cylinder_volume:
    :param immersion_type:
    :return:
    """
    if elec_tariff == ELECTRICITY_7HR:
        if immersion_type == ImmersionTypes.SINGLE:
            return max(0, ((14530 - 762 * N_occ) / cylinder_volume - 80 + 10 * N_occ) / 100)
        else:
            assert immersion_type == ImmersionTypes.DUAL
            return max(0, ((6.8 - 0.024 * cylinder_volume) * N_occ + 14 - 0.07 * cylinder_volume) / 100)
    elif elec_tariff == ELECTRICITY_10HR:
        if immersion_type == ImmersionTypes.SINGLE:
            return max(0, ((14530 - 762 * N_occ) / (1.5 * cylinder_volume) - 80 + 10 * N_occ) / 100)
        else:
            assert immersion_type == ImmersionTypes.DUAL
            return max(0, ((6.8 - 0.036 * cylinder_volume) * N_occ + 14 - 0.105 * cylinder_volume) / 100)
    else:
        return 1


def sedbuk_2005_heating_system(fuel, sedbuk_2005_effy, range_case_loss, range_full_output, boiler_type,
                               fan_assisted_flue, use_immersion_heater_summer, hw_cylinder_volume=0,
                               cpsu_not_in_airing_cupboard=False):
    """

    Args:
        fuel:
        sedbuk_2005_effy: efficiency from the SEDBUK 2005 database
        range_case_loss:
        range_full_output:
        boiler_type:
        fan_assisted_flue:
        use_immersion_heater_summer:

    Returns:

    """
    modulating = True
    is_condensing = True

    if fuel.type == FuelTypes.GAS:
        d7_data = TABLE_D7[FuelTypes.GAS][(modulating, is_condensing, boiler_type)]
    else:
        d7_data = TABLE_D7[fuel.type][(is_condensing, boiler_type)]

    k1 = d7_data[0]
    k2 = d7_data[1]
    k3 = d7_data[2]
    f = 0.901  # !!! Assumes natural gas !!!

    nflnet = (sedbuk_2005_effy - k1) / f + k2
    nplnet = (sedbuk_2005_effy - k1) / f - k2

    if nflnet > 95.5:
        nflnet -= 0.673 * (nflnet - 95.5)
    if nplnet > 96.6:
        nplnet -= .213 * (nplnet - 96.6)

    # !!! Assumes gas
    if is_condensing:
        nflnet = min(98, nflnet)
        nplnet = min(108, nplnet)
    else:
        assert False  # !!!
        nflnet = min(92, nflnet)
        nplnet = min(91, nplnet)

    annual_effy = 0.5 * (nflnet + nplnet) * f + k3
    annual_effy = int(annual_effy * 10 + .5) / 10.
    return sedbuk_2009_heating_system(fuel, annual_effy, range_case_loss, range_full_output, boiler_type, is_condensing,
                                      fan_assisted_flue, use_immersion_heater_summer,
                                      hw_cylinder_volume,
                                      cpsu_not_in_airing_cupboard)


def sedbuk_2009_heating_system(fuel, sedbuk_2009_effy, range_case_loss, range_full_output, boiler_type, is_condensing,
                               fan_assisted_flue, use_immersion_heater_summer, hw_cylinder_volume=0,
                               cpsu_not_in_airing_cupboard=False):
    # !!! Assumes this boiler is also the HW sytstem!
    winter_offset, summer_offset = get_seasonal_effy_offset(
        True,  # !!!
        fuel,
        boiler_type)

    effy_winter = sedbuk_2009_effy + winter_offset
    effy_summer = sedbuk_2009_effy + summer_offset

    # !!! Don't include a flue fan for oil boilers (move to table 5 stuff?)
    has_flue_fan = fan_assisted_flue and fuel.type != FuelTypes.OIL

    # !!! Assumes either a regular boiler or storage combi
    if boiler_type == HeatingTypes.regular_boiler:
        table2b_row = 2
    elif boiler_type == HeatingTypes.storage_combi:
        table2b_row = 3
    elif boiler_type == HeatingTypes.cpsu:
        table2b_row = 7
    else:
        table2b_row = -1

    system = HeatingSystem(boiler_type,
                           effy_winter,
                           effy_summer,
                           use_immersion_heater_summer,
                           has_flue_fan,
                           True,  # CH pump
                           table2b_row,
                           .1,  # !!! 2ndary fraction
                           fuel)

    system.responsiveness = 1
    system.is_condensing = is_condensing
    if system.system_type in [HeatingTypes.combi,
                              HeatingTypes.storage_combi]:
        system.combi_loss = combi_loss_table_3a(hw_cylinder_volume, system)

    elif system.system_type == HeatingTypes.cpsu:
        # TODO: Might also need to set cpsu_Tw here?
        system.cpsu_not_in_airing_cupboard = cpsu_not_in_airing_cupboard

    if range_case_loss != None:
        system.range_cooker_heat_required_scale_factor = 1 - (
            range_case_loss / range_full_output)

    return system
