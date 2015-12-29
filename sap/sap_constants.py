import numpy

# Table 1a
from sap.sap_types import FloorTypes

DAYS_PER_MONTH = numpy.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
IGH_HEATING = numpy.array([26, 54, 94, 150, 190, 201, 194, 164, 116, 68, 33, 21])
T_EXTERNAL_HEATING = numpy.array([4.5, 5, 6.8, 8.7, 11.7, 14.6, 16.9, 16.9, 14.3, 10.8, 7, 4.9])
WIND_SPEED = numpy.array([5.4, 5.1, 5.1, 4.5, 4.1, 3.9, 3.7, 3.7, 4.2, 4.5, 4.8, 5.1])
FLOOR_INFILTRATION = {
    FloorTypes.SUSPENDED_TIMBER_UNSEALED: 0.2,
    FloorTypes.SUSPENDED_TIMBER_SEALED: 0.1,
    FloorTypes.NOT_SUSPENDED_TIMBER: 0,
    FloorTypes.OTHER: 0,
}
HEATING_LATITUDE = 53.4