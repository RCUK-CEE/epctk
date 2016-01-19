import logging

from .elements import FuelTypes


class SchemaValidator:

    def __init__(self):
        self.rules = group()

    def addRule(self, rule):
        self.rules.rules.append(rule)

    def validate(self, dwelling):
        passed, msg = self.rules.validate(dwelling)

        if not passed:
            for m in msg:
                logging.error(m)

        return passed


class required:
    """
    Checks that specified key exists in dwelling
    """

    def __init__(self, name, vtype):
        self.name = name
        self.vtype = vtype

    def validate(self, dwelling):
        if not dwelling.get(self.name):
            return False, ("Missing required attribute %s" % (self.name,),)
        else:
            try:
                val = dwelling[self.name]
                self.vtype(val)
                print(("ok ", self.name))
            except:
                return False, ("Bad type for attribute %s: %s" % (self.name, val),)
        return True, []

# synonym
attribute = required


class required_if:

    """
    Rules that are required if condition evaluates to true
    """

    def __init__(self, condition, *rules):
        self.group = group(*rules)
        self.condition = condition

    def validate(self, dwelling):
        if self.condition(dwelling):
            return self.group.validate(dwelling)
        else:
            return True, []


class required_if_and_only_if:
    """
    Rules that are required if and only if condition evaluates to true

    !!! Not quite right here, because if you have a partially present
        group when you shouldn't have the group at all then it will
        still pass
    """

    def __init__(self, condition, *rules):
        self.group = group(*rules)
        self.condition = condition

    def validate(self, dwelling):
        if self.condition(dwelling):
            return self.group.validate(dwelling)
        else:
            passed, msgs = self.group.validate(dwelling)
            if not passed:
                return True, []
            else:
                # !!! Better message required
                return False, ["Got a group that I shouldn't have got"]


class group:

    """ 
    All sub rules must validate 
    """

    def __init__(self, *args):
        self.rules = list(args)

    def validate(self, dwelling):
        passed = True
        msgs = []
        for r in self.rules:
            thispassed, newmsgs = r.validate(dwelling)
            if not thispassed:
                passed = False
                msgs.extend(newmsgs)
        return passed, msgs


class optional_group:

    """
    Either all sub rules must validate or no sub rules may validate
    """

    def __init__(self, *args):
        self.rules = list(args)

    def validate(self, dwelling):
        passed = 0
        msgs = []
        for r in self.rules:
            thispassed, newmsgs = r.validate(dwelling)
            if not thispassed:
                msgs.extend(newmsgs)
            else:
                passed += 1

        if passed == len(self.rules):
            # group present and ok
            return True, []
        elif passed == 0:
            # group completely missing, ok
            return True, []
        else:
            return False, msgs
        return passed, msgs


class one_of:

    """
    Only one subrule is allowed to validate
    """

    def __init__(self, label, *args):
        self.label = label
        self.rules = list(args)

    def validate(self, dwelling):
        passed = 0
        for r in self.rules:
            thispassed, newmsgs = r.validate(dwelling)
            if thispassed:
                passed += 1

        if passed == 0:
            return False, ["No matches found for %s" % (self.label,), ]
        elif passed > 1:
            return False, ["More than one match found for %s" % (self.label,), ]
        else:
            return True, []


def main_heating_is_oil_boiler(dwelling):
    # !!! need to also tests that system is a boiler - oil room heaters
    # !!! don't have a pump
    return dwelling.main_sys_fuel.type() == FuelTypes.OIL


def main_heating_uses_table_4d(dwelling):
    # !!! The following use 4d:
    # - boilers from table 4b
    # - some heat pumps from table 4a
    # - boilers from pcdf
    return True


def main_heating_is_gas_or_oil_boiler(dwelling):
    # !!!
    return True


def has_second_main_heating(dwelling):
    return hasattr(dwelling, "main_sys_2_fuel")

ATTRIBUTES = [
    required("GFA", float),
    required("volume", float),
    required("Nstoreys", int),
    required("thermal_mass_parameter", float),
    required("Uthermalbridges", float),
    required("low_water_use", bool),
    required("sap_region", int),
    required("overshading", int),  # enum

    required("ventilation_type", int),  # enum
    required("Nflues", int),
    required("Nintermittentfans", int),
    required("Nchimneys", int),
    required("Npassivestacks", int),
    required("Nshelteredsides", int),
    one_of("air tightness",
           attribute("pressurisation_test_result_average", float),
           attribute("pressurisation_test_result", float),
           group(
               attribute("has_draught_lobby", bool),
               attribute("floor_type", int),  # enum
               attribute("draught_stripping", float),
               attribute("wall_type", int))),  # enum

    one_of("low energy lighting",
           group(
               attribute("lighting_outlets_low_energy", int),
               attribute("lighting_outlets_total", int)),
           attribute("low_energy_bulb_ratio", float)),

    one_of("living area",
           attribute("living_area_fraction", float),
           attribute("living_area", float)),

    one_of("main heating type",
           attribute("main_heating_pcdf_id", int),
           attribute("main_heating_type_code", int)),
    # attribute("main_sys_fuel",int), # Errr?
    attribute("control_type_code", int),
    required_if_and_only_if(
        main_heating_is_oil_boiler,
        attribute("main_heating_oil_pump_inside_dwelling", bool)),
    # required_if_and_only_if(
    #    main_heating_uses_table_4d,
    # attribute("heating_emitter_type",int)), # enum
    # required_if_and_only_if(
    #    main_heating_is_gas_or_oil_boiler,
    #    attribute("sys1_has_boiler_interlock",bool)),
    required_if_and_only_if(
        has_second_main_heating,
        attribute("main_heating_fraction", float)),

    # optional_group(
    #    attribute("secondary_heating_type_code",int),
    # attribute("secondary_sys_fuel",int)), # errr?

    required("water_heating_type_code", int),
    # required("water_sys_fuel",int), # err

    optional_group(
        attribute("use_immersion_heater_summer", bool)),
    required_if(
        lambda d: hasattr(
            d, "use_immersion_heater_summer") and d.use_immersion_heater_summer,
        attribute("immersion_type", int)),  # enum

    optional_group(
        # attribute("hw_cylinder_type",int), # enum
        one_of(
            attribute("measured_cylinder_loss", float),
            group(
                attribute("hw_cylinder_volume", float),
                attribute("hw_cylinder_insulation_type", int),  # enum
                attribute("hw_cylinder_insulation", float)))),
    #        attribute("cylinder_in_heated_space",bool),
    #        attribute("has_cylinderstat",bool),
    #        attribute("has_hw_time_control",bool),
    #        attribute("primary_pipework_insulated",bool)),

    optional_group(
        # !!! Also need orientation inputs
        attribute("PV_kWp", float),
        attribute("pv_overshading_category", int)),

    optional_group(
        attribute("hydro_electricity", float)),

    optional_group(
        attribute("wind_turbine_hub_height", float),
        attribute("N_wind_turbines", int),
        attribute("wind_turbine_rotor_diameter", float)),
    required("terrain_type", int),  # enum - but only really required
    # when there is a wind turbine?

    optional_group(
        one_of("cooled area",
               attribute("cooled_area", float),
               attribute("fraction_cooled", float)),
        attribute("cooling_compressor_control", str),
        attribute("cooling_packaged_system", bool),
        attribute("cooling_energy_label", str),
    ),
]


def build_input_schema():
    s = SchemaValidator()
    for rule in ATTRIBUTES:
        s.addRule(rule)

    return s

input_schema = build_input_schema()


def validate(dwelling):
    return input_schema.validate(dwelling)
