import numpy

# SAP constants that aren't necessarily SAP tables, and may be used in ways that
# make them inconvenient to include in sap_tables.py
DAYS_PER_MONTH = numpy.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
IGH_HEATING = numpy.array([26, 54, 94, 150, 190, 201, 194, 164, 116, 68, 33, 21])
T_EXTERNAL_HEATING = numpy.array([4.5, 5, 6.8, 8.7, 11.7, 14.6, 16.9, 16.9, 14.3, 10.8, 7, 4.9])
WIND_SPEED = numpy.array([5.4, 5.1, 5.1, 4.5, 4.1, 3.9, 3.7, 3.7, 4.2, 4.5, 4.8, 5.1])
HEATING_LATITUDE = 53.4
LIVING_AREA_T_HEATING = 21
COOLING_BASE_TEMPERATURE = 24
SUMMER_MONTHS = list(range(5, 9))
USE_TABLE_4D_FOR_RESPONSIVENESS = -99
COMMUNITY_FUEL_ID = -42 # Arbitrary constant for community fuel type, mostly for use of hash function


class SolarConstants:
    def __init__(self, latitude):
        declination = numpy.array(
                [-20.7, -12.8, -1.8, 9.8, 18.8, 23.1, 21.2, 13.7, 2.9, -8.7, -18.4, -23])

        delta_lat = latitude - declination
        delta_lat_sq = delta_lat ** 2
        self.A = .702 - .0119 * (delta_lat) + 0.000204 * delta_lat_sq
        self.B = -.107 + 0.0081 * (delta_lat) - 0.000218 * delta_lat_sq
        self.C = .117 - 0.0098 * (delta_lat) + 0.000143 * delta_lat_sq


SOLAR_HEATING = SolarConstants(HEATING_LATITUDE)