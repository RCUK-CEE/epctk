import math

import numpy

from sap.appendix import appendix_c, appendix_g
from sap.constants import DAYS_PER_MONTH, SUMMER_MONTHS
from sap.heating_system_types import DedicatedWaterSystem
from sap.sap_types import HeatingTypes
from sap.tables import TABLE_4A, get_4a_system, MONTHLY_HOT_WATER_FACTORS, MONTHLY_HOT_WATER_TEMPERATURE_RISE, TABLE_H5


def configure_water_system(dwelling):
    """
    Configure the domestic hot water heating system

    Args:
        dwelling:

    Returns:

    """
    # if dwelling.get('water_heating_type_code'):  # !!! Why this test?
    code = dwelling.water_heating_type_code

    if code in TABLE_4A:
        water_system = get_4a_system(dwelling.electricity_tariff, code)
        dwelling.water_sys = DedicatedWaterSystem(water_system['effy'],
                                                  dwelling.use_immersion_heater_summer if dwelling.get(
                                                          'use_immersion_heater_summer') else False)
        dwelling.water_sys.table2b_row = water_system['table2b_row']
        dwelling.water_sys.fuel = dwelling.water_sys_fuel

    elif code == 999:  # no h/w system present - assume electric immersion
        pass

    elif code == 901:  # from main
        if dwelling.main_sys_1 is None:
            raise RuntimeError("Main system 1 must not be None")
        dwelling.water_sys = dwelling.main_sys_1

    elif code == 902:  # from secondary
        dwelling.water_sys = dwelling.secondary_sys

    elif code == 914:  # from second main
        dwelling.water_sys = dwelling.main_sys_2

    elif code == 950:  # community dhw only
        # TODO Community hot water based on sap defaults not handled
        dwelling.water_sys = appendix_c.CommunityHeating(
                dwelling.community_heat_sources_dhw,
                dwelling.get('sap_community_distribution_type_dhw'))

        if dwelling.get('community_dhw_flat_rate_charging'):
            dwelling.water_sys.dhw_charging_factor = 1.05

        else:
            dwelling.water_sys.dhw_charging_factor = 1.0

        if dwelling.main_sys_1.system_type == HeatingTypes.community:
            # Standing charge already covered by main system
            dwelling.water_sys.fuel.standing_charge = 0

        else:
            # Only half of standing charge applies for DHW only
            dwelling.water_sys.fuel.standing_charge /= 2
    else:
        assert False


def solar_system_output(dwelling, hw_energy_content, daily_hot_water_use):
    """
    Calculate the solar system output as a function of the dwelling data, the
    hot water energy content and daily hot water usage

    Args:
        dwelling:
        hw_energy_content:
        daily_hot_water_use:

    Returns:

    """
    performance_ratio = dwelling.collector_heat_loss_coeff / dwelling.collector_zero_loss_effy

    annual_radiation = dwelling.collector_Igh

    overshading_factor = dwelling.collector_overshading_factor
    available_energy = dwelling.solar_collector_aperture * dwelling.collector_zero_loss_effy
    available_energy *= annual_radiation * overshading_factor

    solar_to_load = available_energy / sum(hw_energy_content)
    utilisation = 1 - math.exp(-1 / solar_to_load)

    if dwelling.water_sys.system_type in [
        HeatingTypes.regular_boiler,
        HeatingTypes.room_heater,  # must be back boiler
    ] and not dwelling.has_cylinderstat:
        utilisation *= .9

    if performance_ratio < 20:
        performance_factor = 0.97 - 0.0367 * performance_ratio + 0.0006 * performance_ratio ** 2
    else:
        performance_factor = 0.693 - 0.0108 * performance_ratio

    effective_solar_volume = dwelling.solar_effective_storage_volume

    volume_ratio = effective_solar_volume / daily_hot_water_use

    storage_volume_factor = numpy.minimum(1., 1 + 0.2 * numpy.log(volume_ratio))

    Qsolar_annual = available_energy * utilisation * performance_factor * storage_volume_factor

    Qsolar = - Qsolar_annual * dwelling.monthly_solar_hw_factors * DAYS_PER_MONTH / 365

    return Qsolar


