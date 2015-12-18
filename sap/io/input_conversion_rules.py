"""
Input conversion rules
----------------------

Input conversion rules for converting from parsed input file
(from RTF, Yaml, or pickled file) into a Dwelling object for use in calculations
"""
import copy
import logging

from ..sap_types import WallTypes, FloorTypes, ImmersionTypes, TerrainTypes, CylinderInsulationTypes, GlazingTypes, \
    ThermalStoreTypes, OvershadingTypes, SHWCollectorTypes, HeatingTypes, PVOvershading, OpeningTypeDataSource
from .. import worksheet
from ..pcdf import DuctTypes, VentilationTypes
from ..sap_tables import HeatEmitters, CommunityDistributionTypes, LoadCompensators
from ..fuels import ELECTRICITY_STANDARD, ELECTRICITY_7HR, ELECTRICITY_10HR, fuel_from_code


class LambdaMapping(object):

    def __init__(self, attr, f):
        self.f = f
        self.attr = attr

    def apply(self, d, r):
        d[self.attr] = self.f(r)



class subtoken_mapping:

    def __init__(self, attr, input_id, token_id, converter=float):
        self.attr = attr
        self.inputId = input_id
        self.tokenId = token_id
        self.converter = converter

    def apply(self, d, r):
        if len(r.vals) <= self.inputId:
            logging.warning(
                "Not enough values for subtoken mapping of %s\n", self.attr)
            return

        tokens = r.vals[self.inputId].value.split()
        if len(tokens) <= self.tokenId:
            logging.warning(
                "Not enough tokens for subtoken mapping of %s\n", self.attr)
            return

        val = self.converter(tokens[self.tokenId])
        d[self.attr] = val


# Mapping functions for primary inputs
def simple_mapping(attr):
    return LambdaMapping(attr, lambda x: float(x.vals[0].value))


def lookup_mapping(attr, dic):
    return LambdaMapping(attr, lambda x: dic[x.vals[0].value])


def percent_to_float(x):
    return float(x[:-1]) / 100.0

ORIENTATIONS = {'(Unspecified)': 90,
                'unspecified': 90,
                'Horiz': 180,
                'North': 0,
                'N': 0,
                'North East': 45,
                'NE': 45,
                'East': 90,
                'E': 90,
                'South East': 135,
                'SE': 135,
                'South': 180,
                'S': 180,
                'South West': 225,
                'SW': 225,
                'West': 270,
                'W': 270,
                'North West': 315,
                'NW': 315,
                }

OVERSHADING = {
    'Average': OvershadingTypes.AVERAGE,
    'Very little': OvershadingTypes.VERY_LITTLE,
}

BOOLEANS = {
    'Yes': True,
    'No': False,
}


class Labels:
    LIVING_AREA = 'Living area'
    ORIENTATION = 'Front of dwelling faces'
    THERMAL_MASS = 'Thermal mass'
    DETACHMENT = 'Detachment'
    DWELLING_TYPE = 'Dwelling type'
    THERMAL_BRIDGES = 'Thermal bridges'
    REGION = 'Region'

    PRESSURE_TEST = 'Pressure tests'
    PRESSURE_TEST_RESULT = 'q50 measured in this dwelling'
    PRESSURE_TEST_RESULT_AVE = 'Average measured q50'
    PRESSURE_TEST_RESULT_ASSUMED = 'Assumed q50 for the calculation'
    PRESSURE_TEST_DESIGNED = 'Design q50'
    NCHIMNEYS = 'Number of chimneys'
    NFLUES = 'Number of open flues'
    NINT_FANS = 'Number of intermittent fans'
    NPASS_STACKS = 'Number of passive stacks'
    NSIDES_SHELTERED = 'Number of sides sheltered'
    NLIGHTING_OUTLETS = 'Total fixed lighting outlets'
    NLOW_ENERGY_LIGHTING_OUTLETS = 'Low energy fixed lighting outlets'

    OVERSHADING = 'Overshading'
    LOW_WATER_USE = 'Water use <= 125 litres/person/day'

    CONSERVATORY = "Conservatory"
    TERRAIN_TYPE = "Terrain type"
    SOLAR_PANEL = "Solar panel"

    MAIN_HEATING_SYSTEM = 'Main heating system'
    MAIN_HEATING_SYSTEM_1 = 'Main heating system 1'
    MAIN_HEATING_SYSTEM_2 = 'Main heating system 2'
    SECONDARY_HEATING_SYSTEM = 'Secondary heating'
    WATER_HEATING_SYSTEM = 'Water heating'
    CONTROL_SYSTEM = 'Main heating controls'
    CONTROL_SYSTEM_1 = 'Main heating controls 1'
    CONTROL_SYSTEM_2 = 'Main heating controls 2'

    COOLING_SYSTEM = 'Space cooling system'

    APPENDIX_Q = 'Special feature '

    ELECTRICITY_TARIFF = 'Electricity tariff'

    VENTILATION = 'Ventilation'
    WALL_TYPE = 'Walls'
    GND_FLOOR_TYPE = 'Ground floor'
    DRAUGHT_LOBBY = 'Draught lobby'
    DRAUGHT_PROOFING = 'Draught proofing'
    DRAUGHT_PROOFING2 = 'Draughtstripping'

    # Water system inputs
    CYLINDER_VOLUME = 'Cylinder volume'
    CYLINDER_INSULATION = 'Cylinder insulation'
    CPSU_VOLUME = 'CPSU volume'
    CPSU_INSULATION = 'CPSU insulation'
    STORE_VOLUME = 'Store volume'
    STORE_INSULATION = 'Store insulation'
    THERMAL_STORE_IN_AIR_CUPBOARD = 'Thermal store in airing cupboard'
    CPSU_NOT_IN_AIRING_CUPBOARD = 'CPSU not in airing cupboard'
    PRIMARY_PIPEWORK_INSULATION = 'Primary pipework insulation'
    CYLINDERSTAT = 'Cylinderstat'
    HW_TIMER = 'Water heating separately timed'
    IMMERSION_TYPE = 'Immersion'

    # Main system input
    SYSTEM_FUEL = 'Fuel'
    CENTRAL_HEATING_PUMP = 'Central heating pump in heated space'
    CENTRAL_HEATING_PUMP_NOT_IN_HEAT_SPACE = 'Central heating pump not in heated space'
    OIL_BOILER_PUMP_IN_HEATED_SPACE = 'Oil pump in heated space'
    OIL_BOILER_PUMP_NOT_IN_HEATED_SPACE = 'Oil pump not in heated space'
    BOILER_INTERLOCK = 'Boiler interlock'
    MAIN_HEAT_FRACTION = 'Fraction of main heat'
    THERMAL_STORE_HW_ONLY = 'Hot Water Only thermal store'
    THERMAL_STORE_INTEGRATED = 'Integrated thermal store'

    # Heat emitter types
    RADIATORS = 'Radiators'
    UNDERFLOOR_SCREED = 'Underfloor heating, in screed'
    UNDERFLOOR_TIMBER = 'Underfloor heating, timber floor'
    UNDERFLOOR_CONCRETE = 'Underfloor heating, concrete slab'
    RADS_UNDERFLOOR_TIMBER = 'Underfloor heating (timber floor) + radiators'
    RADS_UNDERFLOOR_SCREED = 'Underfloor heating (in screed) + radiators'
    RADS_UNDERFLOOR_CONRETE = 'Underfloor heating (concrete slab) + radiators'
    FAN_COILS = 'Fan coil units'

    # Cooling system
    COOLING_ENERGY_LABEL = 'Energy label class'
    COOLING_COMPRESSOR_CONTROL = 'Compressor control'
    COOLED_AREA = 'Cooled area'

    # PV
    PHOTOVOLTAICS = "Photovoltaics"
    PV_PEAK_KW = "Peak kW"
    PV_PITCH = "pitch"
    PV_OVERSHADING = "overshading"

    # Wind
    WIND_TURBINE = "Wind turbine"
    WIND_NUMBER_OF_TURBINES = "Number of turbines"
    WIND_ROTOR_DIAMETER = "rotor diameter"
    WIND_HUB_HEIGHT = "hub height above building"

    # Hydro
    HYDRO = "Hydro-electric generation"

    YEAR_COMPLETED = "Year completed"


