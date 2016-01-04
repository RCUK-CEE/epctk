"""
Module to load raw data from PCDF file

"""

import os

from .sap_types import VentilationTypes, DuctTypes
from .utils import int_or_none, float_or_none

PCDF_DATA_FILE = os.path.join(os.path.dirname(__file__), 'data', 'pcdf2009.dat')
PCDF = None

FUELS = {'1': 'Gas',
         '2': 'LPG',
         '4': 'Oil',
         '12': 'Smokeless',
         '71': 'Biodiesel any',
         '72': 'Biodiesel UCOME',
         '73': 'Rapeseed oil',
         '74': 'Mineral or biofuel',
         '75': 'B30K',
         }

main_types = {'1': 'Regular',
              '2': 'Combi',
              '3': 'CPSU'}

subsidiary_types = {'0': 'Normal',
                    '1': 'with integral PFGHRD'}

condensing = {'1': False,
              '2': True}

flue_types = {'0': 'unknown',
              '1': 'open', '2':
                  'room-sealed',
              '3': 'open or room-sealed'}

flue_fan = {'0': 'False',
            '1': 'False',
            '2': 'True'}

has_keep_hot = {'': 'None',
                '0': 'None',
                '1': 'gas/oil',
                '2': 'elec',
                '3': 'gas/oil and elec'}

has_keep_hot_timer = {'': False,
                      '0': False,
                      '1': True}

storage_types = {'0': 'Unknown',
                 '1': 'storage combi with primary store',
                 '2': 'storage combi with secondary store',
                 '3': 'CPSU'}

mev_configurations = {'1': 'room_kitchen',
                      '2': 'room_other',
                      '3': 'duct_kitchen',
                      '4': 'duct_other',
                      '5': 'wall_kitchen',
                      '6': 'wall_other'}

MV_TYPE_MAPPING = {
    '1': [VentilationTypes.MEV_CENTRALISED, ],
    '2': [VentilationTypes.MEV_DECENTRALISED,
          VentilationTypes.PIV_FROM_OUTSIDE],
    '3': [VentilationTypes.MV,
          VentilationTypes.MVHR, ],
    '10': [],
}


def row_id(table_id, toks):
    if table_id == '191':
        return toks[1]
    else:
        return toks[0]


def load_pcdf():
    print(("LOADING PCDF: ", PCDF_DATA_FILE))
    with open(PCDF_DATA_FILE, 'rU') as datafile:
        pcdf_data = dict()
        current = dict()
        currentid = None
        for line in datafile:
            if line[0] == "#":
                continue

            tokens = line.split(',')
            if line[0] == "$":
                # new table
                currentid = tokens[0][1:]
                current = dict()
                pcdf_data[currentid] = current
            else:
                # existing table
                id = row_id(currentid, tokens)
                current[id] = tokens
    global PCDF
    PCDF = pcdf_data


def get_table(table):
    if PCDF is None:
        load_pcdf()
    return PCDF[table]


def get_product(table, product_id):
    return get_table(table)[product_id]


def get_boiler(boiler_id):
    try:
        fields = get_product('104', boiler_id)
    except KeyError:
        return None
    result = dict(
        sedbuk_idx=str(fields[0]),
        manufacturer=str(fields[3]),
        brand=str(fields[4]),
        model=str(fields[5]),
        model_qualifier=str(fields[6]),
        fuel=FUELS[fields[10]],
        main_type=main_types[fields[13]],
        subsidiary_type=subsidiary_types[fields[14]],
        subsidiary_type_table=fields[15],
        subsidiary_type_index=fields[16],
        condensing=condensing[fields[17]],
        flue_type=flue_types[fields[18]],
        fan_assisted_flue=flue_fan[fields[19]],
        boiler_power_top_of_range=fields[21],
        effy_2009=float(fields[23]),
        winter_effy=float(fields[24]),
        summer_effy=float(fields[25]),
        effy_2005=float(fields[27]),
        sap_appendixD_eqn=str(fields[31]),
        storage_type=storage_types[fields[36]],
        store_boiler_volume=float_or_none(fields[39]),
        store_solar_volume=float_or_none(fields[40]),
        store_insulation_mms=float_or_none(fields[41]),
        separate_dhw_tests=fields[45])
    if len(fields) >= 49:
        extra = dict(
            rejected_energy_r1=fields[48],
            storage_loss_factor_f1=float_or_none(fields[49]))
        result.update(extra)

    if len(fields) >= 53:
        extra = dict(
            storage_loss_factor_f2=float_or_none(fields[53]),
            rejected_factor_f3=fields[54],
            keep_hot_facility=has_keep_hot[fields[55]],
            keep_hot_timer=has_keep_hot_timer[fields[56]],
            keep_hot_elec_heater=0. if fields[
                                           57] == '\n' else float(fields[57]),
        )
        result.update(extra)

    return result


