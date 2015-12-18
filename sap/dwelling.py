from .utils import ALL_PARAMS, CALC_STAGE
from .sap_constants import IGH_HEATING, T_EXTERNAL_HEATING, WIND_SPEED
from .fuels import Fuel, ElectricityTariff


class Dwelling(dict):
    def __init__(self, **kwargs):
        # allow attributes to be sorted
        super().__init__(**kwargs)
        self['wind_speed'] = self.wind_speed = WIND_SPEED

        # apply_sap_hardcoded_values here to avoid setting attrs outside of __init__
        self.Texternal_heating = T_EXTERNAL_HEATING
        self.Igh_heating = IGH_HEATING
        self.living_area_Theating = 21
        self.Tcooling = 24

        #TODO could just use a Dict, don't really need CalculationResults
        self.results = dict()
        self.er_results = dict()
        self.report = CalculationReport(self)

    def __getattr__(self, item):
        """
        Return own attribute, but if that is missing, return it from the results instead...

        FIXME: overloading getattr is fragile and somewhat opaque, prefer getitem
        """
        try:
            return self[item]
        except KeyError:
            try:
                return self.__dict__[item]
            except KeyError:
                raise AttributeError(item)

    def __str__(self):
        s = ''
        for k, v in self.items():
            s += '{} - {} \n'.format(k, v)
        return s

    def __repr__(self):
        return self.__str__()

    # @property
    # def er_results(self):
    #     return self.results
    #
    # @er_results.setter
    # def er_results(self, value):
    #     self.results = value


# TODO: could probably rather subclass Dwelling
# FIXME: seems that worksheet in any case depends on the dwelling object having report object. May better to just merge this into Dwelling
class DwellingResultsWrapper(Dwelling):
    """
    This looks like a dwelling but redirects 'setter' operations
    to a 'results' internal object. This is used to perform different variations of
    SAP calculation on a dwelling and then assign only the results of those to the original
    dwelling with an appropriate prefix, e.g. der_results, fee_results etc...

    The idea being that the original dwelling is 'frozen' and some point in the calculation
    """
    def __init__(self, dwelling):
        super().__init__(**dwelling)
        self.results = dict()  # just use a Dict, don't really need CalculationResults for now
        self.results.report = CalculationReport(self)
        self.report = self.results.report

    def __setattr__(self, key, value):
        # FIXME: hack to allow using setattr without messing with the attrs set in __init__. Would be better to access results explicitly
        # FIXME: This is really fragile...
        if key not in ['dwelling', 'results', 'report']:
            self.results[key] = value
        else:
            self.__dict__[key] = value

    def __getattr__(self, item):
        """
        return from results if k exists, otherwise return from wrapped
        dwelling

        FIXME: overloading getattr is fragile and somewhat opaque, prefer getitem
        """
        try:
            return self[item]
        except KeyError:
            try:
                return self.results[item]
            except KeyError:
                raise AttributeError(item)


# class CalculationResults(dict):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)


