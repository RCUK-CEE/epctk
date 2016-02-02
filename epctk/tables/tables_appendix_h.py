import numpy

from ..elements import SHWCollectorTypes, PVOvershading

TABLE_H1 = {
    SHWCollectorTypes.EVACUATED_TUBE: [0.6, 3, .72],
    SHWCollectorTypes.FLAT_PLATE_GLAZED: [0.75, 6, .9],
    SHWCollectorTypes.UNGLAZED: [0.9, 20, 1],
}
TABLE_H2 = {
    # !!! Needs finishing
    "Horizontal": 961,
    30: {
        0: 730,
        45: 785,
        90: 913,
        135: 1027,
        180: 1073,
        225: 1027,
        270: 913,
        315: 785,
    },
    45: {
        0: 640,
        45: 686,
        90: 854,
        135: 997,
        180: 1054,
        225: 997,
        270: 854,
        315: 686,
    },
    60: {
        0: 500,
        45: 597,
        90: 776,
        135: 927,
        180: 989,
        225: 927,
        270: 776,
        315: 597,
    },
    "Vertical": {
        0: 371,
        45: 440,
        90: 582,
        135: 705,
        180: 746,
        225: 705,
        270: 582,
        315: 440,
    },
}
TABLE_H3 = {
    "Horizontal": numpy.array([0.24, 0.50, 0.86, 1.37, 1.74, 1.84, 1.78, 1.50, 1.06, 0.63, 0.31, 0.19]),
    30: numpy.array([0.35, 0.63, 0.92, 1.30, 1.58, 1.68, 1.62, 1.39, 1.08, 0.74, 0.43, 0.29]),
    45: numpy.array([0.39, 0.69, 0.95, 1.27, 1.52, 1.61, 1.55, 1.34, 1.08, 0.79, 0.48, 0.33]),
    60: numpy.array([0.44, 0.74, 0.97, 1.24, 1.45, 1.54, 1.48, 1.30, 1.09, 0.84, 0.53, 0.37]),
    "Vertical": numpy.array([0.58, 0.92, 1.05, 1.15, 1.25, 1.33, 1.28, 1.15, 1.10, 0.99, 0.69, 0.50]),
}
TABLE_H4 = {
    PVOvershading.HEAVY: 0.5,
    PVOvershading.SIGNIFICANT: 0.65,
    PVOvershading.MODEST: 0.8,
    PVOvershading.NONE_OR_VERY_LITTLE: 1,
}
TABLE_H5 = [1.0, 1.0, 0.94, 0.70, 0.45, 0.44, 0.44, 0.48, 0.76, 0.94, 1.0, 1.0]