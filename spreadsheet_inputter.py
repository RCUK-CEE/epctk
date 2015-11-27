import logging

import win32com.client

from output_checker import check_monthly_result
from output_checker import check_result
from output_checker import check_summer_monthly_result
from sap import runner
from sap import worksheet, input_conversion_rules
from sap.dwelling import Dwelling
from sap.pcdf import VentilationTypes
from sap.sap_tables import GlazingTypes
from tests import reference_case_parser


class CannotDoInSpreadsheetError(RuntimeError):
    pass


WORKBOOK_NAME = "ExcelSAP 1a  & 1b.xlsm"
INPUT_SHEET = "sap_inputs2009"
OUTPUT_SHEET = "sap_current_dwelling_results"
WORKSHEET = "sap_worksheet2009"

TEST_CASES = [
    "EW-1a-detached.rtf",  # manufacturer's data
    "EW-1b-detached with semi-exposed elements.rtf",  # manufacturer's data
    "EW-1c-detached.rtf",
    "EW-1d-detached.rtf",
    "EW-1e-detached.rtf",
    "EW-1f-detached.rtf",
    "EW-1g-detached.rtf",
    "EW-1h-detached.rtf",
    "EW-1i-detached.rtf",
    "EW-1j-detached.rtf",
    "EW-1k-detached.rtf",
    "EW-1L-detached.rtf",
    "EW-1m-detached.rtf",
    "EW-1n-detached.rtf",
    "EW-1p-detached.rtf",  # solar hot water, manuf data for secondary heating

]

# TEST_CASES=official_reference_cases.OFFICIAL_CASES_THAT_WORK

INPUTS = [
    #"electricity_tariff",
    "lighting_outlets_low_energy",
    "lighting_outlets_total",
    "low_water_use",
    "GFA",
    "Nstoreys",
    "volume",
    "living_area",
    "Nintermittentfans",
    "Npassivestacks",
    "Nchimneys",
    "Nshelteredsides",
    "Nflues",
    #"sap_region",
]

GLAZING_TYPES = {
    GlazingTypes.SINGLE: "Single",
    GlazingTypes.DOUBLE: "Double",
    GlazingTypes.TRIPLE: "Triple",
    GlazingTypes.SECONDARY: "Secondary",
}

ELEMENT_TYPES = {
    worksheet.HeatLossElementTypes.EXTERNAL_WALL: "External wall",
    worksheet.HeatLossElementTypes.PARTY_WALL: "Party wall",
    worksheet.HeatLossElementTypes.EXTERNAL_FLOOR: "Ground floor",
    worksheet.HeatLossElementTypes.EXTERNAL_ROOF: "Roof",
    worksheet.HeatLossElementTypes.OPAQUE_DOOR: "Opaque door",
}


