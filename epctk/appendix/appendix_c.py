"""
Community heating, including schemes with Combined Heat and Power (CHP) and schemes that recover heat from power stations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


"""
from ..elements import CommunityDistributionTypes, HeatingTypes, HeatingSystem
from ..fuels import CommunityFuel, Fuel

TABLE_12c = {
    CommunityDistributionTypes.PRE_1990_UNINSULATED: 1.2,
    CommunityDistributionTypes.PRE_1990_INSULATED: 1.1,
    CommunityDistributionTypes.MODERN_HIGH_TEMP: 1.1,
    CommunityDistributionTypes.MODERN_LOW_TEMP: 1.05,
}


class CommunityHeating(HeatingSystem):
    """
    Data container for Community heating systems

    Args:
        heat_sources (List[dict]): list of heat source dicts
        sap_distribution_type (CommunityDistributionTypes):

    """

    def __init__(self, heat_sources, sap_distribution_type):
        # TODO use the super class initializer
        # super().__init__(HeatingTypes.community, winter_effy, summer_effy,
        #          False, False, False,
        #          2, 0.1, CommunityFuel(fuel_factor, emission_factor_adjustment))
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

        # Set these to None, so that if you try to use them before setting them
        # you generate an error
        self.space_heat_charging_factor = None
        self.dhw_charging_factor = None

        if sap_distribution_type is not None:
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
            self._setup_chp(chp_system, boiler_co2_factor, boiler_price, boiler_pe_factor)

        else:
            self.heat_to_power_ratio = 0
            self.co2_factor_ = boiler_co2_factor
            self.pe_factor = boiler_pe_factor
            self.fuel_price_ = boiler_price

        # FIXME: This code was setting fuel_factor and emission factor, but values were always overridden afterwards...
        # this is for TER, not completely sure this is right - how do you
        # pick the TER fuel if you also have a second main system?
        fuel_factor = None
        emission_factor_adjustment = None
        for hs in heat_sources:
            if hs['fuel'].is_mains_gas:
                fuel_factor = hs['fuel'].fuel_factor
                emission_factor_adjustment = hs['fuel'].emission_factor_adjustment
                self.fuel = CommunityFuel(fuel_factor, emission_factor_adjustment)
                break
        else:
            fuel_factor = biggest_contributor['fuel'].fuel_factor
            emission_factor_adjustment = biggest_contributor['fuel'].emission_factor_adjustment

            self.fuel = CommunityFuel(fuel_factor, emission_factor_adjustment)

    def space_heat_effy(self, _Q_space):
        """
        Calculate the space heating efficiency.

        .. note:

          Requires that apply_4c3 has been run on this system in order to set space_heat_charging_factor
          This happens when we apply_table_4e()
          TODO: avoid this requirement by applying the table to the system on initialisation

        Efficiencies work a bit differently for community systems -
        system efficiency is not accounted to in calculating energy
        consumption and cost (so we return 100% here, scaled for
        additional loss factors.  System effy is included in CO2 and
        primary energy factors.

        :param _Q_space: ignored, included for compatiblity with equivalent function for regular heating
        :return:
        """

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

    def _setup_chp(self, chp_system, boiler_co2_factor, boiler_price, boiler_pe_factor):
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