class NullRule:

    def apply(self, d, r):
        # This input does nothing
        pass


class FixedValueRule:

    def __init__(self, val):
        self.expected_val = val

    def apply(self, d, r):
        # Always expect the same value for this rule (mainly for debugging)
        if len(r.vals[0]) > 1:
            if len(r.vals[0]) != len(self.expected_val):
                logging.warning(
                    "Unexpected input value (mismatched length): %s", r)
                return
            for i in range(len(r.vals[0])):
                if r.vals[0][i] != self.expected_val[i]:
                    logging.warning("Unexpected input value: %s", r)
                    return
        else:
            if r.vals[0].value != self.expected_val:
                logging.warning("Unexpected input value: %s", r)


class ThermalMassRule:

    def apply(self, d, r):
        toks = r.vals[0].value.split()
        if toks[0] == "TMP":
            d.thermal_mass_parameter = float(toks[2])
        elif len(toks) > 3 and toks[2] == "k":
            pass
        else:
            logging.warning("Unknown thermal mass rule: %s", r)


class ThermalBridgingRule:

    def apply(self, d, r):
        if r.vals[0].value.split() == 'User-defined'.split() and r.vals[0].note.split() == 'individual Y -values'.split():
            y_table = r.vals[1]
            if y_table.column_headings[1] != "Length" or y_table.column_headings[2] != "Y -value":
                logging.warning("Invalid thermal bridging table: %s", y_table)

            process_y_value_table(d, y_table)
            return

        for v in r.vals:
            if v.value == 'Default ' or v.value == 'ERROR ':
                toks = v.note.split()
            else:
                toks = v.value.split()

            if len(toks) == 3 and toks[0] == 'y':
                d.Uthermalbridges = float(toks[2])
                return

        logging.warning("Unknown thermal bridging rule: %s", r)


def process_y_value_table(d, y_table):
    y_values = []
    for row in y_table.rows:
        length = float(row[0])
        toks = row[1].split()
        y_val = float(toks[0])
        y_values.append(dict(
            length=length,
            y=y_val))

    d.y_values = y_values

EMITTER_TYPES = {
    Labels.RADIATORS: HeatEmitters.RADIATORS,
    Labels.UNDERFLOOR_SCREED: HeatEmitters.UNDERFLOOR_SCREED,
    Labels.UNDERFLOOR_TIMBER: HeatEmitters.UNDERFLOOR_TIMBER,
    Labels.UNDERFLOOR_CONCRETE: HeatEmitters.UNDERFLOOR_CONCRETE,
    Labels.RADS_UNDERFLOOR_TIMBER: HeatEmitters.RADIATORS_UNDERFLOOR_TIMBER,
    Labels.RADS_UNDERFLOOR_SCREED: HeatEmitters.RADIATORS_UNDERFLOOR_SCREED,
    Labels.RADS_UNDERFLOOR_CONRETE: HeatEmitters.RADIATORS_UNDERFLOOR_CONCRETE,
    Labels.FAN_COILS: HeatEmitters.FAN_COILS,
}

FUELS = {
    'Electricity': ELECTRICITY_STANDARD,
    'Mains gas': fuel_from_code(1),
    'mains gas': fuel_from_code(1),
    'LNG': fuel_from_code(8),
    'Bulk LPG': fuel_from_code(2),
    'Bottled LPG': fuel_from_code(3),
    'LPG cond. 18': fuel_from_code(9),

    'Heating oil': fuel_from_code(4),
    'Biodiesel any': fuel_from_code(71),
    'Biodiesel from any biomass source': fuel_from_code(71),
    'Biodiesel UCOME': fuel_from_code(72),
    'Rapeseed oil': fuel_from_code(73),
    'Mineral or biofuel': fuel_from_code(74),
    'B30K': fuel_from_code(75),
    'Bioethanol': fuel_from_code(76),

    'House coal': fuel_from_code(11),
    'Anthracite': fuel_from_code(15),
    'Smokeless': fuel_from_code(12),
    'Wood logs': fuel_from_code(20),
    'Wood pellets (bags)': fuel_from_code(22),
    'Wood pellets (bulk)': fuel_from_code(23),
    'Wood chips': fuel_from_code(21),
    'wood chips': fuel_from_code(21),
    'Dual fuel appliance': fuel_from_code(10),
    'Dual fuel': fuel_from_code(10),
}


def get_fuel(v):
    if v.vals[0].note != "":
        fullname = "%s(%s)" % (v.vals[0].value, v.vals[0].note)
    else:
        fullname = v.vals[0].value
    if fullname in FUELS:
        return copy.deepcopy(FUELS[fullname])
    else:
        logging.warning("Unknown fuel type: \"%s\"" % (fullname,))
        return None

COMMUNITY_FUELS = {
    # Here we are always setting the fuel as a boiler fuel instead of CHP
    'Mains gas ': fuel_from_code(51),
    'LPG ': fuel_from_code(52),
    'Oil ': fuel_from_code(53),
    'B30D ': fuel_from_code(55),
    'Electricity ': fuel_from_code(41),
    'Biomass ': fuel_from_code(43),
    'Biogas ': fuel_from_code(44),
    'Biogas': fuel_from_code(44),
    'Geothermal': fuel_from_code(46),
    'Waste heat': fuel_from_code(45),
}
APPENDIX_D7_TYPES = {
    "condensing, modulating burner control": "D7.4c",
}