class XLInputSheetModel(object):
    def __init__(self):
        self.xl = win32com.client.gencache.EnsureDispatch("Excel.Application")
        self.wb = self.xl.Workbooks(WORKBOOK_NAME)
        self.in_sheet = self.wb.Worksheets(INPUT_SHEET)
        self.out_sheet = self.wb.Worksheets(OUTPUT_SHEET)
        self.worksheet = self.wb.Worksheets(WORKSHEET)

    def set_calc_type(self, type):
        self.set_input("calculation_type", type)

    def set_input(self, name, value):
        self.in_sheet.Range("in_%s" % (name,)).Value = value

    def max_opaque_elements(self):
        return len(self.in_sheet.Range("in_heat_loss_elements"))

    def set_opaque_element(self,
                           idx,
                           heat_loss_element,
                           thermal_mass_element):
        names = self.in_sheet.Range("in_heat_loss_elements")
        areas = self.in_sheet.Range("in_heat_loss_elements_area")
        Uvalues = self.in_sheet.Range("in_heat_loss_elements_uvalue")
        kvalues = self.in_sheet.Range("in_heat_loss_elements_kvalue")
        is_external = self.in_sheet.Range("in_heat_loss_elements_is_external")
        types = self.in_sheet.Range("in_heat_loss_elements_element_type")

        if idx >= len(names):
            raise RuntimeError("Too many opaque elements to fit in spreadsheet")

        if heat_loss_element is None:
            names[idx].Value = "not used"
            areas[idx].Value = ""
            Uvalues[idx].Value = ""
            is_external[idx].Value = ""
            types[idx].Value = ""
        else:
            names[idx].Value = heat_loss_element.name
            areas[idx].Value = heat_loss_element.area
            Uvalues[idx].Value = heat_loss_element.Uvalue
            is_external[idx].Value = heat_loss_element.is_external
            types[idx].Value = ELEMENT_TYPES[heat_loss_element.element_type]

        if thermal_mass_element is None:
            kvalues[idx].Value = ""
        else:
            kvalues[idx].Value = thermal_mass_element.kvalue

    def max_internal_mass_elements(self):
        return len(self.in_sheet.Range("in_mass_only_elements"))

    def set_internal_mass_element(self,
                                  idx,
                                  thermal_mass_element):
        names = self.in_sheet.Range("in_mass_only_elements")
        areas = self.in_sheet.Range("in_mass_only_elements_area")
        kvalues = self.in_sheet.Range("in_mass_only_elements_kvalue")

        if idx >= len(names):
            raise CannotDoInSpreadsheetError("Too many internal mass elements")

        if thermal_mass_element is None:
            names[idx].Value = "not used"
            areas[idx].Value = ""
            kvalues[idx].Value = ""
        else:
            names[idx].Value = thermal_mass_element.name
            areas[idx].Value = thermal_mass_element.area
            kvalues[idx].Value = thermal_mass_element.kvalue

    def max_glazing_elements(self):
        return len(self.in_sheet.Range("in_glazing_elements"))

    def set_glazing_element(self, idx, glazing_element):
        names = self.in_sheet.Range("in_glazing_elements")
        areas = self.in_sheet.Range("in_glazing_elements_area")
        orientations = self.in_sheet.Range("in_glazing_elements_orientation")
        gvalues = self.in_sheet.Range("in_glazing_elements_gvalue")
        uvalues = self.in_sheet.Range("in_glazing_elements_uvalue")
        frame_factors = self.in_sheet.Range("in_glazing_elements_frame_factor")
        glazing_types = self.in_sheet.Range("in_glazing_elements_type")

        if idx >= len(names):
            raise CannotDoInSpreadsheetError("Too many glazed elements")

        if glazing_element is None:
            names[idx].Value = "not used"
            areas[idx].Value = 0
            orientations[idx].Value = 0
            gvalues[idx].Value = 0
            uvalues[idx].Value = 0
            frame_factors[idx].Value = 0
            glazing_types[idx].Value = ""
        else:
            names[idx].Value = glazing_element.name
            areas[idx].Value = glazing_element.area
            orientations[idx].Value = glazing_element.orientation_degrees
            gvalues[idx].Value = glazing_element.type.gvalue
            uvalues[idx].Value = 1 / (1 / glazing_element.type.Uvalue - 0.04)
            frame_factors[idx].Value = glazing_element.type.frame_factor
            glazing_types[idx].Value = GLAZING_TYPES[glazing_element.type.glazing_type]

    def set_roof_window(self, glazing_element):
        if glazing_element is None:
            self.set_input("roof_window_area", 0)
            self.set_input("roof_window_orientation", "")
            self.set_input("roof_window_gvalue", "")
            self.set_input("roof_window_uvalue", "")
            self.set_input("roof_window_frame_factor", "")
            self.set_input("roof_window_type", "")
        else:
            self.set_input("roof_window_area",
                           glazing_element.area)
            self.set_input("roof_window_orientation",
                           glazing_element.orientation_degrees)
            self.set_input("roof_window_gvalue",
                           glazing_element.type.gvalue)
            self.set_input("roof_window_uvalue",
                           1 / (1 / glazing_element.type.Uvalue - 0.04))
            self.set_input("roof_window_frame_factor",
                           glazing_element.type.frame_factor)
            self.set_input("roof_window_type",
                           GLAZING_TYPES[glazing_element.type.glazing_type])

    def monthly_property(name):
        @property
        def propfunc(self):
            return self.worksheet.Range(name).Value[0]

        return propfunc

    def single_value_property(name):
        @property
        def propfunc(self):
            return self.worksheet.Range(name).Value

        return propfunc

    @property
    def der(self):
        return self.out_sheet.Range("out_der").Value

    @property
    def ter(self):
        return self.out_sheet.Range("out_ter").Value

    @property
    def fee(self):
        return self.out_sheet.Range("out_fee").Value

    @property
    def sap(self):
        return self.out_sheet.Range("out_sap").Value

    thermal_mass_parameter = single_value_property("sap_tmp")
    heating_responsiveness = single_value_property("sap_responsiveness")
    heating_control_type = single_value_property("sap_control_type")

    space_main_heating_emissions = single_value_property("sap_emissions_space_primary")
    space_secondary_heating_emissions = single_value_property("sap_emissions_space_secondary")
    water_heating_emissions = single_value_property("sap_emissions_water_heat")
    water_heating_emissions_summer_immersion = single_value_property("sap_emissions_water_heat_summer_immersion")
    pump_emissions = single_value_property("sap_emissions_fans_pumps")
    lighting_emissions = single_value_property("sap_emissions_lighting")
    cooling_emissions = single_value_property("sap_emissions_cooling")

    h = monthly_property("sap_h")
    hw_heat_gain = monthly_property("sap_hw_heat_gain")
    solar_gain_winter = monthly_property("sap_Q_sol_winter")
    solar_gain_summer = monthly_property("sap_Q_sol_summer")
    full_light_gain = monthly_property("sap_lighting_gains")
    winter_heat_gains = monthly_property("sap_total_gain_winter")
    summer_heat_gains = monthly_property("sap_total_gain_summer")
    Tliving = monthly_property("sap_Tliving")
    Tother = monthly_property("sap_Tother")
    Tmean = monthly_property("sap_Tmean")
    Q_required = monthly_property("sap_Q_required")


def get_thermal_mass_element(d, heat_loss_element):
    return get_named_element(d.thermal_mass_elements, heat_loss_element.name)


def get_heat_loss_element(d, thermal_mass_element):
    return get_named_element(d.heat_loss_elements, thermal_mass_element.name)


def get_named_element(els, name):
    candidates = [el for el in els if el.name == name]
    assert len(candidates) <= 1
    return candidates[0] if len(candidates) == 1 else None


