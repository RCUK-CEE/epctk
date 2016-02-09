"""
Tables for RdSAP
~~~~~~~~~~~~~~~~


"""
import logging
import os.path
from enum import Enum, IntEnum
import csv

from ..utils import SAPInputError
from ..elements import GlazingTypes, DwellingType, OpeningType, FloorTypes, FuelTypes, CylinderInsulationTypes
from ..elements.geographic import Country

_DATA_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')


class AgeBand(IntEnum):
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

    @classmethod
    def from_letter(cls, letter):
        return cls.__members__[letter]

    @property
    def letter(self):
        return self.name


class WallMaterial(Enum):
    STONE_HARD = 'stone_hard'
    STONE_SANDSTONE = 'stone_sandstone'
    SOLID_BRICK = 'solid_brick'
    COB = 'cob'
    CAVITY = 'cavity'
    TIMBER = 'timber'
    SYSTEM = 'system'


class WallInsulation(Enum):
    INTERNAL = 'internal'
    EXTERNAL = 'external'
    FILL = 'fill'
    NONE = 'none'


class CylinderDescriptor(Enum):
    INACCESSIBLE = 'inaccessible'
    NORMAL = 'normal'
    MEDIUM = 'medium'
    LARGE = 'large'


# map ageband to year of construction:
TABLE_S1 = {
    Country.Scotland: {AgeBand.A: (None, 1919),
                       AgeBand.B: (1919, 1929),
                       AgeBand.C: (1930, 1949),
                       AgeBand.D: (1950, 1964),
                       AgeBand.E: (1965, 1975),
                       AgeBand.F: (1976, 1983),
                       AgeBand.G: (1984, 1991),
                       AgeBand.H: (1992, 1998),
                       AgeBand.I: (1999, 2002),
                       AgeBand.J: (2003, 2007),
                       AgeBand.K: (2008, None)},
    Country.NorthernIreland: {AgeBand.A: (None, 1919),
                              AgeBand.B: (1919, 1929),
                              AgeBand.C: (1930, 1949),
                              AgeBand.D: (1950, 1973),
                              AgeBand.E: (1974, 1977),
                              AgeBand.F: (1978, 1985),
                              AgeBand.G: (1986, 1991),
                              AgeBand.H: (1992, 1999),
                              AgeBand.I: (2000, 2006),
                              AgeBand.J: None,
                              AgeBand.K: (2007, None)},
    Country.England: {AgeBand.A: (0, 1900),
                      AgeBand.B: (1900, 1929),
                      AgeBand.C: (1930, 1949),
                      AgeBand.D: (1950, 1966),
                      AgeBand.E: (1967, 1975),
                      AgeBand.F: (1976, 1982),
                      AgeBand.G: (1983, 1990),
                      AgeBand.H: (1991, 1995),
                      AgeBand.I: (1996, 2002),
                      AgeBand.J: (2003, 2006),
                      AgeBand.K: (2007, None)}
}


def table_s1_age_band(building_age, country):
    """
    Get the age band from the building age and country
    (England, Scotland, Northern Ireland) - the bands
    are slightly different between UK member countries

    .. note::
      For Wales, set country to Country.England

======== =============== =========== ================
Age band England & Wales Scotland    Northern Ireland
======== =============== =========== ================
A         before 1900    before 1919 before 1919
B         1900-1929 	 1919-1929 	 1919-1929
C         1930-1949      1930-1949   1930-1949
D         1950-1966      1950-1964   1950-1973
E         1967-1975      1965-1975   1974-1977
F         1976-1982      1976-1983   1978-1985
G         1983-1990      1984-1991   1986-1991
H         1991-1995      1992-1998   1992-1999
I         1996-2002      1999-2002   2000-2006
J         2003-2006      2003-2007   (not applicable)
K         2007 onwards   2008 onward 2007 onwards
======== =============== =========== ================

    Args:
        building_age:
        country:

    Returns:
        AgeBand
    """
    country_table = TABLE_S1[country]

    for band, yr_range in country_table.items():
        if yr_range is None:
            continue
        start, end = yr_range
        start = start if start is not None else -9999
        end = end if end is not None else 9999

        if start < building_age <= end:
            return band


def table_s2_wall_thickness_conversion(age_band, wall_material, wall_insulation, p_ext, a_ext):
    """

    If horizontal dimensions are measured externally, they are converted to overall internal dimensions
    for use in SAP calculations by application of the appropriate equations in Table S2, using the
    appropriate wall thickness from Table S3. The equations are applied on a storey-by-storey basis,
    for the whole dwelling (i.e. inclusive of any extension).

    Args:
        age_band:
        wall_material:
        wall_insulation:
        p_ext: external perimeter of floor
        a_ext: external area of floor

    Returns:

    """
    wall_thick = table_s3_wall_thickness(age_band, wall_material, wall_insulation)
    raise NotImplementedError("Table s2 converison from external to internal dimensions not implemented yet")
    # p_int, a_int


