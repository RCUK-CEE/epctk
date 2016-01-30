import logging

from epctk.elements import FuelTypes


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
            return False, ("Missing required key %s" % (self.name,),)
        else:
            try:
                val = dwelling[self.name]
                self.vtype(val)
                print(("ok ", self.name))
            except TypeError:
                return False, ("Bad type for key %s: %s" % (self.name, val),)
        return True, []

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
           required("pressurisation_test_result_average", float),
           required("pressurisation_test_result", float),
           group(
               required("has_draught_lobby", bool),
               required("floor_type", int),  # enum
               required("draught_stripping", float),
               required("wall_type", int))),  # enum

    one_of("low energy lighting",
           group(
               required("lighting_outlets_low_energy", int),
               required("lighting_outlets_total", int)),
           required("low_energy_bulb_ratio", float)),

    one_of("living area",
           required("living_area_fraction", float),
           required("living_area", float)),

    one_of("main heating type",
           required("main_heating_pcdf_id", int),
           required("main_heating_type_code", int)),
    # required("main_sys_fuel",int), # Errr?
    required("control_type_code", int),
    required_if_and_only_if(
        main_heating_is_oil_boiler,
        required("main_heating_oil_pump_inside_dwelling", bool)),
    # required_if_and_only_if(
    #    main_heating_uses_table_4d,
    # required("heating_emitter_type",int)), # enum
    # required_if_and_only_if(
    #    main_heating_is_gas_or_oil_boiler,
    #    required("sys1_has_boiler_interlock",bool)),
    required_if_and_only_if(
        has_second_main_heating,
        required("main_heating_fraction", float)),

    # optional_group(
    #    required("secondary_heating_type_code",int),
    # required("secondary_sys_fuel",int)), # errr?

    required("water_heating_type_code", int),
    # required("water_sys_fuel",int), # err

    optional_group(
        required("use_immersion_heater_summer", bool)),
    required_if(
        lambda d: hasattr(
            d, "use_immersion_heater_summer") and d.use_immersion_heater_summer,
        required("immersion_type", int)),  # enum

    optional_group(
        # required("hw_cylinder_type",int), # enum
        one_of(
            required("measured_cylinder_loss", float),
            group(
                required("hw_cylinder_volume", float),
                required("hw_cylinder_insulation_type", int),  # enum
                required("hw_cylinder_insulation", float)))),
    #        required("cylinder_in_heated_space",bool),
    #        required("has_cylinderstat",bool),
    #        required("has_hw_time_control",bool),
    #        required("primary_pipework_insulated",bool)),

    optional_group(
        # !!! Also need orientation inputs
        required("PV_kWp", float),
        required("pv_overshading_category", int)),

    optional_group(
        required("hydro_electricity", float)),

    optional_group(
        required("wind_turbine_hub_height", float),
        required("N_wind_turbines", int),
        required("wind_turbine_rotor_diameter", float)),
    required("terrain_type", int),  # enum - but only really required
    # when there is a wind turbine?

    optional_group(
        one_of("cooled area",
               required("cooled_area", float),
               required("fraction_cooled", float)),
        required("cooling_compressor_control", str),
        required("cooling_packaged_system", bool),
        required("cooling_energy_label", str),
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