def process_envelope_elements(xlbook, d):
    process_solid_elements(xlbook, d)
    process_internal_elements(xlbook, d)
    process_glazing_elements(xlbook, d)

    if hasattr(d, "Uthermalbridges"):
        xlbook.set_input("Uthermalbridges", d.Uthermalbridges)
    else:
        h_bridging = sum(x['length'] * x['y'] for x in d.y_values)
        A_bridging = sum(e.area for e in d.heat_loss_elements if e.is_external)
        xlbook.set_input("Uthermalbridges", h_bridging / A_bridging)


def process_solid_elements(xlbook, d):
    doors = [el for el in d.heat_loss_elements if el.element_type == worksheet.HeatLossElementTypes.OPAQUE_DOOR]
    assert len(doors) == 1

    xlbook.set_opaque_element(
        0,
        doors[0],
        get_thermal_mass_element(d, doors[0]))

    idx = 1

    for el in [el for el in d.heat_loss_elements if not el.element_type in [
        worksheet.HeatLossElementTypes.OPAQUE_DOOR,
        worksheet.HeatLossElementTypes.GLAZING,
    ]]:
        xlbook.set_opaque_element(
            idx,
            el,
            get_thermal_mass_element(d, el))
        idx += 1

    while idx < xlbook.max_opaque_elements():
        xlbook.set_opaque_element(idx, None, None)
        idx += 1

    if hasattr(d, "thermal_mass_parameter"):
        xlbook.set_input("use_fixed_thermal_mass", True)
        xlbook.set_input("thermal_mass_parameter",
                         d.thermal_mass_parameter)
    else:
        xlbook.set_input("use_fixed_thermal_mass", False)
        xlbook.set_input("thermal_mass_parameter", "")


def process_internal_elements(xlbook, d):
    idx = 0
    for el in d.thermal_mass_elements:
        if get_heat_loss_element(d, el) == None:
            # thermal mass only element - must be internal surface
            xlbook.set_internal_mass_element(idx, el)
            idx += 1
    while idx < xlbook.max_internal_mass_elements():
        xlbook.set_internal_mass_element(idx, None)
        idx += 1


def process_glazing_elements(xlbook, d):
    idx = 0
    for el in (o for o in d.openings if not o.type.roof_window):
        xlbook.set_glazing_element(idx, el)
        idx += 1

    while idx < xlbook.max_glazing_elements():
        xlbook.set_glazing_element(idx, None)
        idx += 1

    roof_windows = [o for o in d.openings if o.type.roof_window]
    if len(roof_windows) == 1:
        xlbook.set_roof_window(roof_windows[0])
    elif len(roof_windows) == 0:
        xlbook.set_roof_window(None)
    else:
        rtype = roof_windows[0].type
        for rw in roof_windows:
            if not rw.type is rtype:
                raise CannotDoInSpreadsheetError("More than one roof window type")
            if not roof_windows[0].orientation_degrees == rw.orientation_degrees:
                raise CannotDoInSpreadsheetError("More than one roof window orientation")

        combined_window = worksheet.Opening(
            sum(rw.area for rw in roof_windows),
            roof_windows[0].orientation_degrees,
            rtype)
        xlbook.set_roof_window(combined_window)


IMMERSION_TYPES = {
    tables.ImmersionTypes.DUAL: "Dual",
    tables.ImmersionTypes.SINGLE: "Single",
}


def process_hw(xlbook, d: Dwelling):
    xlbook.set_input("water_heating_type_code", d.water_heating_type_code)
    if hasattr(d, "use_immersion_heater_summer"):
        xlbook.set_input("use_immersion_heater_summer", d.use_immersion_heater_summer)
    else:
        xlbook.set_input("use_immersion_heater_summer", False)

    if hasattr(d, "immersion_type"):
        xlbook.set_input("immersion_type", IMMERSION_TYPES[d.immersion_type])
    else:
        xlbook.set_input("immersion_type", "")

    if hasattr(d, "water_sys_fuel") and not d.water_sys_fuel is None:
        if d.water_sys_fuel.is_electric:
            xlbook.set_input("water_sys_fuel", "Electric")
        else:
            xlbook.set_input("water_sys_fuel", d.water_sys_fuel.name)
    else:
        xlbook.set_input("water_sys_fuel", "")

    xlbook.set_input("has_hw_time_control",
                     true_and_not_missing(d, "has_hw_time_control"))
    xlbook.set_input("has_cylinderstat",
                     true_and_not_missing(d, "has_cylinderstat"))
    xlbook.set_input("primary_pipework_insulated",
                     true_and_not_missing(d, "primary_pipework_insulated"))

    if not hasattr(d, "hw_cylinder_volume") or d.hw_cylinder_volume == 0:
        xlbook.set_input("cylinder_in_heated_space", "")
        xlbook.set_input("use_measured_cylinder_loss", True)
        xlbook.set_input("measured_cylinder_loss", "")
        xlbook.set_input("hw_cylinder_volume", "")
        xlbook.set_input("hw_cylinder_insulation", "")
        xlbook.set_input("hw_cylinder_insulation_type", "")
    else:
        if hasattr(d, 'cylinder_in_heated_space'):
            xlbook.set_input("cylinder_in_heated_space",
                             d.cylinder_in_heated_space)
        else:
            xlbook.set_input("cylinder_in_heated_space", True)

        if hasattr(d, 'measured_cylinder_loss'):
            xlbook.set_input("use_measured_cylinder_loss", True)
            xlbook.set_input("measured_cylinder_loss", d.measured_cylinder_loss)
            xlbook.set_input("hw_cylinder_volume", d.hw_cylinder_volume)
            xlbook.set_input("hw_cylinder_insulation", "")
            xlbook.set_input("hw_cylinder_insulation_type", "")
        else:
            xlbook.set_input("use_measured_cylinder_loss", False)
            xlbook.set_input("measured_cylinder_loss", "")
            xlbook.set_input("hw_cylinder_volume", d.hw_cylinder_volume)
            xlbook.set_input("hw_cylinder_insulation", d.hw_cylinder_insulation)
            xlbook.set_input("hw_cylinder_insulation_type",
                             "Factory Fitted" if d.hw_cylinder_insulation_type == CylinderInsulationTypes.FOAM else "Loose Jacket")

    if hasattr(d, "solar_collector_aperture") and d.solar_collector_aperture > 0:
        write_solar_hw(xlbook, d)
    else:
        clear_solar_hw(xlbook, d)