def get_solid_fuel_boiler(id):
    try:
        fields = get_product('121', id)
    except KeyError:
        return None
    return dict(
        sedbuk_idx=str(fields[0]),
        manufacturer=str(fields[3]),
        brand=str(fields[4]),
        model=str(fields[5]),
        fuel=FUELS[fields[10]],
        main_type=fields[11],
        fan_assisted=flue_fan[fields[13]],
        seasonal_effy=fields[19],
        nominal_fuel_use=fields[21],
        nominal_heat_to_water=fields[22],
        nominal_heat_to_room=fields[23],
        part_load_fuel_use=fields[24],
        part_load_heat_to_water=fields[25],
        part_load_heat_to_room=fields[26],
    )


def get_twin_burner_cooker_boiler(product_id):
    try:
        fields = get_product('131', product_id)
    except KeyError:
        return None
    return dict(
        sedbuk_idx=str(fields[0]),
        manufacturer=str(fields[3], encoding='latin-1'),
        brand=str(fields[4]),
        model=str(fields[5]),
        fuel=FUELS[fields[10]],
        condensing=condensing[fields[12]],
        flue_type=fields[13],
        fan_assisted=fields[14],
        case_loss_at_full_output=float(fields[17]),
        full_output_power=float(fields[18]),
        winter_effy=float(fields[21]),
        summer_effy=float(fields[22]),

    )


def get_heat_pump(id):
    try:
        fields = get_product('361', id)
    except KeyError:
        return None
    sys = dict(
        sedbuk_idx=str(fields[0]),
        manufacturer=str(fields[4], encoding='latin-1'),
        brand=str(fields[5]),
        model=str(fields[6]),
        fuel=str(fields[11]),
        emitter_type=str(fields[12]),
        flue_type=str(fields[13]),
        heat_source=str(fields[14]),
        service_provision=str(fields[15]),
        hw_vessel=int(fields[16]),
        vessel_volume=float_or_none(fields[17]),
        vessel_heat_loss=float_or_none(fields[18]),
        vessel_heat_exchanger=float_or_none(fields[19]),
        water_heating_effy_sch2=float_or_none(fields[21]),
        net_specific_elec_consumed_sch2=str(fields[22]),
        water_heating_effy_sch3=float_or_none(fields[23]),
        net_specific_elec_consumed_sch3=str(fields[24]),
    )
    if len(fields) > 25:
        sys.update(dict(
            reversible=fields[25],
            eer=fields[26],
            maximum_output=float(fields[27]),
            heating_duration=fields[28],
            mev_mvhr_index=fields[29],
            separate_circulator=fields[30] != "1",
            number_of_air_flow_rates=int_or_none(fields[32]),
            air_flow_1=float_or_none(fields[33]),
            air_flow_2=float_or_none(fields[34]),
            air_flow_3=float_or_none(fields[35]),
            number_of_psrs=int(fields[36])
        ))

        psr_datasets = []
        field_offset = 0
        for airflowrate in range(sys['number_of_air_flow_rates'] if sys['number_of_air_flow_rates'] != None else 1):
            psr_dataset = []
            for i in range(sys['number_of_psrs']):
                psr_data = dict(
                    psr=float(fields[37 + field_offset]),
                    space_effy=float(fields[38 + field_offset]),
                    specific_elec_consumed=fields[39 + field_offset])
                if len(fields) > 40 + field_offset:
                    psr_data['running_hours'] = float_or_none(
                        fields[40 + field_offset])
                else:
                    psr_data['running_hours'] = None
                field_offset += 4

                psr_dataset.append(psr_data)
            psr_datasets.append(psr_dataset)
        sys['psr_datasets'] = psr_datasets

    return sys