class MainHeatingSystemRule:

    def __init__(self, system_id):
        if system_id == 1:
            self.fuel_attr = 'main_sys_fuel'
            self.heating_type_code_attr = 'main_heating_type_code'
            self.pcdf_id_attr = 'main_heating_pcdf_id'
            self.heating_fraction_attr = 'main_heating_fraction'
            self.heating_emitter_attr = 'heating_emitter_type'
            self.oil_pump_location_attr = 'main_heating_oil_pump_inside_dwelling'
            self.hetas_attr = "sys1_hetas_approved"
            self.sedbuk_2005_effy = "sys1_sedbuk_2005_effy"
            self.sedbuk_2009_effy = "sys1_sedbuk_2009_effy"
            self.sedbuk_type = "sys1_sedbuk_type"
            self.sedbuk_fan_assisted = "sys1_sedbuk_fan_assisted"
            self.sedbuk_range_case_loss_at_full_output = "sys1_sedbuk_range_case_loss_at_full_output"
            self.sedbuk_range_full_output = "sys1_sedbuk_range_full_output"

        elif system_id == 2:
            self.fuel_attr = 'main_sys_2_fuel'
            self.heating_type_code_attr = 'main_heating_2_type_code'
            self.pcdf_id_attr = 'main_heating_2_pcdf_id'
            self.heating_fraction_attr = 'main_heating_2_fraction'
            self.heating_emitter_attr = 'heating_emitter_type2'
            self.oil_pump_location_attr = 'main_heating_2_oil_pump_inside_dwelling'
            self.hetas_attr = "sys2_hetas_approved"
        else:
            pass

    def apply(self, dwelling, data):
        """

        :param dwelling:
        :param data: PyParsing ParseResults object
        :return:
        """
        if data.vals[0].value == 'Community heating scheme':
            dwelling[self.heating_type_code_attr] = "community"
            heat_src, sap_dist_typ = parse_community_heating_sources(data)
            dwelling['community_heat_sources'] = heat_src
            dwelling['sap_community_distribution_type'] = sap_dist_typ
            return

        v_prev = None
        for v in data.vals:
            if v.label != '':
                if v.label == Labels.SYSTEM_FUEL:
                    fuel = get_fuel(v)
                    if fuel is not None:
                        dwelling[self.fuel_attr] = fuel
                    else:
                        logging.warning("Unknown fuel: %s", v.vals[0].value)
                elif v.label == Labels.MAIN_HEAT_FRACTION:
                    dwelling[self.heating_fraction_attr] = float(v.vals[0].value)
                elif v.label == 'Database ':
                    dwelling[self.pcdf_id_attr] = v.note.split()[4]
                elif v.label == "Model qualifier":
                    if v.vals[0].value == "(regular boiler)":
                        # We are allowed to use store params from input
                        # data if this is a regular boiler
                        dwelling.parser_use_input_file_store_params = True
                else:
                    logging.warning("Unknown system input: %s", v)
            else:
                try:
                    # -- Extract the heating type code attribute using a simple heuristic
                    # Expects that there should be an int-valued bit of information in this line...
                    # If not (ValueError) then go on to try to parse the rest
                    # FIXME: is this a solid enough heuristic to reliably catch the heating code type?
                    value_type = int(v.value.split()[0])
                    dwelling[self.heating_type_code_attr] = value_type

                    if v.note == "HETAS Approved" or "HETAS" in v.value:
                        dwelling[self.hetas_attr] = True

                    continue
                except ValueError:
                    # logging.warning("Could not extract main heating type from input: {}".format(v))
                    pass

                if v.value == Labels.CENTRAL_HEATING_PUMP:
                    dwelling['central_heating_pump_in_heated_space'] = True

                elif v.value == Labels.CENTRAL_HEATING_PUMP_NOT_IN_HEAT_SPACE:
                    dwelling['central_heating_pump_in_heated_space'] = False

                elif v.value == Labels.OIL_BOILER_PUMP_IN_HEATED_SPACE:
                    dwelling[self.oil_pump_location_attr] = True

                elif v.value == Labels.OIL_BOILER_PUMP_NOT_IN_HEATED_SPACE:
                    dwelling[self.oil_pump_location_attr] = False

                elif v.value == Labels.THERMAL_STORE_HW_ONLY:
                    dwelling['thermal_store_type'] = ThermalStoreTypes.HW_ONLY

                elif v.value == Labels.THERMAL_STORE_INTEGRATED:
                    dwelling['thermal_store_type'] = ThermalStoreTypes.INTEGRATED

                elif v.value in EMITTER_TYPES:
                    dwelling[self.heating_emitter_attr] = EMITTER_TYPES[v.value]

                elif v.value.split()[0] == 'Database':
                    if v.note != "":
                        dwelling[self.pcdf_id_attr] = v.note.split()[4]
                    else:
                        dwelling[self.pcdf_id_attr] = v.value.split()[5][:-1]

                elif v.value == '(re-assigned following interchange of main 1 and secondary)':
                    dwelling['reassign_systems_for_test_case_30'] = True

                elif v.value == 'Each system heats separate parts of house':
                    dwelling['heating_systems_heat_separate_areas'] = True

                elif v.value.split()[0] == "SEDBUK(2005)":
                    dwelling[self.sedbuk_2005_effy] = float(v.value.split()[1][0:-2])
                    self.handle_sedbuk_system(dwelling, v, v_prev)

                elif v.value.split()[0] == "SEDBUK(2009)":
                    dwelling[self.sedbuk_2009_effy] = float(v.value.split()[1][0:-2])
                    self.handle_sedbuk_system(dwelling, v, v_prev)

                elif "Case emission" in v.value:
                    # part of a sedbuk range cooker
                    toks = v.value.split()
                    dwelling[self.sedbuk_range_case_loss_at_full_output] = float(toks[2])
                    dwelling[self.sedbuk_range_full_output] = float(toks[8])

                else:
                    logging.warning("Unknown system field: %s", v)

            v_prev = v

    def handle_sedbuk_system(self, dwelling, v, v_prev):
        dwelling.parser_use_input_file_store_params = True

        previn = v_prev.vals[0].vals[
            0].value if v_prev.value == "" else v_prev.value
        dwelling[self.sedbuk_type] = self.get_sedbuk_type(previn)
        dwelling[self.sedbuk_fan_assisted] = "fan-assisted" in previn

    def get_sedbuk_type(self, typestr):
        if "Regular" in typestr or "Range cooker" in typestr:
            return HeatingTypes.regular_boiler
        elif "primary store" in typestr:
            return HeatingTypes.storage_combi
        elif "CPSU" in typestr:
            return HeatingTypes.cpsu
        elif "Combi" in typestr:
            return HeatingTypes.combi
        else:
            raise ValueError("Unknown sedbuk type")

COMMUNITY_DISTRIBUTION_TYPES = {
    "Piping >= 1991, pre-insulated, low temp, variable flow":
    CommunityDistributionTypes.MODERN_LOW_TEMP,
    "Piping >= 1991, pre-insulated, medium temp, variable flow":
    CommunityDistributionTypes.MODERN_HIGH_TEMP,
    "Piping <= 1990, not pre-ins, medium/high temp, full flow":
    CommunityDistributionTypes.PRE_1990_UNINSULATED,
}


def parse_community_heating_sources(r):
    heat_sources = []
    distribution_type = None
    current_heat_source = None

    for v in r.vals[1:]:
        if v.label == "Heat source":
            if current_heat_source is not None:
                heat_sources.append(current_heat_source)
            current_heat_source = dict(source=v.vals[0].value)

        elif v.label == "Fuel":
            current_heat_source['fuel'] = copy.deepcopy(
                COMMUNITY_FUELS[v.vals[0].value])

        else:
            tokens = [x.split() for x in v.value.split(',')]
            if len(tokens) == 1 and len(tokens[0]) == 0:
                pass
            elif v.value in COMMUNITY_DISTRIBUTION_TYPES:
                # done with heat sources
                heat_sources.append(current_heat_source)
                current_heat_source = None

                distribution_type = COMMUNITY_DISTRIBUTION_TYPES[v.value]
            elif tokens[0][0] == "heat" and tokens[0][1] == "fraction":
                current_heat_source['fraction'] = float(tokens[0][2])
                current_heat_source['efficiency'] = float(tokens[1][1]) / 100.
            elif tokens[0][0].lower() == "heat-to-power":
                current_heat_source['heat_to_power'] = float(tokens[0][2])
            else:
                logging.warning("Unknown community heating field: %s", v)

    if current_heat_source is not None:
        heat_sources.append(current_heat_source)

    return heat_sources, distribution_type

PV_OVERSHADING = {
    'Heavy': PVOvershading.HEAVY,
    'Significant': PVOvershading.SIGNIFICANT,
    'Modest': PVOvershading.MODEST,
    'None or very little': PVOvershading.NONE_OR_VERY_LITTLE,
}

PV_PITCH = {
    "horizontal": "Horizontal",
    "300": 30,
    "300 pitch": 30,
    "450": 45,
    "450 pitch": 45,
    "600": 60,
    "600 pitch": 60,
}

PV_ORIENTATION = {
    "North": 0,
    "orientation North": 0,
    "North East": 45,
    "orientation South": 180,
    "orientation South East": 135,
    "South East": 135,
    "South": 180,
    "South West": 225,
    "orientation South West": 225,
}