ORIENTATIONS = {
    45: "North-east",
    180: "South",
    225: "South-west",
}
PITCH = {
    "Horizontal": 0,
    30: 30,
    45: 45,
    60: 60,
}
OVERSHADING = {
    tables.PVOvershading.HEAVY: 'Heavy',
    tables.PVOvershading.SIGNIFICANT: 'Significant',
    tables.PVOvershading.MODEST: 'Modest',
    tables.PVOvershading.NONE_OR_VERY_LITTLE: 'None or very little',
}
COLLECTOR_TYPES = {
    tables.SHWCollectorTypes.EVACUATED_TUBE: "evacuated tube",
    tables.SHWCollectorTypes.UNGLAZED: "unglazed",
}


def write_solar_hw(xlbook, d):
    xlbook.set_input("solar_collector_aperture", d.solar_collector_aperture)
    xlbook.set_input("collector_pitch",
                     PITCH[d.collector_pitch])
    if hasattr(d, "collector_orientation"):
        xlbook.set_input("collector_orientation",
                         ORIENTATIONS[d.collector_orientation])
    else:
        xlbook.set_input("collector_orientation",
                         "south")

    xlbook.set_input("solar_dedicated_storage_volume", d.solar_dedicated_storage_volume)
    xlbook.set_input("dedicated_solar_tank", not d.solar_storage_combined_cylinder)
    xlbook.set_input("collector_overshading",
                     OVERSHADING[d.collector_overshading])
    if hasattr(d, 'collector_type'):
        xlbook.set_input("collector_type",
                         COLLECTOR_TYPES[d.collector_type])
    else:
        xlbook.set_input("collector_type",
                         "")

    if hasattr(d, "collector_zero_loss_effy"):
        xlbook.set_input("collector_zero_loss_effy", d.collector_zero_loss_effy)
        xlbook.set_input("collector_heat_loss_coeff", d.collector_heat_loss_coeff)
    else:
        xlbook.set_input("collector_zero_loss_effy", "")
        xlbook.set_input("collector_heat_loss_coeff", "")

    xlbook.set_input("has_electric_shw_pump", d.has_electric_shw_pump)


def clear_solar_hw(xlbook, d):
    xlbook.set_input("solar_collector_aperture", 0)
    xlbook.set_input("collector_pitch", "")
    xlbook.set_input("collector_orientation", "")
    xlbook.set_input("solar_dedicated_storage_volume", "")
    xlbook.set_input("dedicated_solar_tank", "")
    xlbook.set_input("collector_zero_loss_effy", "")
    xlbook.set_input("collector_heat_loss_coeff", "")
    xlbook.set_input("collector_overshading", "")
    xlbook.set_input("collector_type", "")
    xlbook.set_input("has_electric_shw_pump", "")


def write_pv(xlbook, pv):
    xlbook.set_input("photovoltaic_systems_kWp", pv["kWp"])
    xlbook.set_input("photovoltaic_systems_pitch",
                     PITCH[pv["pitch"]])
    if "orientation" in pv:
        xlbook.set_input("photovoltaic_systems_orientation",
                         ORIENTATIONS[pv["orientation"]])
    else:
        xlbook.set_input("photovoltaic_systems_orientation", "South")
    xlbook.set_input("photovoltaic_systems_overshading_category",
                     OVERSHADING[pv["overshading_category"]])


def clear_pv(xlbook, d):
    xlbook.set_input("photovoltaic_systems_kWp", 0)
    xlbook.set_input("photovoltaic_systems_pitch", "")
    xlbook.set_input("photovoltaic_systems_orientation", "")
    xlbook.set_input("photovoltaic_systems_overshading_category", "")


TERRAIN = {
    tables.TerrainTypes.RURAL: 'Rural',
    tables.TerrainTypes.SUBURBAN: 'Low rise urban',
    tables.TerrainTypes.DENSE_URBAN: 'Dense urban',
}


