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
