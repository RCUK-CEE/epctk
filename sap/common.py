import numpy


def weighted_effy(Q_space, Q_water, wintereff, summereff):
    """
    Calculate monthly efficiencies given the space and water heating requirements
    and the winter and summer efficiencies

    :param Q_space: space heating demand
    :param Q_water: water heating demand
    :param wintereff: winter efficiency
    :param summereff: summer efficiency
    :return: array with 12 monthly efficiences
    """
    # If there is no space or water demand then divisor will be zero
    water_effy = numpy.zeros(12)
    divisor = Q_space / wintereff + Q_water / summereff
    for i in range(12):
        if divisor[i] != 0:
            water_effy[i] = (Q_space[i] + Q_water[i]) / divisor[i]
        else:
            water_effy[i] = 100
    return water_effy