def write_wind(xlbook, d):
    xlbook.set_input("terrain_type", TERRAIN[d.terrain_type])
    xlbook.set_input("N_wind_turbines", d.N_wind_turbines)
    xlbook.set_input("wind_turbine_rotor_diameter",
                     d.wind_turbine_rotor_diameter)
    xlbook.set_input("wind_turbine_hub_height",
                     d.wind_turbine_hub_height)


def clear_wind(xlbook, d):
    xlbook.set_input("terrain_type", "")
    xlbook.set_input("N_wind_turbines", "")
    xlbook.set_input("wind_turbine_rotor_diameter", "")
    xlbook.set_input("wind_turbine_hub_height", "")


SEDBUK_TYPE_TO_STRING = {
    tables.HeatingSystem.TYPES.regular_boiler: "Regular",
    tables.HeatingSystem.TYPES.storage_combi: "Storage combi",
    tables.HeatingSystem.TYPES.cpsu: "CPSU",
    tables.HeatingSystem.TYPES.combi: "Combi",
}


def write_sedbuk_data(xlbook, d):
    xlbook.set_input("sys1_sedbuk_type",
                     SEDBUK_TYPE_TO_STRING[d.sys1_sedbuk_type])
    if hasattr(d, "sys1_sedbuk_2005_effy"):
        xlbook.set_input("sys1_sedbuk_2005_effy", d.sys1_sedbuk_2005_effy)
        xlbook.set_input("sys1_sedbuk_2009_effy", "")
    elif hasattr(d, "sys1_sedbuk_2009_effy"):
        xlbook.set_input("sys1_sedbuk_2009_effy", d.sys1_sedbuk_2009_effy)
        xlbook.set_input("sys1_sedbuk_2005_effy", "")
    xlbook.set_input("sys1_sedbuk_fan_assisted", d.sys1_sedbuk_fan_assisted)


def clear_sedbuk_data(xlbook):
    xlbook.set_input("sys1_sedbuk_type", "")
    xlbook.set_input("sys1_sedbuk_2005_effy", "")
    xlbook.set_input("sys1_sedbuk_2009_effy", "")
    xlbook.set_input("sys1_sedbuk_fan_assisted", "")


def write_sap_table_system(xlbook, d):
    xlbook.set_input("main_heating_type_code", d.main_heating_type_code)


def clear_sap_table_system(xlbook):
    xlbook.set_input("main_heating_type_code", "")


def write_secondary_system(xlbook, d):
    if d.secondary_sys_fuel.is_electric:
        xlbook.set_input("secondary_sys_fuel", "Electric")
    else:
        xlbook.set_input("secondary_sys_fuel", d.secondary_sys_fuel.name)

    if hasattr(d, 'secondary_heating_type_code'):
        xlbook.set_input("secondary_heating_type_code",
                         d.secondary_heating_type_code)
        xlbook.set_input("secondary_sys_manuf_effy", "")
    else:
        xlbook.set_input("secondary_sys_manuf_effy",
                         d.secondary_sys_manuf_effy)
        xlbook.set_input("secondary_heating_type_code", "")

    xlbook.set_input("secondary_hetas_approved",
                     true_and_not_missing(d, "secondary_hetas_approved"))


def clear_secondary_system(xlbook):
    xlbook.set_input("secondary_sys_fuel", "")
    xlbook.set_input("secondary_heating_type_code", "")
    xlbook.set_input("secondary_sys_manuf_effy", "")


HEATING_EMITTER_TYPES = {
    tables.HeatEmitters.RADIATORS: "Radiators",
    tables.HeatEmitters.UNDERFLOOR_TIMBER: "Underfloor heating, pipes in insulated timber floor",
    tables.HeatEmitters.UNDERFLOOR_SCREED: "Underfloor heating, in screed above insulation",
    tables.HeatEmitters.UNDERFLOOR_CONCRETE: "Underfloor heating, pipes in concrete slab",
    tables.HeatEmitters.RADIATORS_UNDERFLOOR_TIMBER: "Underfloor heating and radiators, pipes in insulated timber floor",
    tables.HeatEmitters.RADIATORS_UNDERFLOOR_SCREED: "Underfloor heating and radiators, in screed above insulation",
    tables.HeatEmitters.RADIATORS_UNDERFLOOR_CONCRETE: "Underfloor heating and radiators, pipes in concrete slab",
    tables.HeatEmitters.FAN_COILS: "Fan coil units",
}


def process_cooling(xlbook, d):
    if hasattr(d, "cooled_area") and d.cooled_area > 0:
        write_cooling_system(xlbook, d)
    else:
        clear_cooling_system(xlbook, d)


def write_cooling_system(xlbook, d):
    xlbook.set_input("cooled_area", d.cooled_area)
    if hasattr(d, 'cooling_tested_eer'):
        xlbook.set_input("cooling_tested_eer", d.cooling_tested_eer)
        xlbook.set_input("cooling_energy_label", "")
    else:
        xlbook.set_input("cooling_energy_label", d.cooling_energy_label)
        xlbook.set_input("cooling_tested_eer", "")
    xlbook.set_input("cooling_packaged_system", d.cooling_packaged_system)
    xlbook.set_input("cooling_on_off_compressor_control",
                     d.cooling_compressor_control == 'on/off')


