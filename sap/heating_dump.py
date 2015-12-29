from sap.appendix_f import appendix_f_cpsu_on_peak
from sap.fuels import ELECTRICITY_7HR, ELECTRICITY_10HR
from sap.sap_types import HeatingTypes, ImmersionTypes


def space_heat_on_peak_fraction(sys, dwelling):
    if sys.system_type == HeatingTypes.off_peak_only:
        return 0

    elif sys.system_type == HeatingTypes.integrated_system:
        assert sys.fuel == ELECTRICITY_7HR
        return .2

    elif sys.system_type == HeatingTypes.storage_heater:
        return 0

    elif sys.system_type == HeatingTypes.cpsu:
        return appendix_f_cpsu_on_peak(sys, dwelling)

    elif sys.system_type == HeatingTypes.electric_boiler:
        if sys.fuel == ELECTRICITY_7HR:
            return 0.9
        elif sys.fuel == ELECTRICITY_10HR:
            return .5
        else:
            return 1

    elif sys.system_type in [HeatingTypes.pcdf_heat_pump,
                             HeatingTypes.microchp]:
        return .8

    elif sys.system_type == HeatingTypes.heat_pump:
        return 0.6
    # !!! underfloor heating
    # !!! ground source heat pump
    # !!! air source heat pump
    # !!! other direct acting heating (incl secondary)
    else:
        if sys.fuel == ELECTRICITY_10HR:
            return .5
        else:
            return 1


def heating_fuel_cost(sys, dwelling):
    if sys.fuel.is_electric:
        on_peak = space_heat_on_peak_fraction(sys, dwelling)
        return sys.fuel.unit_price(on_peak)
    else:
        return sys.fuel.unit_price()


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
        return appendix_f_cpsu_on_peak(water_sys, dwelling)
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