# TODO IDEA: instead of building strings, build a report as a data tree which can be formatted later
class CalculationReport(object):
    def __init__(self, dwelling):
        self.dwelling = dwelling
        self.text = ""

    def start_section(self, number, title):
        title_str = "%s %s\n" % (number, title)
        self.text += "\n"
        self.text += title_str
        self.text += "=" * len(title_str) + "\n"

    def add_annotation(self, label):
        self.text += "%s\n" % (label,)

    def add_single_result(self, label, code, values):
        self.add_monthly_result(label, code, values)

    def add_monthly_result(self, label, code, values):
        if code is not None:
            self.text += "%s %s (%s)\n" % (label, values, code)
        else:
            self.text += "%s %s\n" % (label, values)

    def build_report(self):
        dwelling = self.dwelling

        self.start_section("2", "Ventilation rate")
        self.add_single_result(
            "Infiltration due to chimneys, etc", 8, dwelling.inf_chimneys_ach)

        if dwelling.get('pressurisation_test_result'):
            self.add_annotation("Using pressure tests")
        elif dwelling.get('pressurisation_test_result_average'):
            self.add_annotation("Using pressure tests for average dwelling")
        else:
            self.add_annotation("Using calculated infiltration rate")
        #
        #     base_infiltration_rate=dwelling.pressurisation_test_result/20.+inf_chimneys_ach
        # elif hasattr(dwelling,'pressurisation_test_result_average'):
        #     base_infiltration_rate=(dwelling.pressurisation_test_result_average+2)/20.+inf_chimneys_ach
        # else:
        #     additional_infiltration=(dwelling.Nstoreys-1)*0.1
        #     draught_infiltration=0.05 if not dwelling.has_draught_lobby else 0
        #     dwelling.window_infiltration=0.25-0.2*dwelling.draught_stripping
        #
        #     base_infiltration_rate=( additional_infiltration
        #

        self.add_single_result(
            "Infiltration rate", 18, dwelling.base_infiltration_rate)
        self.add_monthly_result("Effective ach", 25, dwelling.infiltration_ach)

        self.start_section("3", "Heat losses and heat loss parameter")
        self.add_single_result("Thermal bridging", 36, dwelling.h_bridging)
        self.add_single_result(
            "Fabric heat loss", 37, dwelling.h_fabric + dwelling.h_bridging)
        self.add_monthly_result("Ventilation loss", 38, dwelling.h_vent)
        self.add_monthly_result("Heat transfer coeff", 39, dwelling.h)
        self.add_monthly_result("HLP", 40, dwelling.hlp)
        self.add_single_result(
            "Thermal mass parameter", 35, dwelling.thermal_mass_parameter)

        self.start_section("4", "Water heating")
        self.add_monthly_result("Daily water use", 44, dwelling.hw_use_daily)
        self.add_monthly_result("Energy content", 45, dwelling.hw_energy_content)
        self.add_monthly_result("Distribution loss", 46, dwelling.distribution_loss)

        is_pou_heating = (dwelling.get('instantaneous_pou_water_heating') and
                          dwelling.instantaneous_pou_water_heating)
        has_measured_loss = (dwelling.get('measured_cylinder_loss') and
                             dwelling.measured_cylinder_loss is not None)
        if not is_pou_heating and not has_measured_loss and dwelling.get('hw_cylinder_volume', False):
            self.add_single_result(
                "Cylinder volume", None, dwelling.hw_cylinder_volume)
            self.add_single_result(
                "Storage loss factor", None, dwelling.storage_loss_factor)
            self.add_single_result("Volume factor", None, dwelling.volume_factor)
            self.add_single_result(
                "Temperature factor", None, dwelling.temperature_factor)

        self.add_monthly_result("Storage loss", 57, dwelling.storage_loss)
        self.add_monthly_result(
            "Primary circuit loss", 59, dwelling.primary_circuit_loss)
        self.add_monthly_result("Combi loss", 61, dwelling.combi_loss_monthly)
        self.add_monthly_result("Solar input", 63, dwelling.input_from_solar)
        self.add_monthly_result("WWHR savings", 63, dwelling.savings_from_wwhrs)
        self.add_monthly_result("FGHR savings", 63, dwelling.savings_from_fghrs)
        self.add_monthly_result(
            "Water heat output", 64, dwelling.output_from_water_heater)

        self.start_section("5", "Internal gains")
        self.add_monthly_result("Metabolic", "66", dwelling.met_gain)
        self.add_monthly_result("Lighting", "67", dwelling.light_gain)
        self.add_monthly_result("Appliances", "68", dwelling.appliance_gain)
        self.add_monthly_result("Cooking", "69", dwelling.cooking_gain)
        self.add_monthly_result("Pumps, fans", "70", dwelling.pump_gain)
        self.add_monthly_result("Losses", "71", dwelling.losses_gain)
        self.add_monthly_result("Water heating", "72", dwelling.water_heating_gains)
        self.add_monthly_result("Total", "73", dwelling.total_internal_gains)

        self.start_section("6", "Solar gains")
        self.add_monthly_result("Solar gains", "83", dwelling.solar_gain_winter)
        self.add_monthly_result("Total gains", "84", dwelling.winter_heat_gains)

        self.start_section(7, "Mean internal temperature")
        self.add_single_result(
            "Responsiveness", None, dwelling.heating_responsiveness)
        self.add_single_result(
            "Control type, system 1", None, dwelling.heating_control_type_sys1)
        if dwelling.main_heating_fraction < 1:
            self.add_single_result(
                "Control type, system 2", None, dwelling.heating_control_type_sys2)
        res = dwelling.heat_calc_results
        self.add_monthly_result("tau", None, res['tau'])
        self.add_monthly_result("alpha", None, res['alpha'])
        self.add_monthly_result("External temperature", None, res['Texternal'])
        self.add_monthly_result(
            "Living area utilisation factor", 86, res['util_living'])
        self.add_monthly_result(
            "Living area mean temperature", 87, res['Tmean_living_area'])
        self.add_monthly_result(
            "Rest of house mean temperature", 90, res['Tmean_other'])
        self.add_single_result(
            "Living area fraction", 91, dwelling.living_area_fraction)
        self.add_single_result(
            "Temperature adjustment", None, dwelling.temperature_adjustment)
        self.add_monthly_result("Dwelling mean temperature", 93, res['Tmean'])

        if not dwelling.get('sys1_space_effy'):
            # Must be FEE calc, exit here
            return

        self.start_section("8c", "Space cooling requirement")

        self.start_section("9a", "Energy requirements")
        self.add_single_result("Fraction of space heat from secondary",
                               "201", 1 - dwelling.fraction_of_heat_from_main)
        self.add_single_result(
            "Fraction of space heat from main systems", "202", dwelling.fraction_of_heat_from_main)
        self.add_single_result(
            "Fraction of main heating from main system 2", "203", dwelling.main_heating_2_fraction)
        self.add_single_result("Fraction of total space heating from main system 1",
                               "204", dwelling.fraction_of_heat_from_main * dwelling.main_heating_fraction)
        self.add_single_result("Fraction of total space heating from main system 2",
                               "205", dwelling.fraction_of_heat_from_main * dwelling.main_heating_2_fraction)

        self.add_single_result(
            "Efficiency of main heating system 1", "206", dwelling.sys1_space_effy)
        if dwelling.get('sys2_space_effy'):
            self.add_single_result(
                "Efficiency of main heating system 2", "207", dwelling.sys2_space_effy)
        if dwelling.get('secondary_space_effy'):
            self.add_single_result(
                "Efficiency of secondary heating system", "208", dwelling.secondary_space_effy)
        self.add_monthly_result(
            "Space heating requirement", "98", dwelling.Q_required)
        self.add_monthly_result(
            "Space heating fuel (main heating system 1)", "211", dwelling.Q_spaceheat_main)
        self.add_monthly_result(
            "Space heating fuel (main heating system 2)", "213", dwelling.Q_spaceheat_main_2)
        self.add_monthly_result(
            "Space heating fuel (secondary)", "215", dwelling.Q_spaceheat_secondary)

        self.add_monthly_result(
            "Water heating efficiency", "217", dwelling.water_effy)
        self.add_monthly_result("Water heating fuel", "219", dwelling.Q_waterheat)

        self.start_section("10", "Fuel Use, Emissions, Primary Energy")
        end_uses = [
            "water",
            "water_summer_immersion",
            "heating_main",
            "community_elec_credits",
            "community_distribution",
            "negative_community_emissions_correction",
            "heating_main_2",
            "heating_secondary",
            "cooling",
            "fans_and_pumps",
            "mech_vent_fans",
            "lighting",
            "appliances",
            "cooking",
            "pv",
            "wind",
            "hydro",
            "appendix_q_generated",
            "appendix_q_used",
        ]

        for label in end_uses:
            if dwelling.get("energy_use_%s" % label):
                energy = dwelling["energy_use_%s" % label]
                emissions = dwelling["emissions_%s" % label]
                cost = dwelling["cost_%s" % label]
                primary_energy = dwelling["primary_energy_%s" % label]
                self.add_single_result(label, None, "%f | %f | %f | %f" %
                                       (energy, emissions, cost, primary_energy))

        self.start_section("L", "Appendix L - Lighting")
        self.add_single_result(
            "Low energy bulb ratio", None, dwelling.low_energy_bulb_ratio)
        self.add_single_result("C1", "L2", dwelling.lighting_C1)
        self.add_single_result("C2", "L3", dwelling.lighting_C2)
        self.add_single_result("GL", "L5", dwelling.lighting_GL)
        self.add_single_result(
            "Annual consumption", "L8", dwelling.annual_light_consumption)

    def __str__(self):
        return self.text


