import math


def geometry(dwelling):
    if not dwelling.get('Aglazing'):
        dwelling.Aglazing = dwelling.GFA * dwelling.glazing_ratio
        dwelling.Aglazing_front = dwelling.glazing_asymmetry * \
                                  dwelling.Aglazing
        dwelling.Aglazing_back = (
                                     1. - dwelling.glazing_asymmetry) * dwelling.Aglazing
        dwelling.Aglazing_left = 0
        dwelling.Aglazing_right = 0

    elif not dwelling.get('Aglazing_front'):
        dwelling.Aglazing_front = dwelling.Aglazing / 2
        dwelling.Aglazing_back = dwelling.Aglazing / 2
        dwelling.Aglazing_left = 0
        dwelling.Aglazing_right = 0

    if dwelling.get('hlp') is not None:
        return

    if dwelling.get('aspect_ratio') is not None:
        # This is for converting for the parametric SAP style
        # dimensions to the calculation dimensions
        width = math.sqrt(dwelling.GFA / dwelling.Nstoreys / dwelling.aspect_ratio)

        depth = math.sqrt(dwelling.GFA / dwelling.Nstoreys * dwelling.aspect_ratio)

        dwelling.volume = width * depth * (dwelling.room_height * dwelling.Nstoreys +
                                           dwelling.internal_floor_depth * (dwelling.Nstoreys - 1))

        dwelling.Aextwall = 2 * (dwelling.room_height * dwelling.Nstoreys + dwelling.internal_floor_depth * (
            dwelling.Nstoreys - 1)) * (width + depth * (1 - dwelling.terrace_level)) - dwelling.Aglazing

        dwelling.Apartywall = 2 * (dwelling.room_height * dwelling.Nstoreys +
                                   dwelling.internal_floor_depth *
                                   (dwelling.Nstoreys - 1)) * (depth * dwelling.terrace_level)

        if dwelling.type == "House":
            dwelling.Aroof = width * depth
            dwelling.Agndfloor = width * depth
        elif dwelling.type == "MidFlat":
            dwelling.Aroof = 0
            dwelling.Agndfloor = 0
        else:
            raise RuntimeError('Unknown dwelling type: %s' % (dwelling.type,))

    else:
        if not dwelling.get('volume'):
            dwelling.volume = dwelling.GFA * dwelling.storey_height

        if not dwelling.get('Aextwall'):
            if dwelling.get('wall_ratio') is not None:
                dwelling.Aextwall = dwelling.GFA * dwelling.wall_ratio
            else:
                dwelling_height = dwelling.storey_height * dwelling.Nstoreys
                total_wall_A = dwelling_height * dwelling.average_perimeter
                if dwelling.get('Apartywall') is not None:
                    dwelling.Aextwall = total_wall_A - dwelling.Apartywall
                elif dwelling.get('party_wall_fraction') is not None:
                    dwelling.Aextwall = total_wall_A * (
                        1 - dwelling.party_wall_fraction)
                else:
                    dwelling.Aextwall = total_wall_A - \
                                        dwelling.party_wall_ratio * dwelling.GFA

        if not dwelling.get('Apartywall'):
            if dwelling.get('party_wall_ratio') is not None:
                dwelling.Apartywall = dwelling.GFA * dwelling.party_wall_ratio
            else:
                dwelling.Apartywall = dwelling.Aextwall * \
                                      dwelling.party_wall_fraction / \
                                      (1 - dwelling.party_wall_fraction)

        if not dwelling.get('Aroof'):
            dwelling.Aroof = dwelling.GFA / dwelling.Nstoreys
            dwelling.Agndfloor = dwelling.GFA / dwelling.Nstoreys