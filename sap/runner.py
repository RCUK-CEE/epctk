from . import worksheet
from .configure import lookup_sap_tables
from .dwelling import DwellingResults
from .fuels import fuel_from_code
from .sap_types import (CylinderInsulationTypes, GlazingTypes, OvershadingTypes,
                        HeatEmitters, VentilationTypes, HeatLossElementTypes,
                        HeatLossElement, OpeningType, Opening)


def element_type_area(etype, els):
    return sum(e.area for e in els if e.element_type == etype)


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


def run_ter(input_dwelling):
    """
    Run the Target Energy Rating (TER) for the input dwelling.

    Args:
        input_dwelling:

    Returns:
          COPY of the dwelling with the TER results
          Assigns the .results to the input_dwelling.ter_results

    """
    # Note this previously wrapped dwelling in Dwelling Wrapper
    dwelling = DwellingResults(input_dwelling)

    dwelling.reduced_gains = True

    net_wall_area = element_type_area(HeatLossElementTypes.EXTERNAL_WALL,
                                      dwelling.heat_loss_elements)

    opaque_door_area = element_type_area(HeatLossElementTypes.OPAQUE_DOOR,
                                         dwelling.heat_loss_elements)

    window_area = sum(o.area for o in dwelling.openings if o.opening_type.roof_window is False)
    roof_window_area = sum(o.area for o in dwelling.openings if o.opening_type.roof_window is True)
    gross_wall_area = net_wall_area + window_area + opaque_door_area

    new_opening_area = min(dwelling.GFA * .25, gross_wall_area)
    new_window_area = max(new_opening_area - 1.85, 0)

    floor_area = element_type_area(HeatLossElementTypes.EXTERNAL_FLOOR,
                                   dwelling.heat_loss_elements)
    net_roof_area = element_type_area(HeatLossElementTypes.EXTERNAL_ROOF,
                                      dwelling.heat_loss_elements)
    roof_area = net_roof_area + roof_window_area

    heat_loss_elements = [
        HeatLossElement(
            area=gross_wall_area - new_window_area - 1.85,
            Uvalue=.35,
            is_external=True,
            element_type=HeatLossElementTypes.EXTERNAL_WALL
        ),
        HeatLossElement(
            area=1.85,
            Uvalue=2,
            is_external=True,
            element_type=HeatLossElementTypes.OPAQUE_DOOR
        ),
        HeatLossElement(
            area=floor_area,
            Uvalue=.25,
            is_external=True,
            element_type=HeatLossElementTypes.EXTERNAL_FLOOR
        ),
        HeatLossElement(
            area=roof_area,
            Uvalue=.16,
            is_external=True,
            element_type=HeatLossElementTypes.EXTERNAL_ROOF
        ),
        HeatLossElement(
            area=new_window_area,
            Uvalue=1. / (1. / 2 + .04),
            is_external=True,
            element_type=HeatLossElementTypes.GLAZING)
    ]

    dwelling.heat_loss_elements = heat_loss_elements

    ter_opening_type = OpeningType(
            glazing_type=GlazingTypes.DOUBLE,
            gvalue=.72,
            frame_factor=0.7,
            Uvalue=2,
            roof_window=False)

    new_openings = [Opening(
            area=new_window_area,
            orientation_degrees=90,
            opening_type=ter_opening_type)
    ]

    dwelling.openings = new_openings

    dwelling.thermal_mass_parameter = 250
    dwelling.overshading = OvershadingTypes.AVERAGE

    dwelling.Nshelteredsides = 2
    dwelling.Uthermalbridges = .11
    dwelling.ventilation_type = VentilationTypes.NATURAL
    dwelling.pressurisation_test_result = 10
    dwelling.Nchimneys = 0
    dwelling.Nflues = 0

    if input_dwelling.GFA > 80:
        dwelling.Nfansandpassivevents = 3
    else:
        dwelling.Nfansandpassivevents = 2

    dwelling.main_heating_type_code = 102
    dwelling.main_heating_pcdf_id = None
    dwelling.heating_emitter_type = HeatEmitters.RADIATORS
    dwelling.heating_emitter_type2 = None
    dwelling.main_heating_fraction = 1
    dwelling.main_heating_2_fraction = 0
    dwelling.main_sys_fuel = fuel_from_code(1)
    dwelling.main_heating_oil_pump_inside_dwelling = None
    dwelling.main_heating_2_oil_pump_inside_dwelling = None
    dwelling.control_type_code = 2106
    dwelling.sys1_has_boiler_interlock = True
    dwelling.sys1_load_compensator = None
    dwelling.central_heating_pump_in_heated_space = True
    dwelling.appendix_q_systems = None

    dwelling.has_hw_time_control = True
    dwelling.water_heating_type_code = 901
    dwelling.use_immersion_heater_summer = False
    dwelling.has_hw_cylinder = True
    dwelling.hw_cylinder_volume = 150
    dwelling.cylinder_in_heated_space = True
    dwelling.hw_cylinder_insulation_type = CylinderInsulationTypes.FOAM
    dwelling.hw_cylinder_insulation = 35
    dwelling.primary_pipework_insulated = False
    dwelling.has_cylinderstat = True
    dwelling.hwsys_has_boiler_interlock = True
    dwelling.measured_cylinder_loss = None
    dwelling.solar_collector_aperture = None
    dwelling.has_electric_shw_pump = False
    dwelling.solar_storage_combined_cylinder = False
    dwelling.wwhr_systems = None
    dwelling.fghrs = None
    dwelling.cylinder_is_thermal_store = False
    dwelling.thermal_store_type = None
    dwelling.sys1_sedbuk_2005_effy = None
    dwelling.sys1_sedbuk_2009_effy = None

    dwelling.sys1_delayed_start_thermostat = False

    dwelling.low_water_use = False
    dwelling.secondary_sys_fuel = dwelling.electricity_tariff
    dwelling.secondary_heating_type_code = 691
    dwelling.secondary_hetas_approved = False
    dwelling.low_energy_bulb_ratio = .3

    dwelling.cooled_area = 0

    # Need to make sure no summer immersion and no renewables 

    lookup_sap_tables(dwelling)

    dwelling.main_sys_1.heating_effy_winter = 78 + .9
    dwelling.main_sys_1.heating_effy_summer = 78 - 9.2

    worksheet.perform_full_calc(dwelling)

    worksheet.ter(dwelling, input_dwelling.ter_fuel)

    dwelling.report.build_report()

    # Assign the TER results to the original dwelling
    input_dwelling.ter_results = dwelling.results
    return input_dwelling


