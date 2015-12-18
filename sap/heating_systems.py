import numpy


from .fuels import ELECTRICITY_7HR, ELECTRICITY_10HR, Fuel
from .sap_constants import DAYS_PER_MONTH
from .sap_types import FuelTypes, HeatingTypes, ImmersionTypes


class HeatingSystem:
    def __init__(self, system_type,
                 winter_effy,
                 summer_effy,
                 summer_immersion,
                 has_flue_fan,
                 has_ch_pump,
                 table2b_row,
                 default_secondary_fraction,
                 fuel):
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
    # If there is no space or water demand then divisor will be zero
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


def appendix_f_cpsu_on_peak(system, dwelling):
    """
    39m=dwelling.h
    45m=hw_energy_content
    93m=Tmean
    95m=useful gains
    98m=Q_required

    :param dwelling:
    :param system:
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


# Table 12a
def dhw_on_peak_fraction(water_sys, dwelling):
    """
    Function describing Table 12a, describing the fraction of district hot water on
    peak
    :param water_sys: type of hot water system
    :param dwelling:
    :return:
    """
    # !!! Need to complete this table
    if water_sys.system_type == HeatingTypes.cpsu:
        return appendix_f_cpsu_on_peak(water_sys, dwelling)
    elif water_sys.system_type == HeatingTypes.heat_pump:
        # !!! Need off-peak immersion option
        return .7
    elif water_sys.system_type in [HeatingTypes.pcdf_heat_pump,
                                   HeatingTypes.microchp]:
        return .7
    else:
        return water_sys.fuel.general_elec_on_peak_fraction


# Table 13
def immersion_on_peak_fraction(N_occ, elec_tariff, cylinder_volume, immersion_type):
    """

    :param N_occ: number of occupants
    :param elec_tariff:
    :param cylinder_volume:
    :param immersion_type:
    :return:
    """
    if elec_tariff == ELECTRICITY_7HR:
        if immersion_type == ImmersionTypes.SINGLE:
            return max(0, ((14530 - 762 * N_occ) / cylinder_volume - 80 + 10 * N_occ) / 100)
        else:
            assert immersion_type == ImmersionTypes.DUAL
            return max(0, ((6.8 - 0.024 * cylinder_volume) * N_occ + 14 - 0.07 * cylinder_volume) / 100)
    elif elec_tariff == ELECTRICITY_10HR:
        if immersion_type == ImmersionTypes.SINGLE:
            return max(0, ((14530 - 762 * N_occ) / (1.5 * cylinder_volume) - 80 + 10 * N_occ) / 100)
        else:
            assert immersion_type == ImmersionTypes.DUAL
            return max(0, ((6.8 - 0.036 * cylinder_volume) * N_occ + 14 - 0.105 * cylinder_volume) / 100)
    else:
        return 1


class CommunityDistributionTypes:
    PRE_1990_UNINSULATED = 1
    PRE_1990_INSULATED = 2
    MODERN_HIGH_TEMP = 3
    MODERN_LOW_TEMP = 4


TABLE_12c = {
    CommunityDistributionTypes.PRE_1990_UNINSULATED: 1.2,
    CommunityDistributionTypes.PRE_1990_INSULATED: 1.1,
    CommunityDistributionTypes.MODERN_HIGH_TEMP: 1.1,
    CommunityDistributionTypes.MODERN_LOW_TEMP: 1.05,
}


class CommunityHeating:
    class CommunityFuel:
        def __init__(self):
            self.standing_charge = 106

        @property
        def is_mains_gas(self):
            return False

    def __init__(self, heat_sources, sap_distribution_type):
        self.is_community_heating = True
        self.table2b_row = 2  # !!! Assume indirect cylinder inside dwelling
        self.system_type = HeatingTypes.community
        self.has_ch_pump = False
        self.has_oil_pump = False

        self.has_flue_fan = False
        self.has_warm_air_fan = False
        self.responsiveness = 1
        self.summer_immersion = False
        self.default_secondary_fraction = 0.1

        self.fuel = self.CommunityFuel()
        if not sap_distribution_type is None:
            self.distribution_loss_factor = TABLE_12c[sap_distribution_type]
        else:
            self.distribution_loss_factor = 1.5

        self.chp_fraction = 0
        self.chp_heat_to_power = 0
        self.chp_effy = 0
        boiler_effy_sum = 0
        boiler_co2_factor_sum = 0
        boiler_pe_factor_sum = 0
        boiler_price_sum = 0
        boiler_fraction_sum = 0
        chp_system = None
        biggest_contributor = heat_sources[0]
        for hs in heat_sources:
            if 'heat_to_power' in hs:
                # chp
                assert chp_system is None  # should only find one?
                chp_system = hs
            else:
                boiler_effy_sum += hs['fraction'] / hs['efficiency']
                boiler_fraction_sum += hs['fraction']
                boiler_co2_factor_sum += hs['fuel'].co2_factor * hs['fraction'] / hs['efficiency']
                boiler_pe_factor_sum += hs['fuel'].primary_energy_factor * hs['fraction'] / hs['efficiency']
                boiler_price_sum += hs['fuel'].unit_price() * hs['fraction']

            if hs['fraction'] > biggest_contributor['fraction']:
                biggest_contributor = hs

        self.boiler_effy = boiler_fraction_sum / boiler_effy_sum
        boiler_co2_factor = boiler_co2_factor_sum / boiler_fraction_sum
        boiler_pe_factor = boiler_pe_factor_sum / boiler_fraction_sum
        boiler_price = boiler_price_sum / boiler_fraction_sum

        if chp_system is not None:
            self.chp_fraction += chp_system['fraction']
            self.chp_heat_to_power = chp_system['heat_to_power']
            total_effy = chp_system['efficiency']
            heat_effy = total_effy * self.chp_heat_to_power / (1 + self.chp_heat_to_power)
            chp_effy = heat_effy

            self.heat_to_power_ratio = self.chp_heat_to_power / self.chp_fraction
            self.co2_factor_ = (
                self.chp_fraction * chp_system['fuel'].co2_factor / chp_effy +
                (1 - self.chp_fraction) * boiler_co2_factor)

            self.pe_factor = (
                self.chp_fraction * chp_system['fuel'].primary_energy_factor / chp_effy +
                (1 - self.chp_fraction) * boiler_pe_factor)

            chp_price = Fuel(48).unit_price()
            self.fuel_price_ = (self.chp_fraction * chp_price +
                                (1 - self.chp_fraction) * boiler_price)

        else:
            self.heat_to_power_ratio = 0
            self.co2_factor_ = boiler_co2_factor
            self.pe_factor = boiler_pe_factor
            self.fuel_price_ = boiler_price

        # this is for TER, not completely this is right - how do you
        # pick the TER fuel if you also have a second main system?
        for hs in heat_sources:
            if hs['fuel'].is_mains_gas:
                self.fuel.fuel_factor = hs['fuel'].fuel_factor
                self.fuel.emission_factor_adjustment = hs['fuel'].emission_factor_adjustment
                return

        self.fuel.fuel_factor = biggest_contributor['fuel'].fuel_factor
        self.fuel.emission_factor_adjustment = biggest_contributor['fuel'].emission_factor_adjustment

    def space_heat_effy(self, _Q_space):
        # Efficiencies work a bit differently for community systems -
        # system efficiency is not accounted to in calculating energy
        # consumption and cost (so we return 100% here, scaled for
        # additional loss factors.  System effy is included in CO2 and
        # primary energy factors.
        space_mult = 1 / (self.space_heat_charging_factor * self.distribution_loss_factor)
        return 100 * space_mult

    def water_heat_effy(self, _Q_water):
        space_mult = 1 / (self.dhw_charging_factor * self.distribution_loss_factor)
        return 100 * space_mult

    def fuel_price(self, dwelling):
        return self.fuel_price_

    def co2_factor(self):
        return self.co2_factor_

    def primary_energy_factor(self):
        return self.pe_factor

    def water_fuel_price(self, dwelling):
        return self.fuel_price_