from enum import IntEnum

from ..utils import SAPInputError


class Country(IntEnum):
    """
    Countries in the UK.
    .. note::
      "England" is used for region "England and Wales"
    """
    England = 1
    Scotland = 2
    NorthernIreland = 3
    Wales = 4

    @classmethod
    def from_iso(cls, iso_country_code):
        country_codes = {
            "GB-EAW": Country.England,
            "GB-ENG": Country.England,
            "GB-NIR": Country.NorthernIreland,
            "GB-SCT": Country.Scotland,
            "GB-WLS": Country.Wales
        }
        try:
            return country_codes[iso_country_code]
        except KeyError:
            raise SAPInputError("No country in the UK matching code: {}".format(iso_country_code))


COUNTRY_CODES = {
    "GB-EAW": Country.England,
    "GB-ENG": Country.England,
    "GB-NIR": Country.NorthernIreland,
    "GB-SCT": Country.Scotland,
    "GB-WLS": Country.Wales
}


class Region(IntEnum):
    Thames = 1
    SouthEastEngland = 2
    SouthernEngland = 3
    SouthWestEngland = 4
    Severn = 5
    Midlands = 6
    WestPennines = 7
    NwEngland = 8
    SwScotland = 8
    Borders = 9
    NorthEastEngland = 10
    EastPennines = 11
    EastAnglia = 12
    Wales = 13
    WestScotland = 14
    EastScotland = 15
    NorthEastScotland = 16
    Highland = 17
    WesternIsles = 18
    Orkney = 19
    Shetland = 20

COUNTRY_REGIONS = {
    Country.England: [Region.Thames, Region.SouthEastEngland, Region.SouthernEngland, Region.SouthWestEngland,
                      Region.Severn, Region.Midlands, Region.WestPennines, Region.NwEngland, Region.Borders,
                      Region.NorthEastEngland, Region.EastPennines, Region.EastAnglia],
    Country.Wales: [Region.Wales],
    Country.Scotland: [Region.SwScotland, Region.Borders, Region.WestScotland, Region.EastScotland,
                       Region.NorthEastScotland, Region.Highland, Region.WesternIsles, Region.Orkney,
                       Region.Shetland]
}


def country_from_region(region):
    try:
        region = Region(region)  # make sure we are using an Enum value
    except ValueError as e:
        raise SAPInputError(str(e))

    for country, region_list in COUNTRY_REGIONS.items():
        if region in region_list:
            return country
    else:
        raise SAPInputError("No country found for given region: {}".format(region))
