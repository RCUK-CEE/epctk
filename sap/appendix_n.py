"""
Appendix N: Heat Pumps and Micro CHP
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


"""
import types

import numpy

from .heating_systems import weighted_effy, HeatingSystem
from .sap_tables import interpolate_efficiency, interpolate_psr_table, table_n8_secondary_fraction, \
    table_n4_heating_days, USE_TABLE_4D_FOR_RESPONSIVENESS
from .sap_types import HeatingTypes, FuelTypes


def add_appendix_n_equations_heat_pumps(dwelling, sys, pcdf_data):
    add_appendix_n_equations_shared(dwelling, sys, pcdf_data)

    def heat_pump_space_effy(self, Q_space):
        h_mean = sum(dwelling.h) / 12
        psr = 1000 * pcdf_data['maximum_output'] / (h_mean * 24.2)

        if not pcdf_data['number_of_air_flow_rates'] is None:
            throughput = 0.5  # !!!
            flow_rate = dwelling.volume * throughput / 3.6

            if flow_rate < pcdf_data['air_flow_2']:
                assert flow_rate >= pcdf_data['air_flow_1']  # !!!
                flowrateset1 = 0
                flowrateset2 = 1
            else:
                # doesn't matter if flow rate > flowrate_3 because
                # when we do the interpolation we limit frac to 1
                flowrateset1 = 1
                flowrateset2 = 2

            flowrate1 = pcdf_data['air_flow_%d' % (flowrateset1 + 1)]
            flowrate2 = pcdf_data['air_flow_%d' % (flowrateset2 + 1)]
            frac = min(1, (flow_rate - flowrate1) / (flowrate2 - flowrate1))

            effy1 = interpolate_efficiency(psr, pcdf_data['psr_datasets'][flowrateset1])
            effy2 = interpolate_efficiency(psr, pcdf_data['psr_datasets'][flowrateset2])
            effy = (1 - frac) * effy1 + frac * effy2
            run_hrs1 = interpolate_psr_table(psr,
                                             pcdf_data['psr_datasets'][flowrateset1],
                                             key=lambda x: x['psr'],
                                             data=lambda x: x['running_hours'])
            run_hrs2 = interpolate_psr_table(psr, pcdf_data['psr_datasets'][flowrateset2],
                                             key=lambda x: x['psr'],
                                             data=lambda x: x['running_hours'])
            running_hours = (int)((1 - frac) * run_hrs1 + frac * run_hrs2 + .5)
            Rhp = 1  # !!!
            Qfans = dwelling.volume * dwelling.adjusted_fan_sfp * throughput * Rhp * (
                8760 - running_hours) / 3600
            dwelling.Q_mech_vent_fans = Qfans
        else:
            effy = interpolate_efficiency(psr, pcdf_data['psr_datasets'][0])

        space_heat_in_use_factor = .95
        return effy * space_heat_in_use_factor

    def heat_pump_water_effy(self, Q_water):
        if pcdf_data['hw_vessel'] == 1:  # integral
            in_use_factor = .95
        elif pcdf_data['hw_vessel'] == 2:  # separate, specified
            dwelling.hw_cylinder_area = 9e9  # !!! Should be input
            # !!! Need to check performance criteria of cylinder (table N7)
            if (dwelling.hw_cylinder_volume >= pcdf_data['vessel_volume'] and
                # !!! Might not always have measured loss - can also come from insulation type, etc
                        dwelling.measured_cylinder_loss <= pcdf_data['vessel_heat_loss'] and
                        dwelling.hw_cylinder_area >= pcdf_data['vessel_heat_exchanger']):
                in_use_factor = .95
            else:
                in_use_factor = .6
        elif pcdf_data['hw_vessel'] == 3:  # separate, unspecified
            in_use_factor = .6
        else:
            assert False
            in_use_factor = 1

        # !!! also need sch3 option
        water_effy = [max(100, pcdf_data['water_heating_effy_sch2'] * in_use_factor), ] * 12
        if self.summer_immersion:
            for i in range(5, 9):
                water_effy[i] = 100
        return water_effy

    sys.water_heat_effy = types.MethodType(heat_pump_water_effy, sys)
    sys.space_heat_effy = types.MethodType(heat_pump_space_effy, sys)


