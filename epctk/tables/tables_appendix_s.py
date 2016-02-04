"""
Tables for RdSAP
~~~~~~~~~~~~~~~~


"""

import math
from enum import IntEnum

from ..elements import Country


class AgeBands(IntEnum):
    A = 1
    B = 2
    C = 3
    D = 4
    E = 5
    F = 6
    G = 7
    H = 8
    I = 9
    J = 10
    K = 11


# Age band 	England & Wales 	Scotland 	Northern Ireland
# A 	before 1900 	before 1919 	before 1919
# B 	1900-1929 	1919-1929 	1919-1929
# C 	1930-1949 	1930-1949 	1930-1949
# D 	1950-1966 	1950-1964 	1950-1973
# E 	1967-1975 	1965-1975 	1974-1977
# F 	1976-1982 	1976-1983 	1978-1985
# G 	1983-1990 	1984-1991 	1986-1991
# H 	1991-1995 	1992-1998 	1992-1999
# I 	1996-2002 	1999-2002 	2000-2006
# J 	2003-2006 	2003-2007 	(not applicable)
# K 	2007 onwards 	2008 onwards 	2007 onwards

# map ageband to year of construction:
TABLE_S1 = {
    Country.Scotland: {AgeBands.A: (None, 1919),
                       AgeBands.B: (1919, 1929),
                       AgeBands.C: (1930, 1949),
                       AgeBands.D: (1950, 1964),
                       AgeBands.E: (1965, 1975),
                       AgeBands.F: (1976, 1983),
                       AgeBands.G: (1984, 1991),
                       AgeBands.H: (1992, 1998),
                       AgeBands.I: (1999, 2002),
                       AgeBands.J: (2003, 2007),
                       AgeBands.K: (2008, None)},
    Country.NortherIreland: {AgeBands.A: (None, 1919),
                             AgeBands.B: (1919, 1929),
                             AgeBands.C: (1930, 1949),
                             AgeBands.D: (1950, 1973),
                             AgeBands.E: (1974, 1977),
                             AgeBands.F: (1978, 1985),
                             AgeBands.G: (1986, 1991),
                             AgeBands.H: (1992, 1999),
                             AgeBands.I: (2000, 2006),
                             AgeBands.J: None,
                             AgeBands.K: (2007, None)},
    Country.England: {AgeBands.A: (0, 1900),
                      AgeBands.B: (1900, 1929),
                      AgeBands.C: (1930, 1949),
                      AgeBands.D: (1950, 1966),
                      AgeBands.E: (1967, 1975),
                      AgeBands.F: (1976, 1982),
                      AgeBands.G: (1983, 1990),
                      AgeBands.H: (1991, 1995),
                      AgeBands.I: (1996, 2002),
                      AgeBands.J: (2003, 2006),
                      AgeBands.K: (2007, None)},
    Country.Wales: {AgeBands.A: (None, 1900), AgeBands.B: (1900, 1929), AgeBands.C: (1930, 1949),
                    AgeBands.D: (1950, 1966), AgeBands.E: (1967, 1975), AgeBands.F: (1976, 1982),
                    AgeBands.G: (1983, 1990), AgeBands.H: (1991, 1995), AgeBands.I: (1996, 2002),
                    AgeBands.J: (2003, 2006), AgeBands.K: (2007, None)}
}


def table_s1_age_band(building_age, country=Country.England):
    country_table = TABLE_S1[country]

    for band, yr_range in country_table.items():
        if yr_range is None:
            continue
        start, end = yr_range
        start = start if start is not None else -9999
        end = end if end is not None else 9999

        if start < building_age <= end:
            return band


def floor_infiltration(age_band):
    return 0.2 if age_band <= AgeBands.E else 0.1


def n_fans_and_vents(age_band, Nrooms):
    if age_band <= AgeBands.E:
        return 0
    elif age_band <= AgeBands.G:
        return 1
    else:
        if Nrooms <= 2:
            return 1
        elif Nrooms <= 5:
            return 2
        elif Nrooms <= 8:
            return 3
        else:
            return 4


LIVING_AREA_FRACTION = [
    0.75, 0.5, 0.3, 0.25, 0.21, 0.18, 0.16, 0.14, 0.13, 0.12, 0.11, 0.1, 0.1, 0.09, 0.09
]


def living_area_fraction(n_rooms):
    return LIVING_AREA_FRACTION[int(n_rooms) - 1]


def u_roof(loft_ins_thickness_mm):
    return 1 / (1 / 2.3 + 0.021 * loft_ins_thickness_mm)


CAVITY_WALL_U_VALUES = {  # Masonry cavity as built
    AgeBands.A: 2.1,
    AgeBands.B: 1.6,
    AgeBands.C: 1.6,
    AgeBands.D: 1.6,
    AgeBands.E: 1.6,
    AgeBands.F: 1.0,
    AgeBands.G: 0.6,
    AgeBands.H: 0.6,
}

FILLED_CAVITY_WALL_U_VALUES = {  # Masonry cavity filled
    AgeBands.A: 0.5,
    AgeBands.B: 0.5,
    AgeBands.C: 0.5,
    AgeBands.D: 0.5,
    AgeBands.E: 0.5,
    AgeBands.F: 0.4,
    AgeBands.G: 0.35,
    AgeBands.H: 0.35,
}