def log_dwelling_params(param_set, prefix, k, v):
    """
    Customized logging of SAP objects
    """
    param_set.add(prefix + k)

    if isinstance(v, str):
        return

    if k in ["opening_types"]:
        # This is a dict, but the keys aren't interesting (e.g. things
        # like Windows (1), Windows (2), etc)
        for entry in v.values():
            log_dwelling_params(param_set, prefix, "_" + k, entry)
        return

    try:
        # If this is a dict,dump the entries
        for key, value in v.items():
            log_dwelling_params(param_set, prefix + k + ".", key, value)
        return
    except AttributeError:
        pass

    try:
        # If this is a list,dump the entries
        for entry in v:
            log_dwelling_params(param_set, prefix, k, entry)
        return
    except TypeError:
        pass

    try:
        if (isinstance(v, Fuel) or
                isinstance(v, ElectricityTariff)):
            return
        # If this is an object, dump it's dict
        for key, value in v.__dict__.items():
            log_dwelling_params(param_set, prefix + k + ".", key, value)
        return
    except AttributeError:
        pass


def log_dwelling(dwelling, prefix=""):
    """
    Log all the dwelling parameters
    :param dwelling:
    :param prefix:
    :return:
    """
    # FIXME dodgy use of global Calc_stage
    param_set = ALL_PARAMS[CALC_STAGE]

    for k, v in dwelling.items():
        # if k != "_attrs":
        pass
        # log_sap_obj(param_set, prefix, k, v)


class ParamTrackerDwelling(Dwelling):
    def __init__(self):
        super(ParamTrackerDwelling, self).__init__()
        self.calc_stage = 1

    # def __setattr__(self, k, v):
    #     """if k!="ordered_attrs":
    #         if isinstance(v,dict):
    #             v=TrackedDict(v,k)
    #
    #         all_params[calc_stage].add(k)
    #         try:
    #             for key in v.keys():
    #                 all_params[calc_stage].add(k+"."+key)
    #         except AttributeError:
    #             pass"""
    #
    #     Dwelling.__setattr__(self, k, v)

    # TODO: overload dwelling's setitem/getitem (at least for results) so that you can track changes for each stage...

    def next_stage(self):
        self.calc_stage += 1


        # FIXME: find out if this is actually used anywhere...
