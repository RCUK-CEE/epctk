"""
Convert RdSAP inputs to SAP inputs by looking
up missing data from RdSAP tables


"""
import math

from ..elements import DwellingType
from ..elements.geographic import Country, country_from_region

from ..tables.tables_appendix_s import AgeBand, table_s1_age_band, num_sheltered_sides, lookup_wall_u_values, \
    table_s3_wall_thickness, n_fans_and_vents, correct_floor_type, has_draught_lobby, percent_draught_stripping, \
    table_s16_living_area_fraction, has_hw_time_control, table_s17_water_cylinder, primary_pipework_insulated, \
    cylinder_insulation_properties

from ..utils import SAPInputError


def get_country(dwelling):
    """
    Dwelling object should have country code in ISO 3166-2:GB format
    Or a region code from which the country is derived. It might be
    necessary to determine the region from the post code before
    submitting the values.

    Args:
        dwelling:

    Returns:
        country from ISO country code, by default returns England
    """
    country_code = dwelling.get("country_code")
    region_code = dwelling.get("region")

    if country_code is not None:
        country = Country.from_iso(country_code)

    elif region_code is not None:
        country = country_from_region(region_code)
    else:
        raise SAPInputError("No region or country code for the given dwelling")

    #RdSAP treats England and Wales as one
    if country == Country.Wales:
        country = Country.England

    return country



def configure_rdsap(dwelling):
    """

    Args:
        dwelling (dict): rdsap inputs

    Returns:

    """
    # TODO: split this up later...
    # perform lookup for missing data
    # Problem: how to know what data is missing??

    dwelling_type = dwelling.get("dwelling_type")

    dwelling_type = DwellingType.from_string(dwelling_type)

    country = get_country(dwelling)

    age_band = dwelling.get("age_band")
    if not age_band and dwelling.get("age"):
        age_band = table_s1_age_band(dwelling['age'], country)
    else:
        age_band = AgeBand(age_band)

    n_rooms = dwelling['n_rooms']

    # Apply Table S5 for misc corrections
    n_fans_vents = dwelling.get('Nfansandpassivevents')
    if not n_fans_vents:
        n_fans_vents = n_fans_and_vents(age_band, n_rooms)


    ventilation_props = {}

    if "pressurisation_test_result_average" not in dwelling and "pressurisation_test_result" not in dwelling:
        # if no pressure test, need to configure infiltration rates etc

        floor_type = dwelling.get('floor_type')
        floor_type = correct_floor_type(age_band, floor_type)

        draught_stripping = dwelling.get('draught_stripping')
        if draught_stripping is None:
            draught_stripping = percent_draught_stripping(dwelling['openings'])

        ventilation_props['draught_stripping'] = draught_stripping
        ventilation_props['floor_type'] = floor_type

    draught_lobby = dwelling.get('has_draught_lobby')
    if draught_lobby is None:
        draught_lobby = has_draught_lobby(dwelling_type)

    n_sheltered_sides = dwelling.get("Nshelteredsides")
    if n_sheltered_sides is None:
        n_sheltered_sides = num_sheltered_sides(dwelling_type, dwelling.get("n_floors", 1))

    # for ventilation properties, most are not needed if pressure test is present.
    ventilation_props['has_draught_lobby'] = draught_lobby


    # End Table S5

    wall_u = dwelling.get("wall_u_value")

    if not wall_u:
        # From validation, if wall u isn't defined you must define material and insulation type
        try:
            wall_material = dwelling['wall_material']
            wall_insulation = dwelling['wall_insulation']
        except KeyError as e:
            raise SAPInputError("If wall u isn't defined, wall material and insulation type "
                                "must be supplied. {} was missing".format(e.args[0]))

        # apply tables s6/s7/s8 depending on country
        wall_u = lookup_wall_u_values(country, age_band, wall_material, wall_insulation)

        # only needed to convert from externally measured dimensions to internal ones
        wall_t = dwelling.get("wall_thickness")
        if wall_t is None:
            wall_t = table_s3_wall_thickness(age_band, wall_material, wall_insulation)
            dwelling["wall_thickness"] = wall_t


    # Section S5.8
    thermal_mass_parameter = dwelling.get('thermal_mass_parameter')
    if not thermal_mass_parameter:
        thermal_mass_parameter = 250.0

    # S9 living area fraction
    living_a_fraction = table_s16_living_area_fraction(n_rooms)

    # S10 water heating
    # Define flexible water properties dict, because some parameters such as cylinder
    # volumes only apply/should only be set under certain conditions.
    water_props = {}

    # cylinder volume
    has_hw_cylinder = dwelling.get('has_hw_cylinder')
    if has_hw_cylinder == True and not dwelling.get('measured_cylinder_loss'):
        hw_cylinder_volume = dwelling.get('hw_cylinder_volume')
        if hw_cylinder_volume is None:
            desc = dwelling.get("hw_cylinder_descriptor")
            hw_cylinder_volume = table_s17_water_cylinder(desc)

        cylinder_insulation = dwelling.get('hw_cylinder_insulation')
        cylinder_insulation_type = dwelling.get('hw_cylinder_insulation_type')
        if cylinder_insulation is None or cylinder_insulation_type is None:
            cylinder_insulation, cylinder_insulation_type = cylinder_insulation_properties(age_band)

        water_props['hw_cylinder_volume'] = hw_cylinder_volume
        water_props['hw_cylinder_insulation'] = cylinder_insulation
        water_props['hw_cylinder_insulation_type'] = cylinder_insulation_type


    # pipework
    pipework_insulated = dwelling.get('primary_pipework_insulated')
    if pipework_insulated is None:
        pipework_insulated = primary_pipework_insulated(age_band)

    hw_time_control = has_hw_time_control(age_band)

    water_props['pipework_insulated'] = pipework_insulated



    # assign the values to the dwelling object
    # TODO: return this for update instead...
    dwelling['country'] = country
    dwelling['age_band'] = age_band

    dwelling['Nfansandpassivevents'] = n_fans_vents

    dwelling["Nshelteredsides"] = n_sheltered_sides

    dwelling["wall_u_value"] = wall_u
    dwelling['thermal_mass_parameter'] = thermal_mass_parameter
    dwelling['living_area_fraction'] = living_a_fraction

    dwelling['has_hw_time_control'] = hw_time_control


