from . import worksheet
from .configure import lookup_sap_tables
from .dwelling import DwellingResults
from .elements import (OvershadingTypes,
                       HeatEmitters, VentilationTypes)
from .fuels import fuel_from_code


def run_sap(input_dwelling):
    """
    Run SAP on the input dwelling
    :param input_dwelling:
    :return:
    """
    # dwelling = DwellingResults(input_dwelling)
    dwelling = input_dwelling
    dwelling.reduced_gains = False

    lookup_sap_tables(dwelling)

    worksheet.perform_full_calc(dwelling)

    worksheet.sap(dwelling)

    input_dwelling.er_results = dwelling.results

    # dwelling.report.build_report()


def run_fee(input_dwelling):
    """
    Run Fabric Energy Efficiency FEE for dwelling

    :param input_dwelling:
    :return:
    """
    dwelling = DwellingResults(input_dwelling)
    dwelling.reduced_gains = True

    dwelling.cooled_area = input_dwelling.GFA
    dwelling.low_energy_bulb_ratio = 1
    dwelling.ventilation_type = VentilationTypes.NATURAL
    dwelling.water_heating_type_code = 907
    dwelling.fghrs = None

    if input_dwelling.GFA <= 70:
        dwelling.Nfansandpassivevents = 2
    elif input_dwelling.GFA <= 100:
        dwelling.Nfansandpassivevents = 3
    else:
        dwelling.Nfansandpassivevents = 4

    if dwelling.overshading == OvershadingTypes.VERY_LITTLE:
        dwelling.overshading = OvershadingTypes.AVERAGE

    dwelling.main_heating_pcdf_id = None
    dwelling.main_heating_type_code = 191
    dwelling.main_sys_fuel = fuel_from_code(1)
    dwelling.heating_emitter_type = HeatEmitters.RADIATORS
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

    lookup_sap_tables(dwelling)

    dwelling.pump_gain = 0
    dwelling.heating_system_pump_gain = 0

    worksheet.perform_demand_calc(dwelling)
    worksheet.fee(dwelling)
    dwelling.report.build_report()

    # Assign the results of the FEE calculation to the original dwelling, with a prefix...
    input_dwelling.fee_results = dwelling.results


def run_der(input_dwelling):
    """

    Args:
        input_dwelling:

    Returns:

    """
    dwelling = DwellingResults(input_dwelling)
    dwelling.reduced_gains = True

    if dwelling.overshading == OvershadingTypes.VERY_LITTLE:
        dwelling.overshading = OvershadingTypes.AVERAGE

    lookup_sap_tables(dwelling)

    worksheet.perform_full_calc(dwelling)
    worksheet.der(dwelling)

    dwelling.report.build_report()

    # Assign the results of the DER calculation to the original dwelling, with a prefix...
    input_dwelling.der_results = dwelling.results

    if (dwelling.main_sys_fuel.is_mains_gas or
            (dwelling.get('main_sys_2_fuel') and
                 dwelling.main_sys_2_fuel.is_mains_gas)):
        input_dwelling.ter_fuel = fuel_from_code(1)

    elif sum(dwelling.Q_main_1) >= sum(dwelling.Q_main_2):
        input_dwelling.ter_fuel = dwelling.main_sys_fuel

    else:
        input_dwelling.ter_fuel = dwelling.main_sys_2_fuel


