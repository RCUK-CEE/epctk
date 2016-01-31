import math

import numpy

from .appendix import appendix_c, appendix_g
from .constants import DAYS_PER_MONTH, SUMMER_MONTHS
from .elements import HeatingTypes, DedicatedWaterSystem
from .tables import (TABLE_3, TABLE_4A, get_4a_system, MONTHLY_HOT_WATER_FACTORS, MONTHLY_HOT_WATER_TEMPERATURE_RISE,
                     TABLE_H5)
from .utils import SAPInputError


def get_water_heater(dwelling):
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
        water_sys = DedicatedWaterSystem(dwelling.water_sys_fuel,
                                         water_system['effy'],
                                         dwelling.get('use_immersion_heater_summer', False))
        water_sys.table2b_row = water_system['table2b_row']

    elif code == 901:  # from main
        if dwelling.main_sys_1 is None:
            raise RuntimeError("Main system 1 must not be None")
        water_sys = dwelling.main_sys_1

    elif code == 914:  # from second main
        water_sys = dwelling.main_sys_2

    elif code == 902:  # from secondary
        water_sys = dwelling.secondary_sys

    elif code == 950:  # community dhw only
        # TODO Community hot water based on sap defaults not handled
        water_sys = appendix_c.CommunityHeating(
            dwelling.community_heat_sources_dhw,
            dwelling.get('sap_community_distribution_type_dhw'))

        if dwelling.get('community_dhw_flat_rate_charging'):
            water_sys.dhw_charging_factor = 1.05

        else:
            water_sys.dhw_charging_factor = 1.0

        if dwelling.main_sys_1.system_type == HeatingTypes.community:
            # Standing charge already covered by main system
            water_sys.fuel.standing_charge = 0

        else:
            # Only half of standing charge applies for DHW only
            water_sys.fuel.standing_charge /= 2
    elif code == 999:  # no h/w system present - assume electric immersion
        return
    else:
        raise SAPInputError("No valid water system code given")

    # dwelling.water_sys = water_sys
    return water_sys


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
        utilisation *= 0.9

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


def distribution_storage_loss(dwelling, hw_energy_content):
    if dwelling.get('instantaneous_pou_water_heating'):
        distribution_loss = 0
        storage_loss = 0

    else:
        distribution_loss = 0.15 * hw_energy_content

        if dwelling.get('measured_cylinder_loss') is not None:
            storage_loss = dwelling.measured_cylinder_loss * \
                           dwelling.temperature_factor * DAYS_PER_MONTH

        elif dwelling.get('hw_cylinder_volume') is not None:
            cylinder_loss = dwelling.hw_cylinder_volume * dwelling.storage_loss_factor * \
                            dwelling.volume_factor * dwelling.temperature_factor
            storage_loss = cylinder_loss * DAYS_PER_MONTH

        else:
            storage_loss = 0

    return distribution_loss, storage_loss


def hot_water_from_solar(dwelling, hw_energy_content, savings_from_wwhrs, primary_circuit_loss_annual,
                         primary_circuit_loss):
    if dwelling.get('solar_collector_aperture') is not None:
        input_from_solar = solar_system_output(dwelling,
                                               hw_energy_content - savings_from_wwhrs,
                                               dwelling.daily_hot_water_use)

        if primary_circuit_loss_annual > 0 and dwelling.hw_cylinder_volume > 0 and dwelling.has_cylinderstat:
            primary_circuit_loss *= TABLE_H5
    else:
        input_from_solar = 0
    return input_from_solar