def floor_insulation_thickness(age_band):
    if age_band <= AgeBand.H:
        return 0
    elif age_band == AgeBand.I:
        return 25
    elif age_band == AgeBand.J:
        return 75
    elif age_band == AgeBand.K:
        return 100


def ground_floor_U(age_band, exposed_perimeter, wall_thickness, ground_floor_a):
    """
    U-values of floors next to the ground
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    The floor U-value is calculated according to BS EN ISO 13370 using its area (A)
    and exposed perimeter (P), and rounded to two decimal places. Floor U-values
    are obtained separately for the main dwelling and for any extension, using the
    applicable area, exposed perimeter and wall thickness. The following parameters are used:

    – wall thickness (w) from Table S3
    – soil type clay (thermal conductivity λg = 1.5 W/m·K)
    – R_si = 0.17 m2K/W
    – R_se = 0.04 m2K/W
    – floor construction as specified by assessor, or from Table S11 if unknown
    – all-over floor insulation of thickness from Table S11 with thermal conductivity 0.035 W/m·K
      (Rf = 0.001*dins/0.035 where dins if the insulation thickness in mm)

    Args:
        age_band:
        exposed_perimeter:
        wall_thickness:
        ground_floor_a: ground floor area

    Returns:

    """
    if ground_floor_a == 0:
        return 0

    lamda_g = 1.5
    Rsi = 0.17
    Rse = 0.04
    Rf = 0.001 * floor_insulation_thickness(age_band) / 0.035

    if age_band <= AgeBand.B:
        # suspended timber floor
        dg = wall_thickness + lamda_g * (Rsi + Rse)
        B = 2 * ground_floor_a / exposed_perimeter
        Ug = 2 * lamda_g * math.log(math.pi * B / dg + 1) / (math.pi * B + dg)
        h = 0.3
        v = 5
        fw = 0.05
        eps = 0.003
        Uw = 1.5
        Ux = 2 * h * Uw / B + 1450 * eps * v * fw / B
        return 1 / (2 * Rsi + Rf + 0.2 + 1 / (Ug + Ux))
    else:
        # solid floor
        dt = wall_thickness + lamda_g * (Rsi + Rf + Rse)
        B = 2 * ground_floor_a / exposed_perimeter
        if dt < B:
            return 2 * lamda_g * math.log(math.pi * B / dt + 1) / (math.pi * B + dt)
        else:
            return lamda_g / (0.457 * B + dt)



# WORK IN PROGRESS:
# Idea to replace main_1, main_2 prefixes with list of configuration dicts
# similarly for hot water and secondary hw_ and secondary_ prefixes
# Instead have secondary: {conf...}

def system_conf_main_1(dwelling):
    return dict(heating_type_code=dwelling.get('main_heating_type_code'),

                fuel=dwelling.get('main_sys_fuel'),

                pcdf_id=dwelling.get('main_heating_pcdf_id'),

                sedbuk_range_case_loss_at_full_output=dwelling.get('sys1_sedbuk_range_case_loss_at_full_output'),
                sedbuk_range=dwelling.get('sys1_sedbuk_range_full_output'),
                sedbuk_type=dwelling.get('sys1_sedbuk_type'),

                sedbuk_2005_effy=dwelling.get('sys1_sedbuk_2005_effy'),
                sedbuk_2009_effy=dwelling.get('sys1_sedbuk_2009_effy'),
                sedbuk_fan_assisted=dwelling.get('sys1_sedbuk_fan_assisted')
                )


def main_1_from_system_conf(conf):
    return dict(main_heating_type_code=conf.get('conf'),

                main_sys_fuel=conf.get('fuel'),

                main_heating_pcdf_id=conf.get('pcdf_id'),

                sys1_sedbuk_range_case_loss_at_full_output=conf.get('sedbuk_range_case_loss_at_full_output'),
                sys1_sedbuk_range_full_output=conf.get('sedbuk_range'),
                sys_1_sedbuk_type=conf.get('sedbuk_type'),

                sys_1_sedbuk_2005_effy=conf.get('sedbuk_2005_effy'),
                sys_1_sedbuk_2009_effy=conf.get('sedbuk_2009_effy'),
                sys_1_sedbuk_fan_assisted=conf.get('sedbuk_fan_assisted')
                )

