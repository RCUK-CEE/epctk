import numpy

from .common import weighted_effy
# from .heating_dump import heating_fuel_cost, dhw_fuel_cost
from .sap_types import FuelTypes, HeatingTypes


class HeatingSystem:
    def __init__(self, system_type, winter_effy, summer_effy,
                 summer_immersion, has_flue_fan, has_ch_pump,
                 table2b_row, default_secondary_fraction, fuel):
        self.system_type = system_type

        self.heating_effy_winter = winter_effy
        self.heating_effy_summer = summer_effy
        self.summer_immersion = summer_immersion
        self.table2b_row = table2b_row
        self.default_secondary_fraction = default_secondary_fraction

        self.has_flue_fan = has_flue_fan
        self.has_ch_pump = has_ch_pump
        self.has_warm_air_fan = False

        self.has_oil_pump = (fuel.type == FuelTypes.OIL and
                             system_type in [HeatingTypes.regular_boiler,
                                             HeatingTypes.combi,
                                             HeatingTypes.storage_combi])

        self.fuel = fuel

        # These may be changed after init
        self.space_mult = 1
        self.space_adj = 0
        self.water_mult = 1
        self.water_adj = 0

        self.is_community_heating = False

        self.Q_space = 0

    def space_heat_effy(self, Q_space):
        self.Q_space = Q_space
        return (self.heating_effy_winter + self.space_adj) * self.space_mult

    def water_heat_effy(self, Q_water):

        if hasattr(self, 'water_effy'):
            # Override for systems like gas warm air system with circulator
            return self.water_effy

        #
        # base_water_effy=(self.Q_space+Q_water)/(self.Q_space/self.heating_effy_winter+Q_water/self.heating_effy_summer)
        # water_effy=(base_water_effy+self.water_adj)*self.water_mult

        # Looks like you apply effy adjustments before calculating the
        # seasonal weight efficiency, but which adjustments do you use
        # for winter?  Space or water heating?
        wintereff = (self.heating_effy_winter + self.water_adj) * self.water_mult
        summereff = (self.heating_effy_summer + self.water_adj) * self.water_mult

        water_effy = weighted_effy(self.Q_space, Q_water, wintereff, summereff)

        if self.summer_immersion:
            for i in range(5, 9):
                water_effy[i] = 100

        return water_effy

    def fuel_price(self, dwelling):
        """
        Return the fuel price
        :param dwelling:
        :return:
        """
        # Import locally to avoid circular reference problems when importing main module
        from .heating_dump import heating_fuel_cost
        return heating_fuel_cost(self, dwelling)

    def co2_factor(self):
        return self.fuel.co2_factor

    def primary_energy_factor(self):
        return self.fuel.primary_energy_factor

    def water_fuel_price(self, dwelling):
        """
        Return the fuel price for water heating
        :param dwelling:
        :return:
        """
        # Import locally to avoid circular reference problems when importing main module
        from .heating_dump import dhw_fuel_cost
        return dhw_fuel_cost(dwelling)

    def get(self, key, default=None):
        """
        Light encapsulation of HeatingSystem properties, since we have a lot of
        mix between string-keyed data and attributes. To make this more semantic and prevent too
        many hasattr/getattr everywhere, add a dict-like getter for string keys
        that does the hasattr/getattr op, return None if not found (instead of throwing error)

        :param key:
        :param default: As in dict.get(), allows you to set an alternative default value
        :return:
        """
        if hasattr(self, key):
            return getattr(self, key)
        else:
            return default


class DedicatedWaterSystem(HeatingSystem):
    def __init__(self, effy, summer_immersion):
        self.base_effy = numpy.array([effy, ] * 12)
        self.summer_immersion = summer_immersion
        self.water_mult = 1  # Might be changed after init
        self.system_type = HeatingTypes.misc
        self.is_community_heating = False

    def water_heat_effy(self, _Q_water):
        water_effy = self.base_effy * self.water_mult

        if self.summer_immersion:
            for i in range(5, 9):
                water_effy[i] = 100

        return water_effy

    # def co2_factor(self):
    #     return self.fuel.co2_factor

    # def primary_energy_factor(self):
    #     return self.fuel.primary_energy_factor

    # def water_fuel_price(self, dwelling):
    #     return dhw_fuel_cost(dwelling)


class SecondarySystem(object):
    """
    Defines a Secondary heating system. According to Appendix A:

    > The secondary heating system is based upon a room heater. Secondary heating
    > systems are taken from the room heaters section of Table 4a.
    > Only fixed secondary heaters are included in a description of the property
    > (e.g. a gas fire, a chimney and hearth capable of supporting an open fire, a wall-mounted electric fire).

    """

    def __init__(self, system_type, effy, summer_immersion):
        self.effy = effy
        self.summer_immersion = summer_immersion
        self.system_type = system_type
        self.is_community_heating = False

    def space_heat_effy(self, _Q_space):
        return self.effy

    def water_heat_effy(self, _Q_water):
        if hasattr(self, 'water_effy'):
            # Override for systems like gas warm air system with circulator
            return self.water_effy
        water_effy = [self.effy, ] * 12
        if self.summer_immersion:
            for i in range(5, 9):
                water_effy[i] = 100

        return water_effy

    def fuel_price(self, dwelling):
        return heating_fuel_cost(self, dwelling)

    def co2_factor(self):
        return self.fuel.co2_factor

    def primary_energy_factor(self):
        return self.fuel.primary_energy_factor

    def water_fuel_price(self, dwelling):
        return dhw_fuel_cost(dwelling)