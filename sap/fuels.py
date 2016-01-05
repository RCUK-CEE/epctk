import copy
import os.path
import logging

from .pcdf import pcdf_fuel_prices
from .sap_types import FuelTypes
from .utils import float_or_none, csv_to_dict

_DATA_FOLDER = os.path.join(os.path.dirname(__file__), 'data')

PREFER_PCDF_FUEL_PRICES = False


class FuelData:
    def __init__(self, name, fuel_id, co2_factor,
                 fuel_factor, emission_factor_adjustment,
                 price, standing_charge,
                 primary_energy_factor, fuel_type):
        self.name = name
        self.fuel_id = fuel_id
        self.co2_factor = co2_factor
        self.fuel_factor = fuel_factor
        self.emission_factor_adjustment = emission_factor_adjustment
        self.price = price
        self.standing_charge = standing_charge
        self.primary_energy_factor = primary_energy_factor
        self.fuel_type = fuel_type


class Fuel(object):
    def __init__(self, fuel_id):
        self.fuel_id = fuel_id
        self._fuel_data = None
        self.is_electric = False
        self.is_mains_gas = self.fuel_id == 1 or self.fuel_id == 51

    def __hash__(self):
        return self.fuel_id

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.fuel_id == other.fuel_id
        else:
            return False

    def unit_price(self):
        return self.fuel_data.price

    @property
    def standing_charge(self):
        return self.fuel_data.standing_charge

    # @property
    # def is_mains_gas(self):
    #     return self.fuel_id == 1 or self.fuel_id == 51

    # @property
    # def is_electric(self):
    #     return False

    @property
    def type(self):
        return self.fuel_data.fuel_type

    @property
    def co2_factor(self):
        return self.fuel_data.co2_factor

    @property
    def primary_energy_factor(self):
        return self.fuel_data.primary_energy_factor

    @property
    def fuel_factor(self):
        return self.fuel_data.fuel_factor

    @property
    def emission_factor_adjustment(self):
        return self.fuel_data.emission_factor_adjustment

    @property
    def name(self):
        return self.fuel_data.name

    @property
    def fuel_data(self):
        # TODO: check if fuel_data is None
        # FIXME: This is where you need to check USE PCDF DATA
        # if self.use_pcdf_prices:
        #     self._fuel_data = get_fuel_data_pcdf(self.fuel_id)
        # else:
        #     self._fuel_data = get_fuel_data_table_12(self.fuel_id)

        return get_fuel_data(self.fuel_id)

        # !!! Ideally instead of continually getting fuel data
        # !!! (above), would just load it at beginning of calc, as
        # !!! below, except that need to invalidate the fuel data in
        # !!! between calcs
        # if self._fuel_data is None:
        #     self._fuel_data = get_fuel_data(self.fuel_id)
        # return self._fuel_data

    @property
    def fuel_data_pcdf(self):
        return get_fuel_data_pcdf(self.fuel_id)

    @property
    def fuel_data_table_12(self):
        return get_fuel_data_table_12(self.fuel_id)


class CommunityFuel(Fuel):
    def __init__(self, fuel_factor, emission_factor_adjustment):
        super().__init__(None)
        self._fuel_factor = fuel_factor
        self._emission_factor_adjustment = emission_factor_adjustment

        self.is_mains_gas = False

    # @property
    # def is_mains_gas(self):
    #     return False

    @property
    def standing_charge(self):
        return 106

    @property
    def fuel_factor(self):
        return self._fuel_factor

    @property
    def emission_factor_adjustment(self):
        return self._emission_factor_adjustment

    @property
    def fuel_data(self):
        raise NotImplementedError("No fuel data for Community Heating Fuel Type")

class ElectricityTariff(Fuel):
    """
    Assumes that emissions for on and off peak are same
    Assumes that on and off peak standing charge is same
    """

    # TODO: Similar setup to Fuel, decide whether to just subclass...

    def __init__(self, on_peak_fuel_code, off_peak_fuel_code,
                 general_elec_on_peak_fraction, mech_vent_on_peak_fraction):

        self.is_electric = True
        # self.type = FuelTypes.ELECTRIC
        self.is_mains_gas = False

        self.general_elec_on_peak_fraction = general_elec_on_peak_fraction
        self.mech_vent_elec_on_peak_fraction = mech_vent_on_peak_fraction

        self.on_peak_fuel_code = on_peak_fuel_code
        self.off_peak_fuel_code = off_peak_fuel_code

        # fuel_id is used for getting emissions and standing charge data.
        # set this to the on-peak value.
        # Assumes that emissions for on and off peak are same
        # Assumes that on and off peak standing charge is same
        self.fuel_id = on_peak_fuel_code

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        else:
            return False

    def __hash__(self):
        return hash((self.is_electric, self.type, self.is_mains_gas,
                     self.general_elec_on_peak_fraction,
                     self.mech_vent_elec_on_peak_fraction,
                     self.on_peak_fuel_code, self.off_peak_fuel_code))

    def unit_price(self, onpeak_fraction=1):
        price_on_peak = self.on_peak_data.price
        price_off_peak = self.off_peak_data.price
        return price_on_peak * onpeak_fraction + price_off_peak * (1 - onpeak_fraction)

    def type(self):
        return FuelTypes.ELECTRIC

    @property
    def on_peak_data(self):
        return self.fuel_data

    @property
    def off_peak_data(self):
        return get_fuel_data(self.off_peak_fuel_code)

    @property
    def name(self):
        return self.on_peak_data.name.split("(")[0].strip()

    # Properties that are now inherited from Fuel
    # Use the Fuel object for these parameters which use the fuel_data property,
    # which is set to on-peak code
    # @property
    # def fuel_data(self):
    #     return get_fuel_data(self.on_peak_fuel_code)
    # @property
    # def co2_factor(self):
    #     return self.on_peak_data.co2_factor
    #
    # @property
    # def primary_energy_factor(self):
    #     return self.on_peak_data.primary_energy_factor
    #
    # @property
    # def fuel_factor(self):
    #     return self.on_peak_data.fuel_factor
    #
    # @property
    # def emission_factor_adjustment(self):
    #     return self.on_peak_data.emission_factor_adjustment
    #
    # @property
    # def standing_charge(self):
    #     return self.on_peak_data.standing_charge