def clear_cooling_system(xlbook, d):
    xlbook.set_input("cooled_area", 0)
    xlbook.set_input("cooling_energy_label", "")
    xlbook.set_input("cooling_packaged_system", "")
    xlbook.set_input("cooling_on_off_compressor_control", "")


def process_systems(xlbook, d):
    if d.main_sys_fuel.is_electric:
        xlbook.set_input("main_sys_fuel",
                         "Electric")
    else:
        xlbook.set_input("main_sys_fuel",
                         d.main_sys_fuel.name)

    xlbook.set_input("electricity_tariff", d.electricity_tariff.name)

    if hasattr(d, "sys1_sedbuk_type"):
        write_sedbuk_data(xlbook, d)
    else:
        clear_sedbuk_data(xlbook)

    if hasattr(d, "main_heating_type_code"):
        write_sap_table_system(xlbook, d)
    else:
        clear_sap_table_system(xlbook)

    if hasattr(d, "heating_emitter_type"):
        xlbook.set_input("heating_emitter_type",
                         HEATING_EMITTER_TYPES[d.heating_emitter_type])
    else:
        xlbook.set_input("heating_emitter_type", "n/a")
    xlbook.set_input("control_type_code", d.control_type_code)
    xlbook.set_input("cpsu_not_in_airing_cupboard",
                     true_and_not_missing(d, 'cpsu_not_in_airing_cupboard'))

    if hasattr(d, 'sys1_load_compensator') and d.sys1_load_compensator in [
        tables.LoadCompensators.ENHANCED_LOAD_COMPENSATOR,
        tables.LoadCompensators.WEATHER_COMPENSATOR]:
        xlbook.set_input("has_enhanced_load_compensator", True)
    else:
        xlbook.set_input("has_enhanced_load_compensator", False)

    xlbook.set_input("sys1_delayed_start_thermostat",
                     true_and_not_missing(d, 'sys1_delayed_start_thermostat'))

    if hasattr(d, "hwsys_has_boiler_interlock"):
        has_interlock = d.hwsys_has_boiler_interlock
    elif hasattr(d, "sys1_has_boiler_interlock"):
        has_interlock = d.sys1_has_boiler_interlock
    else:
        has_interlock = False
    xlbook.set_input("sys1_has_boiler_interlock", has_interlock)

    if hasattr(d, "sys1_hetas_approved"):
        xlbook.set_input("sys1_hetas_approved", d.sys1_hetas_approved)
    else:
        xlbook.set_input("sys1_hetas_approved", "")

    if hasattr(d, "secondary_sys_fuel"):
        write_secondary_system(xlbook, d)
    else:
        clear_secondary_system(xlbook)

    process_hw(xlbook, d)
    process_cooling(xlbook, d)

    if hasattr(d, "photovoltaic_systems"):
        if len(d.photovoltaic_systems) == 1:
            write_pv(xlbook, d.photovoltaic_systems[0])
        elif len(d.photovoltaic_systems) > 1:
            raise CannotDoInSpreadsheetError("Too many pv systems")
        else:
            clear_pv(xlbook, d)
    else:
        clear_pv(xlbook, d)

    if hasattr(d, "N_wind_turbines") and d.N_wind_turbines > 0:
        write_wind(xlbook, d)
    else:
        clear_wind(xlbook, d)


VENTILATION_TYPES = {
    tables.VentilationTypes.NATURAL: "natural",
    tables.VentilationTypes.MVHR: "mvhr",
    tables.VentilationTypes.MEV_CENTRALISED: "mev (centralised)",
    tables.VentilationTypes.MEV_DECENTRALISED: "mev (decentralised)",
    tables.VentilationTypes.MV: "mv",
    tables.VentilationTypes.PIV_FROM_OUTSIDE: "piv",

}
#    MEV_CENTRALISED=1
#    MEV_DECENTRALISED=2
#    MV=4
#    PIV_FROM_OUTSIDE=5

DUCT_TYPES = {
    tables.DuctTypes.RIGID: "Rigid",
    tables.DuctTypes.FLEXIBLE: "Flexible",
    tables.DuctTypes.RIGID_INSULATED: "Rigid",
    tables.DuctTypes.FLEXIBLE_INSULATED: "Flexible",
}
DUCTS_INSULATED = {
    tables.DuctTypes.RIGID: False,
    tables.DuctTypes.FLEXIBLE: False,
    tables.DuctTypes.RIGID_INSULATED: True,
    tables.DuctTypes.FLEXIBLE_INSULATED: True,
}

WALL_TYPES = {
    tables.WallTypes.MASONRY: 'Masonry',
    tables.WallTypes.OTHER: 'Steel/Timber frame',
}
FLOOR_TYPES = {
    tables.FloorTypes.SUSPENDED_TIMBER_UNSEALED: 'Suspended wooden floor, unsealed',
    tables.FloorTypes.SUSPENDED_TIMBER_SEALED: 'Suspended wooden floor, sealed',
    tables.FloorTypes.NOT_SUSPENDED_TIMBER: 'Other',
    tables.FloorTypes.OTHER: 'Other',
}


