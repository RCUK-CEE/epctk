"""
Seasonal efficiency for solid fuel boilers from test data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This appendix specifies how to obtain a seasonal efficiency from test data on a solid
fuel boiler that is provided in the Product Characteristics Database. A database
record for a solid fuel boiler includes:

- SAP seasonal efficiency, %
- Fuel input, heat to water and heat to room from test at full load, kW
- Fuel input, heat to water and heat to room from test at part load, kW

All efficiency values are gross (net-to-gross conversion factors are given in Table E4).
"""
from ..elements import HeatingTypes, HeatingSystem


def solid_fuel_boiler_from_pcdf(pcdf_data, fuel, use_immersion_in_summer):
    """
    Implements Appendix J

    :param pcdf_data:
    :param fuel:
    :param use_immersion_in_summer:
    :return:
    """
    if pcdf_data['seasonal_effy'] != '':
        effy = float(pcdf_data['seasonal_effy'])

    elif pcdf_data['part_load_fuel_use'] != '':
        # FIXME
        raise NotImplementedError("Appendix J: Part load fuel use not implemented")
        # !!! Need to tests for inside/outside of heated space
        # nominal_effy = 100 * (pcdf_data['nominal_heat_to_water'] + pcdf_data['nominal_heat_to_room']) / pcdf_data[
        #     'nominal_fuel_use']
        # part_load_effy = 100 * (pcdf_data['part_load_heat_to_water'] + pcdf_data['part_load_heat_to_room']) / pcdf_data[
        #     'part_load_fuel_use']
        # effy = 0.5 * (nominal_effy + part_load_effy)

    else:
        nominal_effy = 100 * (
            float(pcdf_data['nominal_heat_to_water']) + float(pcdf_data['nominal_heat_to_room'])) / float(
                pcdf_data['nominal_fuel_use'])
        effy = .975 * nominal_effy

    sys = HeatingSystem(HeatingTypes.regular_boiler,  # !!!
                        effy,
                        effy,
                        summer_immersion=use_immersion_in_summer,
                        has_flue_fan=False,  # !!!
                        has_ch_pump=True,
                        table2b_row=2,  # !!! Solid fuel boilers can only have indirect boiler?
                        default_secondary_fraction=0.1,  # !!! Assumes 10% secondary fraction
                        fuel=fuel)

    sys.responsiveness = .5  # !!! Needs to depend on "main type" input

    sys.has_warm_air_fan = False

    return sys