def get_microchp(id):
    try:
        fields = get_product('142', id)
    except KeyError:
        return None
    sys = dict(
        sedbuk_idx=str(fields[0]),
        manufacturer=str(fields[4], encoding='latin-1'),
        brand=str(fields[5]),
        model=str(fields[6]),
        fuel=str(fields[10]),
        condensing=fields[11],
        flue_type=fields[12],
        service_provision=fields[13],
        hw_vessel=int(fields[14]),
        water_heating_effy_sch2=float_or_none(fields[16]),
        net_specific_elec_consumed_sch2=float_or_none(fields[17]),
        water_heating_effy_sch3=float_or_none(fields[18]),
        net_specific_elec_consumed_sch3=float_or_none(fields[19]),
    )
    if len(fields) > 21:
        sys.update(dict(
            maximum_output=float(fields[21]),
            heating_duration=fields[22],
            separate_circulator=fields[23] != "1",
            number_of_psrs=int(fields[24])
        ))

        psr_dataset = []
        field_offset = 0
        for i in range(sys['number_of_psrs']):
            psr_data = dict(
                psr=float(fields[25 + field_offset]),
                space_effy=float(fields[26 + field_offset]),
                specific_elec_consumed=float(fields[27 + field_offset]))
            field_offset += 3
            psr_dataset.append(psr_data)
        sys['psr_datasets'] = [psr_dataset, ]

    return sys


def get_mev_system(mev_id):
    fields = get_product('322', mev_id)
    sys = dict(
        sedbuk_idx=str(fields[0]),
        manufacturer=str(fields[3]),
        brand=str(fields[4]),
        model=str(fields[5]),
        main_type=fields[9],
        duct_type=fields[10],
        number_of_configs=int(fields[11]),
        configs=dict())

    for i in range(sys['number_of_configs']):
        configuration = mev_configurations[fields[12 + i * 4]]
        config = dict(
            sfp=float(fields[15 + i * 4]) if fields[
                                                 15 + i * 4] != "" else None,
        )
        sys['configs'][configuration] = config
    return sys


def get_wwhr_system(wwhr_id):
    fields = get_product('351', wwhr_id)
    sys = dict(
        idx=str(fields[0]),
        manufacturer=str(fields[3]),
        brand=str(fields[4]),
        model=str(fields[5]),
        effy_mixer_shower=float(fields[9]),
        utilisation_mixer_shower=float(fields[10]))
    return sys


def get_fghr_system(fghr_id):
    fields = get_product('312', fghr_id)

    sys = dict(
        idx=str(fields[0]),
        manufacturer=str(fields[3]),
        brand=str(fields[4]),
        model=str(fields[5]),
        applicable_fuel=fields[9],
        applicable_boiler_types=fields[11],
        integral_only=fields[12],
        heat_store=fields[13],
        heat_store_total_volume=float_or_none(fields[14]),
        heat_store_recaptured_volume=fields[15],
        heat_store_loss_rate=float_or_none(fields[16]),
        direct_total_heat_recovered=float(fields[17]),
        direct_useful_heat_recovered=float(fields[18]),
        power_consumption=fields[19],
        has_pv_module=fields[20] == "1",
        cable_loss=float_or_none(fields[21]),
        number_of_equations=int(fields[22]))

    sys['equations_combi_without_keephot_without_ext_store'] = []
    sys['equations_other'] = []
    for i in range(sys['number_of_equations']):
        if fields[24 + i * 7] != '':
            sys['equations_combi_without_keephot_without_ext_store'].append(
                dict(
                    space_heating_requirement=float(fields[23 + i * 7]),
                    a=float(fields[24 + i * 7]),
                    b=float(fields[25 + i * 7]),
                    c=float(fields[26 + i * 7])))

        if len(fields) > 27 + i * 7 and fields[27 + i * 7] != '':
            sys['equations_other'].append(
                dict(
                    space_heating_requirement=float(fields[23 + i * 7]),
                    a=float_or_none(fields[27 + i * 7]),
                    b=float_or_none(fields[28 + i * 7]),
                    c=float_or_none(fields[29 + i * 7])))

    return sys