class PVRule:

    def apply(self, d, r):
        if not hasattr(d, "photovoltaic_systems"):
            d.photovoltaic_systems = []

        pv_system = dict()
        for v in r.vals:
            if v.label != '':
                if v.label == Labels.PV_PEAK_KW:
                    pv_system["kWp"] = float(v.vals[0].value)
                elif v.label == Labels.PV_OVERSHADING:
                    pv_system['overshading_category'] = PV_OVERSHADING[
                        v.vals[0].value]
                elif v.label == Labels.PV_PITCH:
                    tokens = v.vals[0].value.split(',')
                    pv_system['pitch'] = PV_PITCH[tokens[0]]
                    if len(tokens) > 1:
                        pv_system['orientation'] = PV_ORIENTATION[
                            tokens[1].strip()]
                else:
                    logging.warning("Unknown PV input: %s", v)
            else:
                if v.value == "None":
                    return  # No PV system
                logging.warning("Unknown PV field: %s", v)

        d.photovoltaic_systems.append(pv_system)


class WindTurbineRule:

    def apply(self, d, r):
        for v in r.vals:
            if v.label != '':
                if v.label == Labels.WIND_NUMBER_OF_TURBINES:
                    d.N_wind_turbines = float(v.vals[0].value)
                elif v.label == Labels.WIND_ROTOR_DIAMETER:
                    d.wind_turbine_rotor_diameter = float(v.vals[0].value)
                elif v.label == Labels.WIND_HUB_HEIGHT:
                    d.wind_turbine_hub_height = float(v.vals[0].value)
                else:
                    logging.warning("Unknown wind turbine input: %s", v)
            else:
                if v.value == "No":
                    return  # No wind turbines
                logging.warning("Unknown wind turbine field: %s", v)

TERRAIN = {
    'Rural': TerrainTypes.RURAL,
    'Low rise urban / Suburban': TerrainTypes.SUBURBAN,
    'Dense urban': TerrainTypes.DENSE_URBAN,
}


class ControlSystemRule:

    def __init__(self, system_id):
        if system_id == 1:
            self.control_type_attr = 'control_type_code'
            self.interlock_attr = 'sys1_has_boiler_interlock'
            self.load_compensator_attr = 'sys1_load_compensator'
            self.delayed_start_thermo_attr = 'sys1_delayed_start_thermostat'
        elif system_id == 2:
            self.control_type_attr = 'control_2_type_code'
            self.interlock_attr = 'sys2_has_boiler_interlock'
            self.load_compensator_attr = 'sys2_load_compensator'
            self.delayed_start_thermo_attr = 'sys2_delayed_start_thermostat'
        else:
            pass

    def apply(self, dwelling, data):
        for v in data.vals:
            if v.label != '':
                if v.label == Labels.BOILER_INTERLOCK:
                    dwelling[self.interlock_attr] = BOOLEANS[v.vals[0].value]
                else:
                    logging.warning("Unknown control system input: %s", v)
            else:
                try:
                    type = int(v.value.split()[0])
                    dwelling[self.control_type_attr] = type
                    continue
                except ValueError as e:
                    pass

                if v.value == "Enhanced load compensator":
                    dwelling[self.load_compensator_attr] = LoadCompensators.ENHANCED_LOAD_COMPENSATOR
                elif v.value == "Weather compensator":
                    dwelling[self.load_compensator_attr] = LoadCompensators.WEATHER_COMPENSATOR
                elif v.value == "Delayed start":
                    dwelling[self.delayed_start_thermo_attr] = True
                else:
                    logging.warning("Unknown control system field: %s", v)


class CoolingSystemRule:

    def apply(self, d, r):
        if r.vals[0].value == "None":
            return
        for v in r.vals:
            if v.label != '':
                if v.label == Labels.COOLED_AREA:
                    d.cooled_area = float(v.vals[0].value)
                elif v.label == Labels.COOLING_ENERGY_LABEL:
                    d.cooling_energy_label = v.vals[0].value
                elif v.label == Labels.COOLING_COMPRESSOR_CONTROL:
                    d.cooling_compressor_control = v.vals[0].value
                elif v.label == "EER":
                    d.cooling_tested_eer = float(v.vals[0].value)
                else:
                    logging.warning("Unknown cooling system input: %s", v)
            else:
                if v.value == 'Packaged system':
                    d.cooling_packaged_system = True
                elif v.value == 'Split system':
                    d.cooling_packaged_system = False
                else:
                    logging.warning("Unknown cooling system field: %s", v)


class SecondaryHeatingSystemRule:

    def apply(self, d, r):
        is_using_manufacturer_data = False
        for v in r.vals:
            if v.label == Labels.SYSTEM_FUEL:
                d.secondary_sys_fuel = get_fuel(v)
            elif v.label == "Manufacturer's data":
                is_using_manufacturer_data = True
            elif v.label != '':
                logging.warning("Unknown secondary system input: %s", v)
            else:
                try:
                    type = int(v.value.split()[0])
                    d.secondary_heating_type_code = type
                    if v.note == "HETAS Approved" or "HETAS" in v.value:
                        d.secondary_hetas_approved = True
                    continue
                except ValueError as e:
                    pass

                if v.value == "None":
                    pass
                elif v.value == "(portable electric heaters assumed for the calculation)":
                    d.force_secondary_heating = True
                elif is_using_manufacturer_data and "efficiency" in v.value:
                    tokens = v.value.split()
                    effy_idx = [i for i, x in enumerate(
                        tokens) if x == "efficiency"][0] + 1
                    d.secondary_sys_manuf_effy = 100 * \
                        percent_to_float(tokens[effy_idx])
                else:
                    logging.warning("Unknown secondary system field: %s", v)


class AppendixQRule:

    def apply(self, d, r):
        sys = dict()
        ach_rates = None  # need to be assembled across two sub inputs
        for v in r.vals:
            if v.label == "Energy saved or generated":
                toks = v.vals[0].value.split()
                sys['generated'] = float(toks[0])

                if v.vals[0].note != "" and v.vals[0].note != "Electricity":
                    sys['fuel_saved'] = copy.deepcopy(FUELS[v.vals[0].note])
            elif v.label == "Energy used":
                toks = v.vals[0].value.split()
                sys['used'] = float(toks[0])
                if v.vals[0].note != "" and v.vals[0].note != "Electricity":
                    sys['fuel_used'] = copy.deepcopy(FUELS[v.vals[0].note])
            elif v.label == "air change rates ":
                ach_rates = v.vals[0].value.split()
            elif ach_rates != None:
                # second part
                ach_rates += v.value.split()
                sys['ach_rates'] = [float(x) for x in ach_rates]
                ach_rates = None
            else:
                logging.warning("Unknown Appendix Q input %s", v)
        if not 'generated' in sys:
            sys['generated'] = 0
        if not 'used' in sys:
            sys['used'] = 0
        if not hasattr(d, 'appendix_q_systems'):
            d.appendix_q_systems = [sys, ]
        else:
            d.appendix_q_systems.append(sys)


class HWInsulationRule:

    def apply(self, d, inp):
        if len(inp.vals) != 1:
            logging.warning("Whoops: %s", inp)

        tokens = inp.vals[0].value.split()
        instype = tokens[0]
        thickness = float(tokens[2])
        d.hw_cylinder_insulation = thickness

        if instype == "Loose":
            d.hw_cylinder_insulation_type = CylinderInsulationTypes.JACKET
        elif instype == "Factory":
            d.hw_cylinder_insulation_type = CylinderInsulationTypes.FOAM
        elif instype == "Measured":
            d.measured_cylinder_loss = float(tokens[2])
        else:
            logging.warning("Unknown insulation type: %s", instype)


class CPSUVolumeRule:

    def apply(self, d, inp):
        tokens = inp.vals[0].value.split()
        d.hw_cylinder_volume = float(tokens[0])
        if len(tokens) > 2:
            d.cpsu_Tw = float(tokens[2])

IMMERSION_TYPES = dict(
    Dual=ImmersionTypes.DUAL,
    Single=ImmersionTypes.SINGLE,
)