def process_ventilation_system(xlbook, d):
    xlbook.set_input("ventilation_type",
                     VENTILATION_TYPES[d.ventilation_type])

    xlbook.set_input("mv_sfp", "")
    if hasattr(d, 'mvhr_effy'):
        xlbook.set_input("mvhr_effy", d.mvhr_effy)
        xlbook.set_input("mv_sfp", d.mvhr_sfp)
        xlbook.set_input("ducts_insulated", DUCTS_INSULATED[d.mv_ducttype])
    else:
        xlbook.set_input("mvhr_effy", "")
        xlbook.set_input("ducts_insulated", "")

    if hasattr(d, "mev_sfp"):
        xlbook.set_input("mv_sfp", d.mev_sfp)
    if hasattr(d, "mv_sfp"):
        xlbook.set_input("mv_sfp", d.mv_sfp)

    if hasattr(d, "mv_ducttype"):
        xlbook.set_input("duct_type", DUCT_TYPES[d.mv_ducttype])
    else:
        xlbook.set_input("duct_type", "")

    xlbook.set_input("mv_approved", true_and_not_missing(d, "mv_approved"))

    clear_existing_infiltration_inputs(xlbook)
    if hasattr(d, 'pressurisation_test_result'):
        xlbook.set_input("has_pressure_test_result", True)
        xlbook.set_input("pressurisation_test_result",
                         d.pressurisation_test_result)
        xlbook.set_input("pressurisation_test_result_is_for_average_dwelling",
                         False)
    elif hasattr(d, 'pressurisation_test_result_average'):
        xlbook.set_input("has_pressure_test_result", True)
        xlbook.set_input("pressurisation_test_result",
                         d.pressurisation_test_result_average)
        xlbook.set_input("pressurisation_test_result_is_for_average_dwelling",
                         True)
    else:
        xlbook.set_input("has_pressure_test_result", False)
        xlbook.set_input("has_draught_lobby", d.has_draught_lobby)
        xlbook.set_input("draught_stripping", d.draught_stripping * 100)
        xlbook.set_input("wall_type", WALL_TYPES[d.wall_type])
        xlbook.set_input("floor_type", FLOOR_TYPES[d.floor_type])


def clear_existing_infiltration_inputs(xlbook):
    xlbook.set_input("has_pressure_test_result", "")
    xlbook.set_input("pressurisation_test_result", "")
    xlbook.set_input("pressurisation_test_result_is_for_average_dwelling", "")
    xlbook.set_input("has_draught_lobby", "")
    xlbook.set_input("draught_stripping", "")
    xlbook.set_input("wall_type", "")
    xlbook.set_input("floor_type", "")


REGIONS = {
    2: 'South East England',
    3: 'Southern England',
    4: 'South West England',
    6: 'Midlands',
    8: 'North West England / South West Scotland',
    9: 'Borders',
    10: 'North East England',
    11: 'East Pennines',
    12: 'East Anglia',
    13: 'Wales',
}


def write_to_excel(xlbook, d):
    for i in INPUTS:
        xlbook.set_input(i, getattr(d, i))

    xlbook.set_input("sap_region", REGIONS[d.sap_region])
    process_envelope_elements(xlbook, d)
    process_ventilation_system(xlbook, d)
    process_systems(xlbook, d)


def check_results(xlbook, res, calctype, check_emissions):
    check_monthly_result(calctype, xlbook.h,
                         res.h, "heat loss coeff")
    if hasattr(res, "thermal_mass_parameter"):
        check_result(calctype, xlbook.thermal_mass_parameter,
                     res.thermal_mass_parameter, "thermal mass parameter", 0)
    check_monthly_result(calctype, xlbook.hw_heat_gain,
                         res.heat_gains_from_hw, "water heat gain", .5)
    check_monthly_result(calctype, xlbook.solar_gain_winter,
                         res.solar_gain_winter, "solar gain", .1)
    check_monthly_result(calctype, xlbook.full_light_gain,
                         res.full_light_gain, "heat gain from lights", .1)
    check_monthly_result(calctype, xlbook.winter_heat_gains,
                         res.winter_heat_gains, "total heat gain", .1)
    check_result(calctype, xlbook.heating_responsiveness,
                 res.heating_responsiveness, "heating system responsiveness", 0)
    check_result(calctype, xlbook.heating_control_type,
                 res.heating_control_type_sys1, "heating control type", 0)
    check_monthly_result(calctype, xlbook.Tliving,
                         res.heat_calc_results['Tmean_living_area'], "internal temperature, living area", .01)
    check_monthly_result(calctype, xlbook.Tother,
                         res.heat_calc_results['Tmean_other'], "internal temperature, rest of dwelling", .01)
    check_monthly_result(calctype, xlbook.Tmean,
                         res.heat_calc_results['Tmean'], "internal temperature", .01)
    check_monthly_result(calctype, xlbook.Q_required,
                         res.Q_required, "space heat required", 2)

    if sum(res.Q_cooling_required) > 0:
        check_summer_monthly_result(calctype, xlbook.solar_gain_summer,
                                    res.solar_gain_summer, "solar gain (summer)", .1)
        check_summer_monthly_result(calctype, xlbook.summer_heat_gains,
                                    res.summer_heat_gains,
                                    "total heat gain (summer)", .1)

    if not check_emissions:
        # Emissions results won't match for TER results due to 2009 vs
        # 2005 fuel factors
        return

    check_result(calctype, xlbook.space_main_heating_emissions,
                 res.emissions_heating_main,
                 "space heat emissions (main)", 0.5)
    check_result(calctype, xlbook.space_secondary_heating_emissions,
                 res.emissions_heating_secondary,
                 "space heat emissions (secondary)", 0.5)
    check_result(calctype, xlbook.water_heating_emissions,
                 res.emissions_water,
                 "water heat emissions", 0.5)
    check_result(calctype, xlbook.water_heating_emissions_summer_immersion,
                 res.emissions_water_summer_immersion,
                 "water heat emissions (summer immersion)", 0.5)
    check_result(calctype, xlbook.pump_emissions,
                 res.emissions_fans_and_pumps + res.emissions_mech_vent_fans,
                 "pump and fan emissions", 0.01)
    check_result(calctype, xlbook.lighting_emissions,
                 res.emissions_lighting, "lighting emissions", 0.5)
    check_result(calctype, xlbook.cooling_emissions,
                 res.emissions_cooling,
                 "cooling emissions", 0.01)