def table_s3_wall_thickness(age_band, wall_material, wall_insulation):
    """
    Lookup wall thickness according to table s3

    Args:
        age_band (AgeBand):
        wall_material (WallMaterial):
        wall_insulation (WallInsulation):

    Returns:
        float wall thickness
    """
    # NOTE: make sure all these are tuples, don't remove commas by accident!
    walltype_lookup = {
        'Stone as built': ((WallMaterial.STONE_HARD, WallMaterial.STONE_SANDSTONE), (WallInsulation.NONE,)),
        'Stone with internal or external insulation': ((WallMaterial.STONE_HARD, WallMaterial.STONE_SANDSTONE),
                                                       (WallInsulation.INTERNAL, WallInsulation.EXTERNAL)),
        'Solid brick as built': ((WallMaterial.SOLID_BRICK,),
                                 (WallInsulation.NONE,)),
        'Solid brick with internal or external insulation': ((WallMaterial.SOLID_BRICK,),
                                                             (WallInsulation.INTERNAL, WallInsulation.EXTERNAL)),
        'Cavity': ((WallMaterial.CAVITY,),
                   (WallInsulation.NONE, WallInsulation.FILL)),
        'Timber frame (as built)': ((WallMaterial.TIMBER,),
                                    (WallInsulation.NONE,)),
        'Timber frame with internal insulation': ((WallMaterial.TIMBER,),
                                                  (WallInsulation.INTERNAL,)),
        'Cob': ((WallMaterial.COB,),
                (WallInsulation.NONE,)),
        'Cob with internal or external insulation': ((WallMaterial.COB,),
                                                     (WallInsulation.INTERNAL, WallInsulation.EXTERNAL)),
        'System build': ((WallMaterial.SYSTEM,),
                         (WallInsulation.NONE,)),
        'System build with internal or external insulation': ((WallMaterial.SYSTEM,),
                                                              (WallInsulation.INTERNAL, WallInsulation.EXTERNAL)),

    }

    table = {}
    with open(os.path.join(_DATA_FOLDER, "table_s3.csv")) as csvfile:
        rdr = csv.DictReader(csvfile)
        for row in rdr:
            wall_type = row.pop('WallType').strip()

            band_indexed = {AgeBand.from_letter(c): float(v) for c, v in row.items()}
            table[wall_type] = band_indexed

    for wall_type, row in table.items():
        wall_defs = walltype_lookup[wall_type]
        if wall_material in wall_defs[0] and wall_insulation in wall_defs[1]:
            return row[age_band]
    else:
        raise SAPInputError("No table s3 data for {}, {}, {}".format(age_band, wall_material, wall_insulation))


# Table S5 (contains miscellaneous substitutions)
def n_fans_and_vents(age_band, n_rooms):
    """
    *Table S5*

    Args:
        age_band:
        n_rooms:

    Returns:

    """
    if age_band <= AgeBand.E:
        return 0
    elif age_band <= AgeBand.G:
        return 1
    else:
        if n_rooms <= 2:
            return 1
        elif n_rooms <= 5:
            return 2
        elif n_rooms <= 8:
            return 3
        else:
            return 4


def correct_floor_type(age_band, floor_type: FloorTypes):
    """
    *Table S5*

    For suspended timber floors only, set the floor type to
    unsealed for ageband < E. In SAP this will lookup
    the appropriate infiltration value from the table

    Args:
        age_band:
        floor_type:

    Returns:
        FloorTypes: the corrected floor type - if the floor type is "some type of
         suspended timber" (i.e. not "Not timber" or "other"), return the sealed
         or unseald type according to age band.

    """
    if floor_type not in [FloorTypes.NOT_SUSPENDED_TIMBER, FloorTypes.OTHER]:
        if age_band <= AgeBand.E:
            return FloorTypes.SUSPENDED_TIMBER_UNSEALED
        else:
            return FloorTypes.SUSPENDED_TIMBER_SEALED
    else:
        return floor_type

    # return 0.2 if age_band <= AgeBand.E else 0.1


def has_draught_lobby(dwelling_type):
    """
    *Table S5*

    House or bungalow: no
    Flat or maisonette: yes if heated or unheated corridor

    Args:
        dwelling_type:

    Returns:

    """
    return dwelling_type == DwellingType.FLAT