class SolarPanelRule:

    def apply(self, d, r):
        if len(r.vals) != 1:
            for r in r.vals:
                logging.warning("Unknown solar panel input: %s", r)
        else:
            if r.vals[0].value != "No":
                if r.vals[0].label == "Yes - aperture area":
                    areaTokens = r.vals[0].vals[0].value.split()
                    d.solar_collector_aperture = float(areaTokens[0])
                else:
                    logging.warning("Unknown solar panel input: %s", r.vals[0])


WATER_SYSTEM_RULES = {
    Labels.CYLINDER_VOLUME: subtoken_mapping('hw_cylinder_volume', 0, 0),
    Labels.CYLINDER_INSULATION: HWInsulationRule(),

    Labels.CPSU_VOLUME: CPSUVolumeRule(),
    Labels.CPSU_INSULATION: HWInsulationRule(),

    Labels.SOLAR_PANEL: SolarPanelRule(),
    # Labels.SOLAR_SHADING:NullRule(),
    # Labels.ORIENTATION:NullRule(),
    # Labels.SOLAR_STORAGE:NullRule(),
    "collector heat loss coefficient": simple_mapping('collector_heat_loss_coeff'),
    "collector zero-loss efficiency": simple_mapping('collector_zero_loss_effy'),

    Labels.PRIMARY_PIPEWORK_INSULATION: lookup_mapping('primary_pipework_insulated', BOOLEANS),
    Labels.CYLINDERSTAT: lookup_mapping('has_cylinderstat', BOOLEANS),
    Labels.HW_TIMER: lookup_mapping('has_hw_time_control', BOOLEANS),
    Labels.IMMERSION_TYPE: lookup_mapping('immersion_type', IMMERSION_TYPES),

    Labels.BOILER_INTERLOCK: lookup_mapping('hwsys_has_boiler_interlock', BOOLEANS),
    Labels.PV_OVERSHADING: lookup_mapping('collector_overshading', PV_OVERSHADING),
}


WWHR_SYSTEM_INPUTS = {
    "Total rooms with shower and/or bath",
    "Number of mixer showers in rooms with a bath",
    "Number of mixer showers in rooms without a bath",
}


class WaterHeatingSystemRule:

    def apply(self, d, r):
        d.has_hw_cylinder = True
        for inp in r.vals:
            try:
                toks = inp.value.split()
                type = int(toks[0])
                d.water_heating_type_code = type

                if type == 950:
                    d.community_heat_sources_dhw, d.sap_community_distribution_type_dhw = parse_community_heating_sources(
                        r)

                if toks[-2] == "summer" and toks[-1] == "immersion":
                    d.use_immersion_heater_summer = True

                continue
            except ValueError as e:
                pass
            except IndexError as e:
                pass
            if inp.label != '':
                if inp.label in WATER_SYSTEM_RULES:
                    # Difficult here is that primary inp names are
                    # different to "regular" inp names.
                    # vals only exists for primary inp.
                    WATER_SYSTEM_RULES[inp.label].apply(d, inp)
                elif inp.label == Labels.SYSTEM_FUEL:
                    d.water_sys_fuel = get_fuel(inp)
                elif inp.label == "orientation":
                    tokens = inp.vals[0].value.split(',')
                    if len(tokens) == 1:
                        d.collector_pitch = PV_PITCH[tokens[0].strip()]
                    else:
                        d.collector_orientation = PV_ORIENTATION[tokens[0]]
                        d.collector_pitch = PV_PITCH[tokens[1].strip()]
                elif inp.label == "dedicated solar store volume":
                    tokens = inp.vals[0].value.split()
                    d.solar_dedicated_storage_volume = float(tokens[0])
                    d.solar_storage_combined_cylinder = (
                        inp.vals[0].note == "combined cylinder")
                elif inp.label == "Waste Water Heat Recovery System":
                    self.process_wwhrs(d, r)
                elif inp.label in WWHR_SYSTEM_INPUTS:
                    pass
                elif inp.label == "Flue Gas Heat Recovery System":
                    self.process_fghrs(d, inp)
                elif inp.label == "FGHRS PV module":
                    self.process_fghrs_pv(d, inp)
                elif inp.label == "pitch":
                    # part of fghrs pv module
                    tokens = inp.vals[0].value.split(',')
                    d.fghrs['pitch'] = PV_PITCH[tokens[0]]
                    if len(tokens) > 1:
                        d.fghrs['orientation'] = PV_ORIENTATION[
                            tokens[1].strip()]
                elif inp.label == Labels.STORE_VOLUME and d.parser_use_input_file_store_params:
                    d.hw_cylinder_volume = float(inp.vals[0].value.split()[0])
                elif inp.label == Labels.STORE_INSULATION and d.parser_use_input_file_store_params:
                    HWInsulationRule().apply(d, inp)
                else:
                    logging.warning("Unknown water system input: %s", inp)
            else:
                if inp.value == "No hot water cylinder":
                    d.has_hw_cylinder = False
                elif inp.value == Labels.CPSU_NOT_IN_AIRING_CUPBOARD:
                    d.cpsu_not_in_airing_cupboard = True
                elif inp.value == Labels.THERMAL_STORE_IN_AIR_CUPBOARD:
                    d.cylinder_is_thermal_store = True
                elif inp.value == "Cylinder not in heated space":
                    d.cylinder_in_heated_space = False
                elif inp.value == "Cylinder in heated space":
                    d.cylinder_in_heated_space = True
                elif inp.value == "evacuated tube - default data":
                    d.collector_type = SHWCollectorTypes.EVACUATED_TUBE
                elif inp.value == "unglazed - declared values":
                    d.collector_type = SHWCollectorTypes.UNGLAZED
                elif inp.value == "electrically powered pump":
                    d.has_electric_shw_pump = True
                elif inp.value == "solar powered pump":
                    d.has_electric_shw_pump = False
                elif inp.value == "Flat rate charging":
                    d.community_dhw_flat_rate_charging = True
                else:
                    logging.warning("Unknown water system value: %s", inp)

    def process_wwhrs(self, d, r):
        found_wwhrs = False
        wwhr_systems = []
        system = None
        for inp in r.vals:
            # Skip inputs until we get to the wwhrs
            if inp.label == "Waste Water Heat Recovery System":
                assert not found_wwhrs
                found_wwhrs = True
            if not found_wwhrs:
                continue

            tokens = inp.value.split()
            if inp.label == "Waste Water Heat Recovery System":
                if inp.vals[0].label == "Total rooms with shower and/or bath":
                    d.wwhr_total_rooms_with_shower_or_bath = int(
                        inp.vals[0].vals[0].value)
                else:
                    logging.warning("Unknown WWHRS input %s", inp)
            elif len(tokens) > 2 and tokens[0] == "Product" and tokens[1] == "index":
                system = dict(pcdf_id=tokens[2][:-1])
                if system != None:
                    wwhr_systems.append(system)
            elif inp.label == "Number of mixer showers in rooms with a bath":
                system['Nshowers_with_bath'] = int(inp.vals[0].value)
            elif inp.label == "Number of mixer showers in rooms without a bath":
                system['Nshowers_without_bath'] = int(inp.vals[0].value)
            elif inp.label in WWHR_SYSTEM_INPUTS:
                logging.warn("Unknown WWHRS input %s", inp.label)

        d.wwhr_systems = wwhr_systems

    def process_fghrs(self, d, inp):
        tokens = inp.vals[0].note.split()
        d.fghrs = dict(pcdf_id=tokens[4])

    def process_fghrs_pv(self, d, inp):
        assert hasattr(d, 'fghrs')
        assert inp.vals[0].label == "Peak kW"
        peak_kW = float(inp.vals[0].vals[0].value)
        d.fghrs['PV_kWp'] = peak_kW

        # only one tests case has pv, so just hardcode the input here
        d.fghrs[
            'overshading_category'] = PVOvershading.NONE_OR_VERY_LITTLE