def run_dwelling(xlbook, d, can_run_fee, can_run_der, can_run_ter):
    #can_run_fee=False
    #can_run_ter=False
    write_to_excel(xlbook, d)
    runner.run_fee(d)
    runner.run_der(d)
    runner.run_ter(d)
    runner.run_sap(d)

    if can_run_der:
        xlbook.set_calc_type("DER")
        check_results(xlbook, d.der_results, "DER", True)
        check_result("DER", xlbook.der, d.der_results.der_rating, "DER", 0.01)

        xlbook.set_calc_type("SAP")
        check_results(xlbook, d.er_results, "SAP", True)
        check_result("SAP", xlbook.sap, d.er_results.sap_value, "SAP", 0.01)
        return False
    if can_run_ter:
        xlbook.set_calc_type("TER")
        check_results(xlbook, d.ter_results, "TER", False)
        check_result("TER", xlbook.ter, d.ter_results.ter_rating, "TER", 0.01)

    if can_run_fee:
        xlbook.set_calc_type("FEE")
        check_results(xlbook, d.fee_results, "FEE", False)

        months_with_cooling = sum(1 if x > 0 else 0 for x in d.fee_results.Q_cooling_required)
        if months_with_cooling != 3:
            logging.error("FEE is probably wrong due to cooling calculation")
            check_result("FEE", xlbook.fee, d.fee_results.fee_rating, "FEE", 0.01)


def run_case(xlbook, fname):
    if fname in [
        "EW-2k-semi - electric CPSU_10-hour 180 litres.rtf",
    ]:
        return False

    res = v0.load_or_parse_file(fname, reference_case_parser.whole_file, False)
    dwelling = Dwelling()
    input_conversion_rules.process_inputs(dwelling, res.inputs)

    can_run_der = True
    can_run_ter = True
    can_run_fee = True

    if hasattr(dwelling, 'main_sys_2_fuel'):
        can_run_der = False
        can_run_ter = False
    if not hasattr(dwelling, 'main_sys_fuel'):
        # These are the community heating tests cases
        #can_run_der=False
        return
    if dwelling.get('wwhr_systems'):
        can_run_der = False
    if hasattr(dwelling, 'main_heating_pcdf_id'):
        can_run_der = False
    if hasattr(dwelling, 'photovoltaic_systems') and len(dwelling.photovoltaic_systems) > 1:
        can_run_der = False
    if not dwelling['ventilation_type'] in [
        VentilationTypes.NATURAL,
        VentilationTypes.MVHR,
        VentilationTypes.MEV_CENTRALISED,
        VentilationTypes.MV]:
        #sap_tables.VentilationTypes.MEV_DECENTRALISED]:
        #sap_tables.VentilationTypes.PIV_FROM_OUTSIDE]:
        can_run_der = False
    if hasattr(dwelling, 'appendix_q_systems'):
        can_run_der = False
        can_run_fee = False

    print(fname)
    try:
        run_dwelling(xlbook, dwelling, can_run_fee, can_run_der, can_run_ter)
        return True
    except CannotDoInSpreadsheetError as e:
        print(("Skipping because: " + e.message))
        return False


def workbook_is_open(xl, name):
    for wb in xl.Workbooks:
        if wb.Name == name:
            return True
    return False


def main():
    logging.basicConfig(level=logging.ERROR)
    from sap import pcdf

    pcdf.DATA_FILE = "./official_reference_cases/pcdf2009_test_322.dat"

    xl = win32com.client.gencache.EnsureDispatch("Excel.Application")
    xl_opened_by_script = False

    if not workbook_is_open(xl, WORKBOOK_NAME):
        xl_opened_by_script = True
        xl.Workbooks.Open("C:\\UCL\SAP\spreadsheet\ExcelSAP 1a  & 1b.xlsm")
        print("yes")

    xlbook = XLInputSheetModel()
    count = 0
    for fname in TEST_CASES:
        if run_case(xlbook, fname):
            count += 1
            xlbook.wb.SaveAs(fname + ".xlsm")

    print(("Ran: ", count))

    if xl_opened_by_script:
        xl.Workbooks(WORKBOOK_NAME).Close()


if __name__ == "__main__":
    main()