SOLID_BRICK_U_VALUES = {  # Solid brick as built
    AgeBands.A: 2.1,
    AgeBands.B: 2.1,
    AgeBands.C: 2.1,
    AgeBands.D: 2.1,
    AgeBands.E: 1.7,
    AgeBands.F: 1.0,
    AgeBands.G: .6,
    AgeBands.H: .6,
}

"""
SOLID_BRICK_U_VALUES= { ### Solid brick as built
    AgeBands.A:1.7,
    AgeBands.B:1.7,
    AgeBands.C:1.7,
    AgeBands.D:1.7,
    AgeBands.E:1.7,
    AgeBands.F:1.0,
    AgeBands.G:.6,
    AgeBands.H:.6, 
}"""
TIMBER_WALL_U_VALUES = {  # Timber frame
    AgeBands.A: 2.5,
    AgeBands.B: 1.9,
    AgeBands.C: 1.9,
    AgeBands.D: 1.0,
    AgeBands.E: 0.8,
    AgeBands.F: 0.45,
    AgeBands.G: 0.4,
    AgeBands.H: 0.4,
}

CONCRETE_WALL_U_VALUES = {  # System build as built
    AgeBands.A: 2.0,
    AgeBands.B: 2.0,
    AgeBands.C: 2.0,
    AgeBands.D: 2.0,
    AgeBands.E: 1.7,
    AgeBands.F: 1.0,
    AgeBands.G: 0.6,
    AgeBands.H: 0.6,
}

CAVITY_WALL_THICKNESS = {
    AgeBands.A: .25,
    AgeBands.B: .25,
    AgeBands.C: .25,
    AgeBands.D: .25,
    AgeBands.E: .25,
    AgeBands.F: .26,
    AgeBands.G: .27,
    AgeBands.H: .27,
}

SOLID_WALL_THICKNESS = {
    AgeBands.A: .22,
    AgeBands.B: .22,
    AgeBands.C: .22,
    AgeBands.D: .22,
    AgeBands.E: .24,
    AgeBands.F: .25,
    AgeBands.G: .27,
    AgeBands.H: .27,
}

TIMBER_WALL_THICKNESS = {
    AgeBands.A: .15,
    AgeBands.B: .15,
    AgeBands.C: .15,
    AgeBands.D: .25,
    AgeBands.E: .27,
    AgeBands.F: .27,
    AgeBands.G: .27,
    AgeBands.H: .27,
}

CONCRETE_WALL_THICKNESS = {
    AgeBands.A: .25,
    AgeBands.B: .25,
    AgeBands.C: .25,
    AgeBands.D: .25,
    AgeBands.E: .25,
    AgeBands.F: .30,
    AgeBands.G: .30,
    AgeBands.H: .30,
}


def floor_insulation_thickness(age_band):
    if age_band <= AgeBands.H:
        return 0
    elif age_band == AgeBands.I:
        return 25
    elif age_band == AgeBands.J:
        return 75
    elif age_band == AgeBands.K:
        return 100


def Ugnd(age_band, exposed_perimeter, wall_thickness, Agndfloor):
    if Agndfloor == 0:
        return 0

    lamda_g = 1.5
    Rsi = .17
    Rse = 0.04
    Rf = 0.001 * floor_insulation_thickness(age_band) / 0.035

    if age_band <= AgeBands.B:
        # suspended timber floor
        dg = wall_thickness + lamda_g * (Rsi + Rse)
        B = 2 * Agndfloor / exposed_perimeter
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
        B = 2 * Agndfloor / exposed_perimeter
        if dt < B:
            return 2 * lamda_g * math.log(math.pi * B / dt + 1) / (math.pi * B + dt)
        else:
            return lamda_g / (0.457 * B + dt)


class Glazing:
    def __init__(self, light_transmittance, gvalue, Uvalue, draught_proof):
        self.properties = {
            'light_transmittance': light_transmittance,
            'gvalue': gvalue,
            'Uglazing': Uvalue,
            'glazing_is_draught_proof': draught_proof
        }

    def apply_to(self, target):
        # target.glazing=self.properties
        for k, v in list(self.properties.items()):
            setattr(target, k, v)


GLAZING_TYPES = dict(
    SINGLE=Glazing(0.9, 0.85, 1 / (0.04 + 1 / 4.8), False),
    ### Should vary with age
    DOUBLE=Glazing(0.8, 0.76, 1 / (0.04 + 1 / 3.1), True),
)


# also need secondary and triple glazing


class DwellingType(IntEnum):
    HOUSE = 1
    FLAT = 2
    BUNGALOW = 3
    MAISONETTE = 4


class DwellingSubType(IntEnum):
    DETACHED = 1
    SEMI_DETACHED = 2
    MID_TERRACE = 3
    END_TERRACE = 4
    ENCLOSED_MID_TERRACE = 5
    ENCLOSED_END_TERRACE = 6


def has_draught_lobby(dwelling_type):
    return dwelling_type == DwellingType.FLAT


def primary_pipework_insulated():
    return False


def has_hw_time_control(age_band):
    if age_band <= AgeBands.I:
        return False
    else:
        return True
