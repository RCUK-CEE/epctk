import numpy

from sap.fuels import ELECTRICITY_7HR, ELECTRICITY_10HR
from sap.sap_tables import DAYS_PER_MONTH, immersion_on_peak_fraction, dhw_on_peak_fraction
from .sap_types import FuelTypes, HeatingTypes


class HeatingSystem:
    def __init__(self, system_type,
                 winter_effy,
                 summer_effy,
                 summer_immersion,
                 has_flue_fan,
                 has_ch_pump,
                 table2brow,
                 default_secondary_fraction,
                 fuel):
        self.system_type = system_type

        self.heating_effy_winter = winter_effy
        self.heating_effy_summer = summer_effy
        self.summer_immersion = summer_immersion
        self.table2brow = table2brow
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

        """
        base_water_effy=(self.Q_space+Q_water)/(self.Q_space/self.heating_effy_winter+Q_water/self.heating_effy_summer)
        water_effy=(base_water_effy+self.water_adj)*self.water_mult
        """
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
        return heating_fuel_cost(self, dwelling)

    def co2_factor(self):
        return self.fuel.co2_factor

    def primary_energy_factor(self):
        return self.fuel.primary_energy_factor

    def water_fuel_price(self, dwelling):
        return dhw_fuel_cost(dwelling)

    def get(self, key):
        """
        Light encapsulation of HeatingSystem properties, since we have a lot of
        mix between string-keyed data and attributes. To make this more semantic and prevent too
        many hasattr/getattr everywhere, add a dict-like getter for string keys
        that does the hasattr/getattr op, return None if not found (instead of throwing error)
        :param key:
        :return:
        """
        if hasattr(self, key):
            return getattr(self, key)
        else:
            return None


class SecondarySystem(object):
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


class DedicatedWaterSystem(object):
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

    def co2_factor(self):
        return self.fuel.co2_factor

    def primary_energy_factor(self):
        return self.fuel.primary_energy_factor

    def water_fuel_price(self, dwelling):
        return dhw_fuel_cost(dwelling)


def weighted_effy(Q_space, Q_water, wintereff, summereff):
    # If there is no space or water demand then divisor will be
    # zero
    water_effy = numpy.zeros(12)
    divisor = Q_space / wintereff + Q_water / summereff
    for i in range(12):
        if divisor[i] != 0:
            water_effy[i] = (Q_space[i] + Q_water[i]) / divisor[i]
        else:
            water_effy[i] = 100
    return water_effy


def space_heat_on_peak_fraction(sys, dwelling):
    if sys.system_type == HeatingTypes.off_peak_only:
        return 0
    elif sys.system_type == HeatingTypes.integrated_system:
        assert sys.fuel == ELECTRICITY_7HR
        return .2
    elif sys.system_type == HeatingTypes.storage_heater:
        return 0
    elif sys.system_type == HeatingTypes.cpsu:
        return appendix_f_cpsu_on_peak(sys, dwelling)
    elif sys.system_type == HeatingTypes.electric_boiler:
        if sys.fuel == ELECTRICITY_7HR:
            return 0.9
        elif sys.fuel == ELECTRICITY_10HR:
            return .5
        else:
            return 1
    elif sys.system_type in [HeatingTypes.pcdf_heat_pump,
                             HeatingTypes.microchp]:
        return .8
    elif sys.system_type == HeatingTypes.heat_pump:
        return 0.6
    # !!! underfloor heating
    # !!! ground source heat pump
    # !!! air source heat pump
    # !!! other direct acting heating (incl secondary)
    else:
        if sys.fuel == ELECTRICITY_10HR:
            return .5
        else:
            return 1


def heating_fuel_cost(sys, dwelling):
    if sys.fuel.is_electric:
        on_peak = space_heat_on_peak_fraction(sys, dwelling)
        return sys.fuel.unit_price(on_peak)
    else:
        return sys.fuel.unit_price()


def appendix_f_cpsu_on_peak(sys, dwelling):
    """
    39m=dwelling.h
    45m=hw_energy_content
    93m=Tmean
    95m=useful gains
    98m=Q_required

    :param dwelling:
    :param sys:
    """

    Vcs = dwelling.hw_cylinder_volume
    Tw = dwelling.water_sys.cpsu_Tw
    Cmax = .1456 * Vcs * (Tw - 48)
    nm = DAYS_PER_MONTH
    Tmin = ((dwelling.h * dwelling.heat_calc_results['Tmean']) - Cmax + (
        1000 * dwelling.hw_energy_content / (24 * nm)) -
            dwelling.heat_calc_results['useful_gain']) / dwelling.h

    Text = dwelling.Texternal_heating
    Eonpeak = numpy.where(
            Tmin - Text == 0,
            0.024 * dwelling.h * nm,
            (0.024 * dwelling.h * nm * (Tmin - Text)) / (1 - numpy.exp(-(Tmin - Text))))

    F = Eonpeak / (dwelling.hw_energy_content + dwelling.Q_required)
    for i in range(5, 9):
        F[i] = 0
    return F


def dhw_fuel_cost(dwelling):
    if dwelling.water_sys.fuel.is_electric and dwelling.get('immersion_type') and not dwelling.immersion_type is None:
        # !!! Are there other places that should use non-solar cylinder volume?
        non_solar_cylinder_volume = dwelling.hw_cylinder_volume - (
            dwelling.solar_dedicated_storage_volume
            if dwelling.get('solar_dedicated_storage_volume')
            else 0)
        on_peak = immersion_on_peak_fraction(dwelling.Nocc,
                                             dwelling.electricity_tariff,
                                             non_solar_cylinder_volume,
                                             dwelling.immersion_type)
        return dwelling.water_sys.fuel.unit_price(on_peak)
    elif dwelling.water_sys.fuel.is_electric:
        on_peak = dhw_on_peak_fraction(dwelling.water_sys, dwelling)
        return dwelling.water_sys.fuel.unit_price(on_peak)
    else:
        return dwelling.water_sys.fuel.unit_price()