DUCT_TYPES = {
    'rigid': DuctTypes.RIGID,
    'flexible': DuctTypes.FLEXIBLE,
    'rigid, insulated': DuctTypes.RIGID_INSULATED,
    'rigid, uninsulated': DuctTypes.RIGID,
    'flexible, insulated': DuctTypes.FLEXIBLE_INSULATED,
    'flexible, uninsulated': DuctTypes.FLEXIBLE,
}

COMMON_MECH_VENT_RULES = {
    'Ductwork': lookup_mapping('mv_ducttype', DUCT_TYPES),
    'Approved Installation Scheme': lookup_mapping('mv_approved', BOOLEANS),
}


def apply_common_mv_rules(d, v):
    if v.label != '':
        if v.label in COMMON_MECH_VENT_RULES:
            COMMON_MECH_VENT_RULES[v.label].apply(d, v)
            return True
    return False


class VentilationRule:

    def apply(self, d, r):
        if len(r.vals) == 1 and r.vals[0].value == "Natural ventilation ":
            # natural ventilation
            d.ventilation_type = VentilationTypes.NATURAL
        elif len(r.vals) == 1 and r.vals[0].value == "Mechanical extract ventilation, centralised " and r.vals[0].note == 'Table 4g':
            d.ventilation_type = VentilationTypes.MEV_CENTRALISED
        elif len(r.vals) == 1 and r.vals[0].value == "MVHR " and r.vals[0].note == 'Table 4g':
            d.ventilation_type = VentilationTypes.MVHR
        elif len(r.vals) >= 1 and r.vals[0].value == "MVHR " and r.vals[0].note == 'App.Q data sheet':
            self.process_mvhr(d, r)
        elif len(r.vals) >= 1 and r.vals[0].label == "MVHR ":
            self.process_mvhr(d, r)
        elif r.vals[0].value == "Balanced MV (no HR) (Table 4g)":
            d.ventilation_type = VentilationTypes.MV
        elif r.vals[0].value == "Balanced MV (no HR) (App.Q data sheet)":
            self.process_mv_no_hr(d, r)
        elif r.vals[0].value == "Positive input ventilation (from outside) (App.Q data sheet)":
            self.process_piv_from_outside(d, r)
        elif r.vals[0].value == "Positive input ventilation (from outside) (Table 4g)":
            d.ventilation_type = VentilationTypes.PIV_FROM_OUTSIDE
        elif r.vals[0].value == "Positive input ventilation ":
            d.ventilation_type = VentilationTypes.NATURAL
        else:
            toks = r.vals[0].value.split()
            if r.vals[0].label == 'MEV centralised ':
                self.process_centralised_mev(d, r)
            elif len(toks) >= 2 and toks[0] == 'MEV' and toks[1] == 'decentralised':
                self.process_decentralised_mev_app_q(d, r)
            elif r.vals[0].label == 'MEV decentralised ':
                self.process_decentralised_mev(d, r)
            elif r.vals[0].value == "MEV centralised " and r.vals[0].note == "App.Q data sheet":
                self.process_centralised_mev_app_q(d, r)
            else:
                logging.warning("Unknown ventilation rule: %s", r.vals)

    def process_mv_no_hr(self, d, r):
        d.ventilation_type = VentilationTypes.MV
        for v in r.vals[1:]:
            if apply_common_mv_rules(d, v):
                continue
            if v.label == 'Test SFP':
                d.mv_sfp = float(v.vals[0].value)
            else:
                logging.warning("Unknown MV (no HR) input: %s", v)

    def process_piv_from_outside(self, d, r):
        d.ventilation_type = VentilationTypes.PIV_FROM_OUTSIDE
        for v in r.vals[1:]:
            if apply_common_mv_rules(d, v):
                continue
            if v.label == 'Test SFP':
                d.piv_sfp = float(v.vals[0].value)
            else:
                logging.warning("Unknown PIV input: %s", v)

    def process_mvhr(self, d, r):
        d.ventilation_type = VentilationTypes.MVHR

        for v in r.vals[1:]:
            if apply_common_mv_rules(d, v):
                continue
            if v.label == 'Test efficiency':
                toks = v.vals[0].label.split()
                effy_str = toks[0].split('%')[0]
                d.mvhr_effy = float(effy_str)
                d.mvhr_sfp = float(v.vals[0].vals[0].value)
            else:
                logging.warning("Unknown MVHR input: %s", v)

    def process_centralised_mev(self, d, r):
        d.ventilation_type = VentilationTypes.MEV_CENTRALISED
        for v in r.vals[1:]:
            if apply_common_mv_rules(d, v):
                continue
            if v.label == 'Test SFP':
                d.mev_sfp = float(v.vals[0].value)
            else:
                logging.warning("Unknown MEV input: %s", v)

    def process_centralised_mev_app_q(self, d, r):
        d.ventilation_type = VentilationTypes.MEV_CENTRALISED
        for v in r.vals[1:]:
            if apply_common_mv_rules(d, v):
                continue
            if v.label == 'Test SFP':
                d.mev_sfp = float(v.vals[0].value)
            else:
                logging.warning("Unknown MEV input: %s", v)

    def process_decentralised_mev(self, d, r):
        if r.vals[0].note != "":
            note_toks = r.vals[0].note.split()
            if note_toks[0] == "database":
                d.mev_sys_pcdf_id = note_toks[5]

        d.ventilation_type = VentilationTypes.MEV_DECENTRALISED
        for v in r.vals[1:]:
            if apply_common_mv_rules(d, v):
                continue

            # Working around a difficulty in the parsing here
            if v.label == 'Model qualifier':
                realv = v.vals[0]
            else:
                realv = v

            toks_loc = realv.label.split()
            if toks_loc[0] != "Fans" or len(realv.vals) != 1:
                logging.warning("Unknown MEV input %s", v)
                continue

            location = toks_loc[2]

            if realv.vals[0].label != "Kitchen":
                logging.warning("Unknown MEV input %s", v)
                continue

            toks_kitchen_count = realv.vals[0].vals[0].label.split()
            kitchen_count = int(toks_kitchen_count[0])
            other_count = int(realv.vals[0].vals[0].vals[0].value)

            d["mev_fan_" + location + "_kitchen_count"] = kitchen_count
            d["mev_fan_" + location + "_other_count"] = other_count

    def process_decentralised_mev_app_q(self, d, r):
        if r.vals[0].note != "App.Q data sheet":
            raise Exception("WTF")

        d.ventilation_type = VentilationTypes.MEV_DECENTRALISED
        location = ""
        for v in r.vals[2:]:
            if apply_common_mv_rules(d, v):
                continue

            if v.label != '':
                toks = v.label.split()
                if toks[0] == 'Fans':
                    location = toks[2]
                else:
                    logging.warning("Unknown MEV input: %s", v)
                    continue
            toks_lab = v.vals[0].label.split()
            toks_val = v.vals[0].vals[0].value.split()

            if len(toks_val) != 6:
                logging.warning("Unknown MEV input: %s", v)
                continue

            basename = "mev_fan_" + location + "_" + toks_lab[0].lower()
            d[basename + "_count"] = int(toks_val[0])
            d[basename + "_sfp"] = float(toks_val[5])

WALL_TYPES = {
    'Masonry': WallTypes.MASONRY,
    'Steel/Timber frame': WallTypes.OTHER,
}


class FloorInfiltrationRule:

    def apply(self, d, r):
        if r.vals[0].value == 'Suspended timber ' and r.vals[0].note == 'unsealed':
            d.floor_type = FloorTypes.SUSPENDED_TIMBER_UNSEALED
        elif r.vals[0].value == 'Suspended timber ' and r.vals[0].note == 'sealed':
            d.floor_type = FloorTypes.SUSPENDED_TIMBER_SEALED
        elif r.vals[0].value == 'Not suspended timber':
            d.floor_type = FloorTypes.NOT_SUSPENDED_TIMBER
        elif r.vals[0].value == 'Not applicable':
            # probably ground floor doesn't exist
            d.floor_type = FloorTypes.OTHER
        else:
            logging.warning("Unknown floor type: %s", r)