def hot_water_use(dwelling):
    """
    Calculate the dwelling hot water use, assign the result as
    attribute on dwelling

    :param dwelling:
    :return:
    """
    dwelling.hw_use_daily = dwelling.daily_hot_water_use * MONTHLY_HOT_WATER_FACTORS

    dwelling.hw_energy_content = (4.19 / 3600.) * dwelling.hw_use_daily * \
                                 DAYS_PER_MONTH * MONTHLY_HOT_WATER_TEMPERATURE_RISE

    if dwelling.get('instantaneous_pou_water_heating'):
        dwelling.distribution_loss = 0
        dwelling.storage_loss = 0

    else:
        dwelling.distribution_loss = 0.15 * dwelling.hw_energy_content

        if dwelling.get('measured_cylinder_loss') is not None:
            dwelling.storage_loss = dwelling.measured_cylinder_loss * \
                                    dwelling.temperature_factor * DAYS_PER_MONTH

        elif dwelling.get('hw_cylinder_volume') is not None:
            cylinder_loss = dwelling.hw_cylinder_volume * dwelling.storage_loss_factor * \
                            dwelling.volume_factor * dwelling.temperature_factor
            dwelling.storage_loss = cylinder_loss * DAYS_PER_MONTH

        else:
            dwelling.storage_loss = 0

    if dwelling.get("solar_storage_combined_cylinder"):
        dwelling.storage_loss *= (dwelling.hw_cylinder_volume -
                                  dwelling.solar_dedicated_storage_volume) / dwelling.hw_cylinder_volume

    if dwelling.get('primary_loss_override') is not None:
        primary_circuit_loss_annual = dwelling.primary_loss_override
    else:
        primary_circuit_loss_annual = dwelling.primary_circuit_loss_annual

    # This will produce and array Array
    dwelling.primary_circuit_loss = (primary_circuit_loss_annual / 365.0) * DAYS_PER_MONTH  # type: numpy.array

    if dwelling.get('combi_loss') is not None:
        dwelling.combi_loss_monthly = dwelling.combi_loss(dwelling.hw_use_daily) * DAYS_PER_MONTH / 365
    else:
        dwelling.combi_loss_monthly = 0

    if dwelling.get('use_immersion_heater_summer', False):
        for i in SUMMER_MONTHS:
            dwelling.primary_circuit_loss[i] = 0

    if dwelling.get('wwhr_systems') is not None:
        dwelling.savings_from_wwhrs = appendix_g.wwhr_savings(dwelling)
    else:
        dwelling.savings_from_wwhrs = 0

    if dwelling.get('solar_collector_aperture') is not None:
        dwelling.input_from_solar = solar_system_output(dwelling,
                                                        dwelling.hw_energy_content - dwelling.savings_from_wwhrs,
                                                        dwelling.daily_hot_water_use)

        if primary_circuit_loss_annual > 0 and dwelling.hw_cylinder_volume > 0 and dwelling.has_cylinderstat:
            dwelling.primary_circuit_loss *= TABLE_H5
    else:
        dwelling.input_from_solar = 0

    if dwelling.get('fghrs') is not None and dwelling.fghrs['has_pv_module']:
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
    # i.e default value is True if missing
    if dwelling.get('cylinder_in_heated_space', True):
        dwelling.heat_gains_from_hw = 0.25 * (0.85 * dwelling.hw_energy_content + dwelling.combi_loss_monthly) + 0.8 * (
            dwelling.distribution_loss + dwelling.primary_circuit_loss)
    else:
        dwelling.heat_gains_from_hw = 0.25 * (0.85 * dwelling.hw_energy_content + dwelling.combi_loss_monthly) + 0.8 * (
            dwelling.distribution_loss + dwelling.storage_loss + dwelling.primary_circuit_loss)
    dwelling.heat_gains_from_hw = numpy.maximum(0, dwelling.heat_gains_from_hw)


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