def percent_draught_stripping(openings):
    """
    *Table S5*

    Windows draughtstripped equal to percentage of triple, double or secondary glazing
    (glazing in a non-separated conservatory is included in the calculation of the percentage).

    Doors not draughtstripped

    Args:
        openings (OpeningType):

    Returns:
        float percentage draft stripped
    """
    count_openings = 0
    count_non_single = 0
    for opening in openings:
        count_openings += 1
        if opening.get('glazing_type') in [GlazingTypes.DOUBLE, GlazingTypes.TRIPLE, GlazingTypes.SECONDARY]:
            count_non_single += 1

    return 100 * count_non_single / count_openings


def num_sheltered_sides(dwelling_type, n_floors):
    """
    *Table S5*

    4 for flat/maisonette up to third storey above ground level 2 in other cases
    Args:
        dwelling_type:
        n_floors:

    Returns:
        int number of sheltered sides
    """

    if dwelling_type in [DwellingType.FLAT, DwellingType.MAISONETTE] and n_floors < 3:
        return 4
    else:
        return 2


### END table s5 ###


def lookup_wall_u_values(country, age_band, wall_material, wall_insulation):
    """
    Lookup U-values using table s6, s7, or s8 depending on the country

    Args:
        country:
        age_band:
        wall_material:
        wall_insulation:
    """
    table_nums = {
        Country.England: 6,
        Country.Wales: 6,
        Country.Scotland: 7,
        Country.NorthernIreland: 8
    }

    table_n = table_nums[country]

    table_lookup = {
        'Stone: granite or whin (as built)': (WallMaterial.STONE_HARD, WallInsulation.NONE),
        'Stone: sandstone (as built)': (WallMaterial.STONE_SANDSTONE, WallInsulation.NONE),
        'Solid brick (as built)': (WallMaterial.SOLID_BRICK, WallInsulation.NONE),
        'Stone/solid brick (external insulation)': (WallMaterial.SOLID_BRICK, WallInsulation.EXTERNAL),
        'Stone/solid brick (internal insulation)': (WallMaterial.SOLID_BRICK, WallInsulation.INTERNAL),
        'Cob (as built)': (WallMaterial.COB, WallInsulation.NONE),
        'Cob (external insulation)': (WallMaterial.COB, WallInsulation.EXTERNAL),
        'Cob (internal insulation)': (WallMaterial.COB, WallInsulation.INTERNAL),
        'Cavity (as built)': (WallMaterial.CAVITY, WallInsulation.NONE),
        'Filled cavity': (WallMaterial.CAVITY, WallInsulation.FILL),
        'Timber frame (as built)': (WallMaterial.TIMBER, WallInsulation.NONE),
        'Timber frame (internal insulation)': (WallMaterial.TIMBER, WallInsulation.INTERNAL),
        'System build (as built)': (WallMaterial.SYSTEM, WallInsulation.NONE),
        'System build (external insulation)': (WallMaterial.SYSTEM, WallInsulation.EXTERNAL),
        'System build (internal insulation)': (WallMaterial.SYSTEM, WallInsulation.INTERNAL),
    }

    table = {}
    with open(os.path.join(_DATA_FOLDER, "table_s{}.csv".format(table_n))) as csvfile:
        rdr = csv.DictReader(csvfile)
        for row in rdr:
            wall_type = row.pop('WallType').strip()
            wall_type = table_lookup[wall_type]
            band_indexed = {AgeBand.from_letter(c): float(v) for c, v in row.items()}
            table[wall_type] = band_indexed

    try:
        return table[(wall_material, wall_insulation)][age_band]
    except KeyError:
        raise SAPInputError("No table s6/7/8 data for {}, {}, {}".format(age_band, wall_material, wall_insulation))


def table_s9_u_roof(loft_ins_thickness_mm, roof_type='tiles'):
    """
    Table S9
    Args:
        loft_ins_thickness_mm: loft insulation thickness at joists in mm,

    Returns:
        U-value of roof according to table s9. In cases where s9 does not apply,
        use table s10

    """
    if roof_type != 'tiles':
        raise NotImplementedError("Only tiles/slate roofs are implemented, {} type not supported".format(roof_type))
    with open(os.path.join(_DATA_FOLDER, "table_s9.csv")) as csvfile:
        rdr = csv.DictReader(csvfile)
        max_u = 0
        for row in rdr:
            t = float(row["Insulation thickness at joists (mm)"])
            u = float(row["Slates or tiles"])
            if loft_ins_thickness_mm >= t:
                max_u = u

        return max_u

        # return 1 / (1 / 2.3 + 0.021 * loft_ins_thickness_mm)


