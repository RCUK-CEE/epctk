from .constants import (IGH_HEATING, T_EXTERNAL_HEATING, WIND_SPEED,
                        LIVING_AREA_T_HEATING, COOLING_BASE_TEMPERATURE)
from .fuels import Fuel, ElectricityTariff


class Dwelling(dict):
    """
    Dwelling Class

    Dict subclass for storing dwelling data. Is a dict which makes
    key/value pair accessible as attributes for readability and compatibility
    with code base.

    .. todo:
      This is somewhat error prone/sensitive to changes, and makes it harder
      for tools like IDE's to check the types/usage of dwelling properties.
      Would be preferable to list all the required and optional dwelling properties
      somewhere, making the configuration much more explicit.

    """
    # apply_sap_hardcoded_values here to avoid setting attrs outside of __init__
    wind_speed = WIND_SPEED
    Texternal_heating = T_EXTERNAL_HEATING
    Igh_heating = IGH_HEATING
    living_area_Theating = LIVING_AREA_T_HEATING
    Tcooling = COOLING_BASE_TEMPERATURE

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # TODO: allow attributes to be sorted. Could be done by subclassing ordereddict
        # IMPORTANT: best to only set values explicitly as dict values here
        self['use_pcdf_fuel_prices'] = True
        self['results'] = dict() #needs to be defined here to avoid circular issues between getatte and getitem
        self['report'] = CalculationReport(self)

    def __setattr__(self, key, value):
        """
        Override setting attributes so that their values go into the dictionary,
        thereby standardising on 'dictionary style' access

        Args:
            key:
            value:

        Returns:

        """
        self[key] = value

    def __getattr__(self, item):
        """
        Make dict keys accessible as attributes. If an item is not in the
        dict, return it from the object `__dict__`

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


class DwellingResults(Dwelling):
    """
    Dwelling Results allows you to "freeze" a dwelling configuration.
    Any changes made, such as setting new attributes, will be stored in the
    "results" dict making it easy to retreive only the changed values later
    in the process.

    This is used to perform different variations of
    SAP calculation on a dwelling and then assign only the results of those to the original
    dwelling with an appropriate prefix, e.g. der_results, fee_results etc...

    """
    def __init__(self, dwelling):
        super().__init__(**dwelling)

    def __setattr__(self, key, value):
        """
        Override the set attribute so that everything set AFTER wrapping
        a dwelling in a dwellingResults is set on the `results` dict instead
        of the 'main' dict. This way you can retrieve only the 'changed' values
        by accessing `results`

        Args:
            key:
            value:

        """
        self['results'][key] = value

    def __getattr__(self, item):
        """
        Return value from `results`, if missing return it from the Dwelling's original
        dict, then try the original attributes

        Args:
            item: name of item to retrieve
        Returns:
            item
        """
        try:
            return self['results'][item]
        except KeyError:
            try:
                return self[item]
            except KeyError:
                try:
                    return self.__dict__[item]
                except KeyError:
                    raise AttributeError(item)

    def __getitem__(self, item):
        if item == 'results':
            return super().__getitem__('results')

        # if item in super().__getitem__('results'):
        #     return super().__getitem__('results')[item]
        # else:
        #     return super().__getitem__(item)

        try:
            return super().__getitem__('results')[item]
        except KeyError:
            try:
                return super().__getitem__(item)
            except KeyError:
                return self.__dict__[item]


    def __setitem__(self, key, value):
        self['results'][key] = value

    def get(self, key, default=None):
        """
        Override get to return from results first.
        Important since otherwise if you overwrite an existing key from Dwelling
        in Dwelling Results, only the original will be returned with get()

        Args:
            key:
            default:

        Returns:

        """
        try:
            return self['results'][key]
        except KeyError:
            try:
                return self[key]
            except KeyError:
                try:
                    return self.__dict__[key]
                except KeyError:
                    return default




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
        if not is_pou_heating and not has_measured_loss and dwelling.get('hw_cylinder_volume') is not None:
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

    Args:
        param_set:
        prefix:
        k:
        v:
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
