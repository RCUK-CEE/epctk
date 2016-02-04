"""
Convert RdSAP inputs to SAP inputs by looking
up missing data from RdSAP tables


"""
import math

from ..elements import DwellingType
from ..elements.geographic import Country, country_from_region

from ..tables.tables_appendix_s import AgeBand, table_s1_age_band, num_sheltered_sides

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
        dwelling: dwelling input dict

    Returns:

    """

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



    n_sheltered_sides = dwelling.get("Nshelteredsides")

    if n_sheltered_sides is None:
        num_sheltered_sides(dwelling_type, dwelling.get("n_floors", 1))

    dwelling['country'] = country

    dwelling['age_band'] = age_band




def configure_u_values(dwelling):
    wall_u = lookup_wall_u()


def lookup_wall_u(country, age_band, wall_type):
    # TODO: lookup based on tables s6 s7 s8. Need to complete tables too
    pass

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