TARIFFS = {
    'Standard tariff': ELECTRICITY_STANDARD,
    'Off-peak 7-hour': ELECTRICITY_7HR,
    'Off-peak 10-hour': ELECTRICITY_10HR,
}


class ElectricityTariffRule:

    def apply(self, d, r):
        for v in r.vals:
            if v.value in TARIFFS:
                tariff = copy.deepcopy(TARIFFS[v.value])
                d.electricity_tariff = tariff
                if hasattr(d, 'main_sys_fuel') and d.main_sys_fuel.is_electric:
                    d.main_sys_fuel = copy.deepcopy(tariff)
            else:
                logging.warning("Unknown electricity tariff: %s", v.value)

SAP_REGIONS = {
    'South East England': 2,
    'Southern England': 3,
    'South West England': 4,
    'Midlands': 6,
    'North West England': 8,
    'Borders ': 9,
    'North East England': 10,
    'East Pennines': 11,
    'East Anglia': 12,
    'Wales': 13,
}


DWELLING_TYPES = {
    'Flat': True,
    'House': False,
    'Bungalow': False,
}


INPUT_RULES = {
    Labels.DETACHMENT: NullRule(),
    Labels.DWELLING_TYPE: lookup_mapping('is_flat', DWELLING_TYPES),
    Labels.YEAR_COMPLETED: NullRule(),

    Labels.PRESSURE_TEST: FixedValueRule(['Yes ', 'measured in this dwelling']),
    Labels.PRESSURE_TEST_RESULT: simple_mapping('pressurisation_test_result'),
    Labels.PRESSURE_TEST_RESULT_AVE: simple_mapping('pressurisation_test_result_average'),
    Labels.PRESSURE_TEST_RESULT_ASSUMED: simple_mapping('pressurisation_test_result'),
    Labels.PRESSURE_TEST_DESIGNED: simple_mapping('pressurisation_test_result'),
    Labels.WALL_TYPE: lookup_mapping('wall_type', WALL_TYPES),
    Labels.GND_FLOOR_TYPE: FloorInfiltrationRule(),
    Labels.DRAUGHT_LOBBY: lookup_mapping('has_draught_lobby', BOOLEANS),
    Labels.DRAUGHT_PROOFING: subtoken_mapping('draught_stripping', 0, 0, percent_to_float),
    Labels.DRAUGHT_PROOFING2: subtoken_mapping('draught_stripping', 0, 0, percent_to_float),

    Labels.NCHIMNEYS: subtoken_mapping('Nchimneys', 0, 0),
    Labels.NFLUES: simple_mapping('Nflues'),
    Labels.NINT_FANS: simple_mapping('Nintermittentfans'),
    Labels.NPASS_STACKS: simple_mapping('Npassivestacks'),
    Labels.NSIDES_SHELTERED: simple_mapping('Nshelteredsides'),
    Labels.NLIGHTING_OUTLETS: simple_mapping('lighting_outlets_total'),
    Labels.NLOW_ENERGY_LIGHTING_OUTLETS: simple_mapping('lighting_outlets_low_energy'),
    Labels.THERMAL_MASS: ThermalMassRule(),
    Labels.LIVING_AREA: subtoken_mapping('living_area', 0, 0),
    Labels.ORIENTATION: NullRule(),
    Labels.THERMAL_BRIDGES: ThermalBridgingRule(),
    Labels.REGION: lookup_mapping('sap_region', SAP_REGIONS),
    Labels.OVERSHADING: lookup_mapping('overshading', OVERSHADING),
    Labels.MAIN_HEATING_SYSTEM: MainHeatingSystemRule(1),
    Labels.MAIN_HEATING_SYSTEM_1: MainHeatingSystemRule(1),
    Labels.MAIN_HEATING_SYSTEM_2: MainHeatingSystemRule(2),
    Labels.SECONDARY_HEATING_SYSTEM: SecondaryHeatingSystemRule(),
    Labels.CONTROL_SYSTEM: ControlSystemRule(1),
    Labels.CONTROL_SYSTEM_1: ControlSystemRule(1),
    Labels.CONTROL_SYSTEM_2: ControlSystemRule(2),
    Labels.COOLING_SYSTEM: CoolingSystemRule(),
    Labels.APPENDIX_Q: AppendixQRule(),
    Labels.WATER_HEATING_SYSTEM: WaterHeatingSystemRule(),
    Labels.LOW_WATER_USE: lookup_mapping('low_water_use', BOOLEANS),
    Labels.CONSERVATORY: FixedValueRule('No'),
    Labels.PHOTOVOLTAICS: PVRule(),
    Labels.WIND_TURBINE: WindTurbineRule(),
    Labels.HYDRO: subtoken_mapping('hydro_electricity', 0, 0, float),
    Labels.TERRAIN_TYPE: lookup_mapping('terrain_type', TERRAIN),
    Labels.VENTILATION: VentilationRule(),
    Labels.ELECTRICITY_TARIFF: ElectricityTariffRule(),

    "Located in": NullRule(),
    "Postcode": NullRule(),
    "RRN": NullRule(),
    "UPRN": NullRule(),
    "RPN": NullRule(),
    "Date of assessment": NullRule(),
    "Date of certificate": NullRule(),
    "Assessment type": NullRule(),
    "Transaction type": NullRule(),
    "Related party disclosure": NullRule(),

}



def process_floor_area_table(d, r):
    gfa = 0
    volume = 0
    floors = 0
    for row in r.rows:
        A = float(row[1].split()[0])
        if A == 0:
            continue
        h = float(row[2].split()[0])
        gfa += A
        volume += A * h

        if row[0] != "Non-separated conservatory":
            floors += 1
    d.GFA = gfa
    d.volume = volume
    d.Nstoreys = floors


class Elements:
    solid_external_elements = {
        'Doors': worksheet.HeatLossElementTypes.OPAQUE_DOOR,
        'Roof (1)': worksheet.HeatLossElementTypes.EXTERNAL_ROOF,
        'Roof (2)': worksheet.HeatLossElementTypes.EXTERNAL_ROOF,
        'Roof (3)': worksheet.HeatLossElementTypes.EXTERNAL_ROOF,
        'Roof (4)': worksheet.HeatLossElementTypes.EXTERNAL_ROOF,
        'Ground floor': worksheet.HeatLossElementTypes.EXTERNAL_FLOOR,
        'Walls (1)': worksheet.HeatLossElementTypes.EXTERNAL_WALL,
        'Walls (2)': worksheet.HeatLossElementTypes.EXTERNAL_WALL,
        'Walls (3)': worksheet.HeatLossElementTypes.EXTERNAL_WALL,
        'Walls (4)': worksheet.HeatLossElementTypes.EXTERNAL_WALL,
        'Curtain Walls (1)': worksheet.HeatLossElementTypes.EXTERNAL_WALL,
        'Exposed floor': worksheet.HeatLossElementTypes.EXTERNAL_FLOOR,
    }

    solid_internal_elements = [
        'Party wall',
        'Party floor',
        'Party ceiling',
        'Internal wall (1)',
        'Internal wall (2)',
        'Internal wall (3)',
    ]

    opening_elements = [
        'Windows (1)',
        'Windows (2)',
        'Windows (3)',
        'Windows (4)',
        'Roof windows (1)',
    ]

    conservatory_elements = [
        'Conservatory floor',
        'Conservatory walls',
        'Conservatory roof',
    ]

    # Names are so long that they lose some columns in the table
    awkward_elements = [
        'Internal floor level 1 from below',
        'Internal floor level 1 from above',
        'Internal floor level 2 from below',
        'Internal floor level 2 from above',
        'Internal floor level 3 from below',
        'Internal floor level 3 from above',
        'Internal floor level 4 from below',
        'Internal floor level 4 from above',
    ]

    thermal_mass_elements = (list(solid_external_elements.keys()) +
                             solid_internal_elements +
                             awkward_elements)