def hot_water_use(dwelling):
    """
    Calculate hot water use variables.

    .. todo::
        break function into smaller chunks. Could probably string together a series of .updates
        for each sub-section.

    Args:
        dwelling:

    Returns:

    """
    hot_water_use_variables = {}

    hw_use_daily = dwelling.daily_hot_water_use * MONTHLY_HOT_WATER_FACTORS

    hw_energy_content = (4.19 / 3600.0) * hw_use_daily * DAYS_PER_MONTH * MONTHLY_HOT_WATER_TEMPERATURE_RISE

    distribution_loss, storage_loss = distribution_storage_loss(dwelling, hw_energy_content)

    if dwelling.get("solar_storage_combined_cylinder"):
        storage_loss *= (dwelling.hw_cylinder_volume -
                         dwelling.solar_dedicated_storage_volume) / dwelling.hw_cylinder_volume

    if dwelling.get('primary_loss_override') is not None:
        primary_circuit_loss_annual = dwelling.primary_loss_override
    else:
        primary_circuit_loss_annual = dwelling.primary_circuit_loss_annual

    # This will produce an Array
    primary_circuit_loss = (primary_circuit_loss_annual / 365.0) * DAYS_PER_MONTH  # type: numpy.array

    if dwelling.get('combi_loss') is not None:
        combi_loss_monthly = dwelling.combi_loss(hw_use_daily) * DAYS_PER_MONTH / 365
    else:
        combi_loss_monthly = 0

    if dwelling.get('use_immersion_heater_summer', False):
        for i in SUMMER_MONTHS:
            primary_circuit_loss[i] = 0

    if dwelling.get('wwhr_systems') is not None:
        savings_from_wwhrs = appendix_g.wwhr_savings(dwelling)
    else:
        savings_from_wwhrs = 0

    input_from_solar = hot_water_from_solar(dwelling, hw_energy_content, savings_from_wwhrs,
                                            primary_circuit_loss_annual, primary_circuit_loss)

    if dwelling.get('fghrs') is not None and dwelling.fghrs['has_pv_module']:
        fghrs_input_from_solar = fghrs_solar_input(dwelling,
                                                   dwelling.fghrs,
                                                   hw_energy_content,
                                                   dwelling.daily_hot_water_use)
    else:
        fghrs_input_from_solar = 0

    total_water_heating = 0.85 * hw_energy_content + distribution_loss + \
                          storage_loss + primary_circuit_loss + \
                          combi_loss_monthly

    # Assumes the cylinder is in the heated space if input is missing
    # i.e default value is True if missing
    if dwelling.get('cylinder_in_heated_space', True):
        heat_gains_from_hw = 0.25 * (0.85 * hw_energy_content + combi_loss_monthly) + 0.8 * (
            distribution_loss + primary_circuit_loss)
    else:
        heat_gains_from_hw = 0.25 * (0.85 * hw_energy_content + combi_loss_monthly) + 0.8 * (
            distribution_loss + storage_loss + primary_circuit_loss)

        heat_gains_from_hw = numpy.maximum(0, heat_gains_from_hw)

    return dict(
        hw_use_daily=hw_use_daily,
        hw_energy_content=hw_energy_content,
        total_water_heating=total_water_heating,
        storage_loss=storage_loss,
        distribution_loss=distribution_loss,
        primary_circuit_loss=primary_circuit_loss,
        combi_loss_monthly=combi_loss_monthly,
        heat_gains_from_hw=heat_gains_from_hw,
        input_from_solar=input_from_solar,
        fghrs_input_from_solar=fghrs_input_from_solar,
        savings_from_wwhrs=savings_from_wwhrs
    )


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


def get_table3_row(dwelling):
    """
    Get the row number from Table 3 for the given dwelling
    by finding the row corresponding to the dwellings' combination of heating
    type codes and thermal storage.

    This implements the logic of section 4.2 Storage loss, and is used through the
    hw_primary_circuit_loss function

    Args:
        dwelling (Dwelling):

    Returns:
        Table 3 row corresponding to this dwelling properties
    """
    if dwelling.water_heating_type_code == 901:
        # !!! Also need to do this for second main system?

        # Water heating with main
        if dwelling.main_sys_1.system_type == HeatingTypes.cpsu:
            return 7
        if (dwelling.get('main_heating_type_code') and
                    dwelling.main_heating_type_code == 191):
            return 1

    if dwelling.water_sys.system_type in [HeatingTypes.combi,
                                          HeatingTypes.storage_combi]:
        return 6

    elif dwelling.water_heating_type_code == 903:
        # Immersion
        return 1

    elif dwelling.community_heating_dhw:
        # Community heating
        return 12

    elif dwelling.get('cylinder_is_thermal_store'):
        # !!! Need to check length of pipework here and insulation
        return 10

    elif (dwelling.water_sys.system_type in [HeatingTypes.pcdf_heat_pump,
                                             HeatingTypes.microchp]
          and dwelling.water_sys.has_integral_store):
        return 8

    elif dwelling.has_hw_cylinder:
        # Cylinder !!! Cylinderstat should be assumed to be present
        # for CPSU, electric immersion, etc - see 9.3.7
        if dwelling.has_cylinderstat and dwelling.primary_pipework_insulated:
            return 5
        elif dwelling.has_cylinderstat or dwelling.primary_pipework_insulated:
            return 3  # row 4 is the same
        else:
            return 2

    else:
        # Must be combi?
        raise Exception("Must be combi?")
        # return 6


def hw_primary_circuit_loss(dwelling):
    """
    Hot water primary circuit losses according to the logic described in
    Section 4.2.

    :param dwelling:
    :return:
    """
    table3row = get_table3_row(dwelling)
    return TABLE_3[table3row]