def translate_12_row(fuels, row):
    # !!! Shouldn't allow None values for some of these columns
    # String mapping for row 12 to convert name -> enum value
    # TODO: could probably have these labels built into the FuelType class
    fuel_types = {'GAS': FuelTypes.GAS, 'OIL': FuelTypes.OIL,
                  'SOLID': FuelTypes.SOLID, 'COMMUNAL': FuelTypes.COMMUNAL,
                  'ELECTRIC': FuelTypes.ELECTRIC}

    f = FuelData(row[0],
                 int(row[1]),
                 float_or_none(row[2]),
                 float_or_none(row[3]),
                 float(row[4]) / float(row[5]) if row[4] != "" else None,
                 float_or_none(row[6]),
                 float_or_none(row[7]),
                 float_or_none(row[8]),
                 fuel_types[row[9]])

    fuels[f.fuel_id] = f


# ELECTRICITY_FROM_CHP=Fuel(49,.529,None,None,None,106,2.92,FuelTypes.COMMUNAL)
# ELECTRICITY_FOR_DISTRIBUTION_NETWORK=Fuel(50,.517,None,None,None,106,2.92,FuelTypes.COMMUNAL)
# HEAT_FROM_CHP = Fuel(48)


_TABLE_12_DATA_CACHE = None


def get_fuel_data_table_12(fuel_id):
    global _TABLE_12_DATA_CACHE
    if _TABLE_12_DATA_CACHE is None:
        _TABLE_12_DATA_CACHE = csv_to_dict(os.path.join(_DATA_FOLDER, 'table_12.csv'), translate_12_row)
    return _TABLE_12_DATA_CACHE[fuel_id]


_PCDF_FUEL_PRICES_CACHE = None


def get_fuel_data_pcdf(fuel_id):
    """
    Get the fuel data from the PCDF file, in particular the prices
    Do so by getting the "Structure" of the FuelData from the loaded
    Table 12 and replacing the price field with the one from the PCDF file

    .. WARNING:

      Despite the function name, this will currently fallback to Table 12 data if
      no PCDF data is found. This can therefore be misleading when you set
      use_pcdf to True, since you might still not be getting PCDF data...

    :param fuel_id:
    :return:
    """
    global _PCDF_FUEL_PRICES_CACHE
    if _PCDF_FUEL_PRICES_CACHE is None:
        _PCDF_FUEL_PRICES_CACHE = pcdf_fuel_prices()

    if fuel_id in _PCDF_FUEL_PRICES_CACHE:
        pcdf_data = _PCDF_FUEL_PRICES_CACHE[fuel_id]

        fuel_prices = copy.deepcopy(get_fuel_data_table_12(fuel_id))

        fuel_prices.standing_charge = pcdf_data['standing_charge']
        fuel_prices.price = pcdf_data['price']

        return fuel_prices

    elif fuel_id in [51, 52, 53, 54, 55, 41, 42, 43, 44, 45, 46]:
        # community heating - uses fuel code 47 in pcdf
        pcdf_data = _PCDF_FUEL_PRICES_CACHE[47]

        fuel_prices = copy.deepcopy(get_fuel_data_table_12(fuel_id))

        fuel_prices.standing_charge = pcdf_data['standing_charge']
        fuel_prices.price = pcdf_data['price']
        return fuel_prices

    else:
        # print()
        logging.warning("fuels.py: THERE IS NO PCDF DATA FOR THIS FUEL ID %d" % fuel_id)
        # raise RuntimeError("THERE IS NO PCDF DATA FOR THIS FUEL ID")
        return get_fuel_data_table_12(fuel_id)


# FIXME!!! References Global Mutable Variable, which is a BIG ISSUE!
# FIXME: USE_PCDF_FUEL_PRICES doesn't guarantee you get a PCDF fuel price, since it falls back to T12 anyway
def get_fuel_data(fuel_id):
    if PREFER_PCDF_FUEL_PRICES:
        return get_fuel_data_pcdf(fuel_id)
    else:
        return get_fuel_data_table_12(fuel_id)


ELECTRICITY_STANDARD = ElectricityTariff(30, 30, 1, 1)
ELECTRICITY_7HR = ElectricityTariff(32, 31, 0.9, 0.71)
ELECTRICITY_10HR = ElectricityTariff(34, 33, 0.8, 0.58)
ELECTRICITY_24HR = ElectricityTariff(35, 35, 1, 1)

_TABLE_12_ELEC = {
    30: ELECTRICITY_STANDARD,
    32: ELECTRICITY_7HR,
    31: ELECTRICITY_7HR,
    34: ELECTRICITY_10HR,
    33: ELECTRICITY_10HR,
    35: ELECTRICITY_24HR,
}


def fuel_from_code(code):
    if code in _TABLE_12_ELEC:
        return copy.deepcopy(_TABLE_12_ELEC[code])
    else:
        return Fuel(code)