def add_appendix_n_equations_shared(dwelling, sys, pcdf_data):
    def longer_heating_days(self):
        h_mean = sum(dwelling.h) / 12
        psr = 1000 * pcdf_data['maximum_output'] / (h_mean * 24.2)

        # !!! Not the best place to set this
        dwelling.fraction_of_heat_from_main = 1 - table_n8_secondary_fraction(psr, pcdf_data['heating_duration'])

        # TABLE N3
        if pcdf_data['heating_duration'] == "V":
            N24_16, N24_9, N16_9 = table_n4_heating_days(psr)
        elif pcdf_data['heating_duration'] == "24":
            N24_16, N24_9, N16_9 = (104, 261, 0)
        elif pcdf_data['heating_duration'] == "16":
            N24_16, N24_9, N16_9 = (0, 0, 261)
        else:
            assert pcdf_data['heating_duration'] == "11"
            N24_16, N24_9, N16_9 = (0, 0, 0)

        # TABLE N5
        MONTH_ORDER = [0, 11, 1, 2, 10, 3, 9, 4, 5, 6, 7, 8]
        N_WE = [9, 9, 8, 9, 8, 8, 9, 9, 9, 9, 9, 8]
        N_WD = [22, 22, 20, 22, 22, 22, 22, 22, 21, 22, 22, 22]

        N24_9_m = [0, ] * 12
        N16_9_m = [0, ] * 12
        N24_16_m = [0, ] * 12
        for i in range(12):
            month = MONTH_ORDER[i]

            # Allocate weekdays
            N24_9_m[month] = min(N_WD[i], N24_9)
            N24_9 -= N24_9_m[month]
            N_WD[i] -= N24_9_m[month]

            N16_9_m[month] = min(N_WD[i], N16_9)
            N16_9 -= N16_9_m[month]

            # Allocate weekends
            N24_16_m[month] = min(N_WE[i], N24_16)
            N24_16 -= N24_16_m[month]

        return numpy.array(N24_16_m), numpy.array(N24_9_m), numpy.array(N16_9_m),

    dwelling.longer_heating_days = types.MethodType(longer_heating_days, dwelling)


def sch3_calc(dwelling, sch2val, sch3val):
    Vd = dwelling.daily_hot_water_use
    return sch2val + (sch3val - sch2val) * (Vd - 100.2) / 99.6


def add_appendix_n_equations_microchp(dwelling, sys, pcdf_data):
    add_appendix_n_equations_shared(dwelling, sys, pcdf_data)

    def micro_chp_space_effy(self, Q_space):
        h_mean = sum(dwelling.h) / 12
        psr = 1000 * pcdf_data['maximum_output'] / (h_mean * 24.2)
        effy = interpolate_efficiency(psr, pcdf_data['psr_datasets'][0])
        sys.effy_space = effy
        space_heat_in_use_factor = 1
        self.Q_space = Q_space

        dwelling.chp_space_elec = interpolate_psr_table(
                psr, pcdf_data['psr_datasets'][0],
                key=lambda x: x['psr'],
                data=lambda x: x['specific_elec_consumed'])

        return effy * space_heat_in_use_factor

    def micro_chp_water_effy(self, Q_water):
        # !!! Can this all be replaced with regular water function?
        # !!! Winter effy might be the problem as it needs psr

        # !!! adjustments can apply??
        if not pcdf_data['water_heating_effy_sch3'] is None:
            Vd = dwelling.daily_hot_water_use
            summereff = sch3_calc(dwelling,
                                  pcdf_data['water_heating_effy_sch2'],
                                  pcdf_data['water_heating_effy_sch3'])
        else:
            summereff = pcdf_data['water_heating_effy_sch2']
        wintereff = sys.effy_space

        water_effy = weighted_effy(self.Q_space, Q_water, wintereff, summereff)

        if self.summer_immersion:
            for i in range(5, 9):
                water_effy[i] = 100

        return water_effy

    # Dynamically set the efficiency methods to micro chp methods, overriding the default ones.
    sys.water_heat_effy = types.MethodType(micro_chp_water_effy, sys)
    sys.space_heat_effy = types.MethodType(micro_chp_space_effy, sys)