def pcdf_mech_vent_in_use_factors():
    """
    Construct tables for mechanical ventilation in use factors

    :return:
    """
    factors_table = get_table("329")
    sfp_factor_table = dict()
    sfp_factor_table_approved = dict()
    hr_factor_table = dict()
    hr_factor_table_approved = dict()

    for row in list(factors_table.values()):
        vent_types = MV_TYPE_MAPPING[row[0]]
        sfp_flexible = float_or_none(row[1])
        sfp_rigid = float_or_none(row[2])
        sfp_no_duct = float_or_none(row[3])
        mvhr_uninsulated = float_or_none(row[4])
        mvhr_insulated = float_or_none(row[5])
        sfp_flexible_approved = float_or_none(row[6])
        sfp_rigid_approved = float_or_none(row[7])
        sfp_no_duct_approved = float_or_none(row[8])
        mvhr_uninsulated_approved = float_or_none(row[9])
        mvhr_insulated_approved = float_or_none(row[10])

        for vent_type in vent_types:
            sfp_factor_table[vent_type] = {
                DuctTypes.FLEXIBLE: sfp_flexible,  # Uninsulated
                DuctTypes.FLEXIBLE_INSULATED: sfp_flexible,
                DuctTypes.RIGID: sfp_rigid,  # Uninsulated
                DuctTypes.RIGID_INSULATED: sfp_rigid,
                DuctTypes.NONE: sfp_no_duct,
            }

            sfp_factor_table_approved[vent_type] = {
                DuctTypes.FLEXIBLE: sfp_flexible_approved,
                DuctTypes.FLEXIBLE_INSULATED: sfp_flexible_approved,
                DuctTypes.RIGID: sfp_rigid_approved,
                DuctTypes.RIGID_INSULATED: sfp_rigid_approved,
                DuctTypes.NONE: sfp_no_duct_approved,
            }

            if vent_type == VentilationTypes.MVHR:
                hr_factor_table[vent_type] = {
                    DuctTypes.FLEXIBLE: mvhr_uninsulated,  # Uninsulated
                    DuctTypes.FLEXIBLE_INSULATED: mvhr_insulated,
                    DuctTypes.RIGID: mvhr_uninsulated,  # Uninsulated
                    DuctTypes.RIGID_INSULATED: mvhr_insulated,
                }
                hr_factor_table_approved[vent_type] = {
                    # Uninsulated
                    DuctTypes.FLEXIBLE: mvhr_uninsulated_approved,
                    DuctTypes.FLEXIBLE_INSULATED: mvhr_insulated_approved,
                    DuctTypes.RIGID: mvhr_uninsulated_approved,  # Uninsulated
                    DuctTypes.RIGID_INSULATED: mvhr_insulated_approved,
                }

    return sfp_factor_table, sfp_factor_table_approved, hr_factor_table, hr_factor_table_approved


def pcdf_fuel_prices():
    fuel_table = get_table("191")
    fuels = dict()
    for row in list(fuel_table.values()):
        fuels[int(row[1])] = dict(
            category=int(row[0]),
            fuel=int(row[1]),
            standing_charge=float(row[2]),
            price=float(row[3])
        )
    return fuels



# Lazy load these, to give a chance to swap the pcdf database file if necessary
# FIXME: if it's possible to swap the PCDF file, make this explicit!

TABLE_4h_in_use = None
TABLE_4h_in_use_approved_scheme = None
TABLE_4h_hr_effy_approved_scheme = None


def load_4h_tables():
    global TABLE_4h_in_use, TABLE_4h_in_use_approved_scheme, TABLE_4h_hr_effy, TABLE_4h_hr_effy_approved_scheme

    (TABLE_4h_in_use,
     TABLE_4h_in_use_approved_scheme,
     TABLE_4h_hr_effy,
     TABLE_4h_hr_effy_approved_scheme
     ) = pcdf_mech_vent_in_use_factors()


def mech_vent_in_use_factor(vent_type, duct_type, approved_scheme):
    """
    Table 4h: In-use factors for mechanical ventilation systems

    :param vent_type:
    :param duct_type:
    :param approved_scheme:
    :return:
    """
    if TABLE_4h_in_use is None:
        load_4h_tables()

    if approved_scheme:
        return TABLE_4h_in_use_approved_scheme[vent_type][duct_type]
    else:
        return TABLE_4h_in_use[vent_type][duct_type]


def mech_vent_in_use_factor_hr(vent_type, duct_type, approved_scheme):
    """
    Table 4h: In-use factors for mechanical ventilation systems with heat recovery

    :param vent_type:
    :param duct_type:
    :param approved_scheme:
    :return:
    """
    if TABLE_4h_in_use is None:
        load_4h_tables()

    if approved_scheme:
        return TABLE_4h_hr_effy_approved_scheme[vent_type][duct_type]
    else:
        return TABLE_4h_hr_effy[vent_type][duct_type]