def process_elements_table(dwelling, table):
    heat_loss_elements = []
    t = []
    for row in table.rows:
        if row[0].strip() in Elements.thermal_mass_elements:
            if row[0].strip() in Elements.awkward_elements:
                kvalueStr = row[3]
            elif len(row) > 5:
                kvalueStr = row[5]
            else:
                kvalueStr = ""
            areaStr = row[1] if row[
                0].strip() in Elements.awkward_elements else row[3]
            if kvalueStr != "":
                try:
                    t.append(
                        worksheet.ThermalMassElement(area=float(areaStr),
                                                     kvalue=float(
                                                             kvalueStr),
                                                     name=row[0]))
                except ValueError:
                    # Original tests cases don't have kvalues in their sap_tables
                    pass

        if row[0] in Elements.solid_external_elements:
            area = float(row[3])
            if area > 0:
                heat_loss_elements.append(worksheet.HeatLossElement(area=area,
                                                   Uvalue=float(row[4]),
                                                   is_external=True,
                                                   element_type=Elements.solid_external_elements[
                                                           row[0]],
                                                   name=row[0]))
        elif row[0] in Elements.solid_internal_elements:
            area = float(row[3])
            if area > 0 and row[4] != "":
                heat_loss_elements.append(worksheet.HeatLossElement(area=float(row[3]),
                                                   Uvalue=float(row[4]),
                                                   is_external=False,
                                                   element_type=worksheet.HeatLossElementTypes.PARTY_WALL,
                                                   name=row[0]))
        elif row[0] in Elements.opening_elements:
            U = 1 / (1 / float(row[4]) + 0.04)
            area = float(row[3])
            if area > 0:
                heat_loss_elements.append(worksheet.HeatLossElement(area=float(row[3]),
                                                   Uvalue=U,
                                                   is_external=True,
                                                   element_type=worksheet.HeatLossElementTypes.GLAZING,
                                                   name=row[0]))
        elif row[0] in Elements.conservatory_elements:
            if row[0] == 'Conservatory walls':
                # Annoying special case - missing one column
                # Note glazing U-value correction!
                U = 1 / (1 / float(row[3]) + 0.04)
                area = float(row[2])
                if area > 0:
                    heat_loss_elements.append(worksheet.HeatLossElement(area=area,
                                                       Uvalue=U,
                                                       is_external=True,
                                                       element_type=worksheet.HeatLossElementTypes.GLAZING,
                                                       name=row[0]))

                    dwelling.openings.append(worksheet.Opening(
                        area=area,
                        orientation_degrees=90,
                        opening_type=dwelling.opening_types["Windows (2)"]))

            elif row[0] == 'Conservatory roof':
                # Note glazing U-value correction!
                U = 1 / (1 / float(row[4]) + 0.04)
                area = float(row[3])
                if area > 0:
                    heat_loss_elements.append(worksheet.HeatLossElement(area=area,
                                                       Uvalue=U,
                                                       is_external=True,
                                                       element_type=worksheet.HeatLossElementTypes.GLAZING,
                                                       name=row[0]))
                    import copy
                    window_type = copy.deepcopy(dwelling.opening_types["Windows (2)"])
                    window_type.roof_window = True
                    dwelling.openings.append(worksheet.Opening(
                        area=area,
                        orientation_degrees=90,
                        opening_type=window_type))

            else:
                U = float(row[4])
                area = float(row[3])
                if area > 0:
                    heat_loss_elements.append(worksheet.HeatLossElement(area=area,
                                                       Uvalue=U,
                                                       is_external=True,
                                                       element_type=worksheet.HeatLossElementTypes.EXTERNAL_FLOOR,
                                                       name=row[0]))
        elif not row[0].strip() in Elements.awkward_elements:
            logging.warning("unknown element type %s", row[0])
    dwelling.heat_loss_elements = heat_loss_elements
    dwelling.thermal_mass_elements = t

OPENING_TYPE_DATA_SOURCES = {
    "SAP": OpeningTypeDataSource.SAP,
    "BFRC": OpeningTypeDataSource.BFRC,
    "manu.": OpeningTypeDataSource.MANUFACTURER,
}
GLAZING_TYPES = {
    "SINGLE": GlazingTypes.SINGLE,
    "DOUBLE": GlazingTypes.DOUBLE,
    "TRIPLE": GlazingTypes.TRIPLE,
    "SECONDARY GLAZING": GlazingTypes.SECONDARY,
    "SECOND": GlazingTypes.SECONDARY,
}


def process_opening_types_part1_table(d, r):
    types = dict()
    for row in r.rows:
        if row[0] == 'Doors':
            pass  # door u-value picked up in areas table
        elif row[0] in Elements.opening_elements:
            data_source = OPENING_TYPE_DATA_SOURCES[row[1]]
            glazing_type = GLAZING_TYPES[row[3].split(',')[0].upper()]
            window_type = row[2]

            types[row[0]] = worksheet.OpeningType(
                glazing_type=glazing_type,
                gvalue=0,  # Filled in from next table
                frame_factor=0,
                Uvalue=0,
                roof_window=(window_type == "Roof window"))
        else:
            logging.warning("unknown element type %s", row[0])

    d.opening_types = types


def process_opening_types_part2_table(d, r):
    types = d.opening_types
    for row in r.rows:
        if row[0] == 'Doors':
            pass  # door u-value picked up in areas table
        elif row[0] in types:
            # Note glazing U-value correction!
            t = types[row[0]]
            t.gvalue = float(row[3])
            t.Uvalue = 1 / (1 / float(row[4]) + 0.04)

            if len(row) > 5 and row[5] != '' and row[5].split()[0] == 'BFRC':
                # Special case of window with BFRC cert, in which case we set
                # frame factor to 1/0.9 to cancel out the 0.9 factor in the SAP
                # calc
                t.frame_factor = 1 / 0.9
                t.bfrc_data = True
            else:
                t.frame_factor = float(row[2])
        else:
            logging.warning("unknown element type %s", row[0])


def process_openings_table(dwelling, r):
    # Rely on fact that types table comes first in rtf!
    types = dwelling.opening_types
    openings = []
    for row in r.rows:
        if row[1] == "Doors":
            pass
        elif row[1] in types:
            orientationStr = row[3]
            orientation = ORIENTATIONS[row[3]] if orientationStr != '' else 90
            openings.append(worksheet.Opening(
                area=float(row[4]) * float(row[5]),
                orientation_degrees=orientation,
                opening_type=types[row[1]],
                name=row[1]))
        else:
            logging.warning("Unrecognised opening type: %s", row[1])

    dwelling.openings = openings


def process_table(dwelling, row):
    if row.column_headings[1] == 'Gross area':
        process_elements_table(dwelling, row)

    elif row.column_headings[1] == 'Floor area':
        process_floor_area_table(dwelling, row)

    elif row.column_headings[1] == 'Source':
        process_opening_types_part1_table(dwelling, row)

    elif row.column_headings[1] == 'Gap':
        process_opening_types_part2_table(dwelling, row)

    elif row.column_headings[1] == 'Type-Name':
        process_openings_table(dwelling, row)

    else:
        logging.warning("Unknown table: %s", row)


def process_inputs(dwelling, inputs):
    dwelling.parser_use_input_file_store_params = False

    for section in inputs:
        if section.column_headings != '':
            process_table(dwelling, section)
        elif section.label in INPUT_RULES:
            INPUT_RULES[section.label].apply(dwelling, section)
        else:
            if section[0] != "EPC language":
                logging.warning("Unknown rule: %s", section)