def micro_chp_from_pcdf(dwelling, pcdf_data, fuel, use_immersion_in_summer):
    # !!! Probably should check provision type in here for consistency
    # !!! with water sys inputs (e.g. summer immersion, etc)
    sys = HeatingSystem(HeatingTypes.microchp,
                        -1,
                        -1,
                        summer_immersion=use_immersion_in_summer,
                        has_flue_fan=False,  # !!!
                        has_ch_pump=pcdf_data['separate_circulator'],
                        table2b_row=2,
                        default_secondary_fraction=0,  # overwritten below
                        fuel=fuel)

    sys.responsiveness = USE_TABLE_4D_FOR_RESPONSIVENESS

    # It seems that oil based micro chp needs to include a 10W gain
    # inside the dwelling, but doesn't include the electricity
    # consumption of the pump
    if fuel.type == FuelTypes.OIL:
        dwelling.main_heating_oil_pump_inside_dwelling = True
    # !!! Effy adjustments for condensing underfloor heating can be applied?

    if pcdf_data['hw_vessel'] == 1:
        # integral vessel
        dwelling.measured_cylinder_loss = 0
        dwelling.hw_cylinder_volume = 0
        dwelling.has_cylinderstat = True
        dwelling.has_hw_time_control = True
        dwelling.cylinder_in_heated_space = False
        sys.has_integral_store = True
    else:
        sys.has_integral_store = False

    if not dwelling.get('secondary_heating_type_code'):
        dwelling.secondary_heating_type_code = 693
        dwelling.secondary_sys_fuel = dwelling.electricity_tariff

    if not pcdf_data['net_specific_elec_consumed_sch3'] is None:
        dwelling.chp_water_elec = sch3_calc(dwelling,
                                            pcdf_data['net_specific_elec_consumed_sch2'],
                                            pcdf_data['net_specific_elec_consumed_sch3'])
    else:
        dwelling.chp_water_elec = pcdf_data['net_specific_elec_consumed_sch2']

    add_appendix_n_equations_microchp(dwelling, sys, pcdf_data)
    return sys


def heat_pump_from_pcdf(dwelling, pcdf_data, fuel, use_immersion_in_summer):
    # !!! Probably should check provision type in here for consistency
    # !!! with water sys inputs (e.g. summer immersion, etc)
    sys = HeatingSystem(HeatingTypes.pcdf_heat_pump,
                        -1,
                        -1,
                        summer_immersion=use_immersion_in_summer,
                        has_flue_fan=False,  # !!!
                        has_ch_pump=pcdf_data['separate_circulator'],
                        table2b_row=2,
                        default_secondary_fraction=0,  # overwritten below
                        fuel=fuel)

    if pcdf_data['emitter_type'] == "4":
        sys.responsiveness = 1
        sys.has_warm_air_fan = True
        sys.has_ch_pump = False
    else:
        # !!! Assumes we have a heat emitter - is that always the case?
        sys.responsiveness = USE_TABLE_4D_FOR_RESPONSIVENESS

    if pcdf_data['hw_vessel'] == 1:
        # integral vessel
        dwelling.measured_cylinder_loss = pcdf_data['vessel_heat_loss']
        dwelling.hw_cylinder_volume = pcdf_data['vessel_volume']
        dwelling.has_cylinderstat = True
        dwelling.has_hw_time_control = True
        dwelling.cylinder_in_heated_space = False  # !!! Not sure why this applies?
        sys.has_integral_store = True
    else:
        sys.has_integral_store = False

    if not dwelling.get('secondary_heating_type_code'):
        dwelling.secondary_heating_type_code = 693
        dwelling.secondary_sys_fuel = dwelling.electricity_tariff

    add_appendix_n_equations_heat_pumps(dwelling, sys, pcdf_data)
    return sys