def table_s10_u_roof(age_band, country=Country.England):
    raise NotImplementedError("Table s10 is not implemented yet")


def table_s14_window_properties(glazing_type, is_roof_window=False):
    """
    Args:
        glazing_type(GlazingTypes):
        is_roof_window: the U-value of the window will be increased by 0.2 if
                        the window is a roof window
    """
    roof_u_adjust = 0.2 if is_roof_window else 0

    glazing = {
        GlazingTypes.SINGLE: OpeningType(GlazingTypes.SINGLE, 0.86, 0.7, 4.8 + roof_u_adjust, is_roof_window),
        GlazingTypes.DOUBLE: OpeningType(GlazingTypes.DOUBLE, 0.76, 0.7, 2.0 + roof_u_adjust, is_roof_window),
        GlazingTypes.SECONDARY: OpeningType(GlazingTypes.SECONDARY, 0.76, 0.7, 2.4 + roof_u_adjust, is_roof_window),
        GlazingTypes.TRIPLE: OpeningType(GlazingTypes.TRIPLE, 0.68, 0.7, 1.8 + roof_u_adjust, is_roof_window),
    }

    return glazing[glazing_type]


def table_s16_living_area_fraction(n_rooms):
    """
    Living area fraction according to table s16

    Args:
        n_rooms:

    Returns:

    """

    living_area_fraction = [
        0.75, 0.5, 0.3, 0.25, 0.21, 0.18, 0.16, 0.14, 0.13, 0.12, 0.11, 0.1, 0.1, 0.09, 0.09
    ]
    return living_area_fraction[int(n_rooms) - 1]


def table_s17_water_cylinder(descriptor, fuel_type=None):
    """
    if descriptor is "inaccessible:
        if off-peak electric dual immersion: 210 litres
        if from solid fuel boiler: 160 litres
        otherwise: 110 litre
    Args:
        descriptor: cylinder access descriptor
        fuel_type:

    Returns:
        estimated cylinder volume from description, in litres

    """
    descriptor = CylinderDescriptor(descriptor)

    sizes = {
        CylinderDescriptor.NORMAL: 110,
        CylinderDescriptor.MEDIUM: 160,
        CylinderDescriptor.LARGE: 210
    }

    if descriptor == CylinderDescriptor.INACCESSIBLE:
        if fuel_type == FuelTypes.SOLID:
            return sizes[CylinderDescriptor.MEDIUM]
        elif fuel_type == FuelTypes.ELECTRIC:
            logging.warning("INCOMPLETE: assuming that inaccessible electric cylinder is off-peak dual immersion")
            return sizes[CylinderDescriptor.LARGE]
        else:
            return sizes[CylinderDescriptor.NORMAL]

    return sizes[descriptor]

# Table S18 is a collection of misc corrections/assumptions


def cylinder_insulation_properties(age_band):
    """
    *Table S18, row 1*

    Age band of main property A to F: 12 mm loose jacket
    Age band of main property G, H: 25 mm foam
    Age band of main property I to K: 38 mm foam
    Args:
        age_band:

    Returns:

    """
    if AgeBand.A <= age_band <= AgeBand.F:
        return 12.0, CylinderInsulationTypes.JACKET
    elif AgeBand.G <= age_band <= AgeBand.H:
        return 25.0, CylinderInsulationTypes.FOAM
    elif age_band >= AgeBand.I:
        return 38.0, CylinderInsulationTypes.FOAM
    else:
        raise SAPInputError("Invalid Age Band {}".format(age_band), age_band)


def primary_pipework_insulated(age_band):
    """
    *Table S18, row 4*

    Args:
        age_band:

    Returns:

    """
    if age_band >= AgeBand.K:
        return True
    else:
        return False


def pump_in_heated_space():
    """
    *Table S18, row 5*
    Space heating circulation pump for wet systems is in heated space

    Returns:

    """
    return True


def fan_assist(boiler_data):
    """
    *Table S18, row 7,8*

    Gas boilers pre 1998, balanced or open flue - not fan assisted
    Oil boilers from SAP table - not fan assisted

    Args:
        boiler_data:

    Returns:

    """
    raise NotImplementedError("Fan assist logic not implemented")

def boiler_hetas_approved(boiler_fuel):
    if boiler_fuel == FuelTypes.SOLID:
        return False
    # TODO what about other types?


def has_hw_time_control(age_band):
    """
    *Table S18, row 13*

    Does the dwelling have a hot water timer control

    Args:
        age_band:

    Returns:

    """
    if age_band <= AgeBand.I:
        return False
    else:
        return True
