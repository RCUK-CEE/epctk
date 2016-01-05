import logging


def check_result(calctype, actual, target, desc, max_err=0.1):
    if abs(actual - target) > max_err:
        print(("ERROR: %s: Mismatched %s: %.2f vs %.2f" % (
            calctype, desc, actual, target)))


def check_monthly_result(calctype, actual, target, desc, max_err=0.1):
    assert len(actual) == len(target)
    assert len(actual) == 12

    for month in range(12):
        if abs(actual[month] - target[month]) > max_err:
            print(("ERROR: %s: Mismatched %s (month %d): %.2f vs %.2f" % (
                calctype, desc, month + 1, actual[month], target[month])))
            return


def check_summer_monthly_result(calctype, actual, target, desc, max_err=0.1):
    assert len(actual) == len(target)
    assert len(actual) == 12

    for i in range(3):
        month = i + 5
        if abs(actual[month] - target[month]) > max_err:
            print(("ERROR: %s: Mismatched %s (month %d): %.2f vs %.2f" % (
                calctype, desc, month + 1, actual[month], target[month])))
            return


def sum_summer(l):
    return sum(l[5:9])


def sum_winter(l):
    return sum(l[0:5]) + sum(l[9:])


def float_or_zero(f):
    return float(f) if f != "" else 0


def check_cost_results(calctype, d, results):
    if results.cost_heating_main != "":
        check_result(calctype, d.cost_heating_main,
                     float(results.cost_heating_main),
                     "main heating cost", .15)
    elif results.cost_heating_main_1 != "":
        check_result(calctype, d.cost_heating_main,
                     float(results.cost_heating_main_1),
                     "main heating 1 cost", .15)
        check_result(calctype, d.cost_heating_main_2,
                     float(results.cost_heating_main_2),
                     "main heating 2 cost", 0.15)
    elif results.cost_heating_main_high_rate != "":
        check_result(calctype, d.cost_heating_main,
                     (float(results.cost_heating_main_high_rate) +
                      float(results.cost_heating_main_low_rate)),
                     "main heating cost", .15)
    else:
        check_result(calctype, d.cost_heating_main,
                     (float_or_zero(results.cost_heating_community_1) +
                      float_or_zero(results.cost_heating_community_2) +
                      float_or_zero(results.cost_heating_community_3) +
                      float_or_zero(results.cost_heating_community_4) +
                      float_or_zero(results.cost_heating_community_5)),
                     "community space heating cost", .15)

    check_result(calctype, d.cost_heating_secondary,
                 float(results.cost_heating_secondary),
                 "secondary heating cost", 0.15)

    water_cost = 0
    if results.cost_water_heat != "":
        water_cost += float(results.cost_water_heat)
    if results.cost_water_heat_high_rate != "":
        water_cost += float(results.cost_water_heat_high_rate)
        water_cost += float(results.cost_water_heat_low_rate)
    if results.cost_water_heat_immersion != "":
        water_cost += float(results.cost_water_heat_immersion)
    if results.cost_water_heat_chp != "":
        water_cost += float(results.cost_water_heat_chp)
        water_cost += float(results.cost_water_heat_boilers)
    else:
        water_cost += (float_or_zero(results.cost_community_water_heat_1) +
                       float_or_zero(results.cost_community_water_heat_2) +
                       float_or_zero(results.cost_community_water_heat_3) +
                       float_or_zero(results.cost_community_water_heat_4) +
                       float_or_zero(results.cost_community_water_heat_5))

    check_result(calctype, d.cost_water + d.cost_water_summer_immersion,
                 water_cost,
                 "water heating cost", .15)

    fan_and_pump_cost = float(results.cost_fans_and_pumps)

    if results.cost_fans_and_pumps_keep_hot != "":
        fan_and_pump_cost += float(results.cost_fans_and_pumps_keep_hot)
    if results.cost_solar_water_pump != "":
        fan_and_pump_cost += float(results.cost_solar_water_pump)

    check_result(calctype, d.cost_fans_and_pumps,
                 fan_and_pump_cost,
                 "fans and pumps cost", .15)

    if results.cost_mech_vent != "":
        check_result(calctype, d.cost_mech_vent_fans,
                     float(results.cost_mech_vent),
                     "mech vent fan cost", 0.01)

    check_result(calctype, d.cost_lighting,
                 float(results.cost_lighting),
                 "lighting cost", .25)

    if results.cost_cooling != "":
        check_result(calctype, d.cost_cooling,
                     float(results.cost_cooling),
                     "cooling cost", .15)
    else:
        check_result(calctype, d.cost_cooling,
                     0,
                     "cooling cost", .15)

    if results.cost_standing != "":
        check_result(calctype, d.cost_standing,
                     float(results.cost_standing),
                     "standing cost", .15)
    else:
        check_result(calctype, d.cost_standing,
                     0,
                     "standing cost", 0)

    check_result(calctype, d.fuel_cost,
                 float(results.cost_total),
                 "total fuel cost", 0.5)


def check_emissions_results(calctype, d, results):
    if results.emissions_heating_main != "":
        check_result(calctype, d.emissions_heating_main,
                     float(results.emissions_heating_main),
                     "main heating emissions", 1)
    elif results.emissions_heating_main_1 != "":
        check_result(calctype, d.emissions_heating_main,
                     float(results.emissions_heating_main_1),
                     "main heating 1 emissions", 1)
        check_result(calctype, d.emissions_heating_main_2,
                     float(results.emissions_heating_main_2),
                     "main heating 2 emissions", 1)
    else:
        # community heating
        emissions_not_chp = (float_or_zero(results.emissions_community_1) +
                             float_or_zero(results.emissions_community_2) +
                             float_or_zero(results.emissions_community_3) +
                             float_or_zero(results.emissions_community_4) +
                             float_or_zero(results.emissions_community_5))

        emissions_chp = 0
        if results.emissions_heating_main_chp != "":
            emissions_chp += float(results.emissions_heating_main_chp)
        if results.emissions_water_heat_chp != "":
            emissions_chp += float(results.emissions_water_heat_chp)

        # !!! A nasty little hack here, because tests case 6g has two
        # !!! emissions results labelled (368)
        prev = None
        res_368 = 0
        for r in results:
            if r == "(368)":
                res_368 += float(prev)
            prev = r
        emissions_not_chp = emissions_not_chp - \
            float_or_zero(results.emissions_community_2) + res_368
        # !!!!! end of nastiness

        check_result(calctype, d.emissions_heating_main + d.emissions_water,
                     emissions_not_chp + emissions_chp,
                     "community space heating emissions", 1)

        chp_credits = 0
        if results.emissions_heating_main_chp_elec_credits != "":
            chp_credits += float(
                results.emissions_heating_main_chp_elec_credits)
        if results.emissions_water_heat_chp_elec_credits != "":
            chp_credits += float(results.emissions_water_heat_chp_elec_credits)

        if hasattr(d, 'emissions_community_elec_credits'):
            check_result(calctype, d.emissions_community_elec_credits,
                         chp_credits,
                         "community space heating elec credit emissions", 1)
        else:
            check_result(calctype, 0,
                         chp_credits,
                         "community space heating elec credit emissions", 1)

    if results.emissions_heating_secondary != "":
        check_result(calctype, d.emissions_heating_secondary,
                     float(results.emissions_heating_secondary),
                     "secondary heating emissions", 1)
    else:
        check_result(calctype, d.emissions_heating_secondary,
                     0, "secondary heating emissions", 1)

    if results.emissions_water_heat != "":
        check_result(calctype, d.emissions_water,
                     float(results.emissions_water_heat),
                     "water heating emissions", 1)

    if results.emissions_water_heat_immersion != "":
        check_result(calctype, d.emissions_water_summer_immersion,
                     float(results.emissions_water_heat_immersion),
                     "summer immersion water heating emissions", 1)

    check_result(
        calctype, d.emissions_fans_and_pumps + d.emissions_mech_vent_fans,
        float(results.emissions_fans_and_pumps),
        "fans and pumps emissions", 1)

    check_result(calctype, d.emissions_lighting,
                 float(results.emissions_lighting),
                 "lighting emissions", 1)

    if results.emissions_cooling != "":
        check_result(calctype, d.emissions_cooling,
                     float(results.emissions_cooling),
                     "cooling emissions", 1)
    else:
        check_result(calctype, d.emissions_cooling,
                     0,
                     "cooling emissions", 1)

    check_result(calctype, d.emissions,
                 float(results.emissions_total),
                 "total emissions", 1)


def check_primary_energy_results(calctype, d, results):
    check_result(calctype, d.primary_energy,
                 float(results.primary_energy_total),
                 "total primary energy", 5.5)


def check_renewables(calctype, d, results):
    if results.energy_pv != "":
        check_result(calctype, d.pv_electricity,
                     -float(results.energy_pv),
                     "PV energy", 1)
        check_result(calctype, d.cost_pv,
                     float(results.cost_pv),
                     "PV cost offset", .15)
        check_result(calctype, d.emissions_pv,
                     float(results.emissions_pv),
                     "PV emissions offset", 1)
    else:
        check_result(calctype, d.pv_electricity,
                     0,
                     "PV energy", 0)

    if results.energy_wind != "":
        check_result(calctype, d.wind_electricity,
                     -float(results.energy_wind),
                     "wind energy", 1)
        check_result(calctype, d.cost_wind,
                     float(results.cost_wind),
                     "wind cost offset", .15)
        check_result(calctype, d.emissions_wind,
                     float(results.emissions_wind),
                     "wind emissions offset", 1)
    else:
        check_result(calctype, d.wind_electricity,
                     0,
                     "wind energy", 0)

    if results.energy_chp != "":
        check_result(calctype, d.chp_electricity,
                     -float(results.energy_chp),
                     "chp energy", 1)
        check_result(calctype, d.cost_offset,
                     float(results.cost_chp),
                     "chp cost offset", .15)
        check_result(calctype, d.emissions_offset,
                     float(results.emissions_chp),
                     "chp emissions offset", 1)
    else:
        check_result(calctype, d.chp_electricity,
                     0,
                     "chp energy", 0)


def check_basic_nonsystem_results(calctype, d, results):
    check_result(calctype, d.h[0],
                 float(results.heat_loss[0]), "January heat loss coeff")

    check_result(calctype, d.solar_gain_winter[0],
                 float(results.solar_heat_gain[0]), "January solar gain", .5)
    check_result(calctype, d.winter_heat_gains[0],
                 float(results.total_internal_heat_gain[0]), "January total heat gain", .5)
    check_result(calctype, sum(d.Q_required),
                 float(results.heat_required), "space heat required", 2)

    if results.cooling_required != "":
        check_result(calctype, sum(d.Q_cooling_required),
                     float(results.cooling_required), "cooling required", 1)
    else:
        check_result(calctype, sum(d.Q_cooling_required),
                     0, "cooling required", 1)


def check_basic_system_results(calctype, d, results):
    check_result(calctype, d.Q_fans_and_pumps + d.Q_mech_vent_fans,
                 float(results.fan_and_pump_energy), "fan and pump energy", .5)

    if results.water_heater_immersion_output != "":
        check_result(calctype, sum_winter(d.output_from_water_heater),
                     float(results.water_heater_output), "water heater output")
        check_result(calctype, sum_summer(d.output_from_water_heater),
                     float(results.water_heater_immersion_output), "immersion heater output")
    else:
        check_result(calctype, sum(d.output_from_water_heater),
                     float(results.water_heater_output), "water heater output")

    if results.space_heat_fuel_1_main != "":
        check_result(calctype, d.Q_spaceheat_main[0],
                     float(results.space_heat_fuel_1_main[0]),
                     "January main sys 1 space heat fuel", 1)
        check_result(calctype, d.Q_spaceheat_main_2[0],
                     float(results.space_heat_fuel_2_main[0]),
                     "January main sys 2 space heat fuel", 1)
        check_result(calctype, sum(d.Q_spaceheat_main),
                     sum(map(float, results.space_heat_fuel_1_main)),
                     "annual main sys 1 space heat fuel", 2)
        check_result(calctype, sum(d.Q_spaceheat_main_2),
                     sum(map(float, results.space_heat_fuel_2_main)),
                     "annual main sys 2 space heat fuel", 2)
    elif results.space_heat_fuel_main != "":
        check_result(calctype, d.Q_spaceheat_main[0],
                     float(results.space_heat_fuel_main[0]),
                     "January main sys space heat fuel", 1)
        check_result(calctype, sum(d.Q_spaceheat_main),
                     sum(map(float, results.space_heat_fuel_main)),
                     "annual main sys space heat fuel", 3)
    else:
        # community heating
        check_result(calctype, sum(d.Q_spaceheat_main),
                     (float_or_zero(results.space_heat_fuel_community_1) +
                      float_or_zero(results.space_heat_fuel_community_2) +
                      float_or_zero(results.space_heat_fuel_community_3) +
                      float_or_zero(results.space_heat_fuel_community_4) +
                      float_or_zero(results.space_heat_fuel_community_5)),
                     "annual community sys space heat fuel", 3)

    try:
        check_result(calctype, sum(d.Q_spaceheat_secondary),
                     sum(map(float, results.space_heat_fuel_secondary)),
                     "annual secondary sys space heat fuel", 2)
        check_result(calctype, d.Q_spaceheat_secondary[0],
                     float(results.space_heat_fuel_secondary[0]),
                     "January secondary sys space heat fuel", 1)
    except ValueError:
        check_result(calctype, sum(d.Q_spaceheat_secondary),
                     float(results.space_heat_fuel_secondary),
                     "annual secondary sys space heat fuel", 2)

    if results.water_heat_fuel != "":
        # community heating results don't include this
        check_result(calctype, d.Q_waterheat[0],
                     float(results.water_heat_fuel[0]),
                     "January water heat fuel", 1)

    if results.water_heat_fuel_immersion != "":
        check_result(calctype, sum_winter(d.Q_waterheat),
                     sum(map(float, results.water_heat_fuel)),
                     "annual water heat fuel", 1.01)
        check_result(calctype, sum_summer(list(map(int, d.Q_waterheat + .5))),
                     sum(map(float, results.water_heat_fuel_immersion)),
                     "annual immersion heat fuel", 1)
    elif results.water_heat_fuel != "":
        check_result(calctype, sum(map(int, d.Q_waterheat + .5)),
                     sum(map(float, results.water_heat_fuel)),
                     "annual water fuel", 3)

    if results.space_cooling_fuel != "":
        check_result(calctype, d.Q_spacecooling[5],
                     float(results.space_cooling_fuel[5]),
                     "June space cooling fuel", .5)
        check_result(calctype, sum(d.Q_spacecooling),
                     sum(map(float, results.space_cooling_fuel)),
                     "annual space cooling fuel", 1)
    else:
        check_result(calctype, d.Q_spacecooling[0],
                     0,
                     "January space cooling fuel", 1)
        check_result(calctype, sum(map(int, d.Q_spacecooling + .5)),
                     0,
                     "annual space cooling fuel", 1)


def check_basic_calc_results(calctype, d, results):
    check_basic_nonsystem_results(calctype, d, results)
    check_basic_system_results(calctype, d, results)


def check_er_results(label, d, res):
    check_basic_calc_results(label, d, res)
    check_cost_results(label, d, res)
    check_emissions_results(label, d, res)
    check_renewables(label, d, res)
    check_primary_energy_results(label, d, res)
    check_result(label, d.sap_value,
                 float(res.sap_value),
                 "sap rating (rounded)", 0.5)
    check_result(label, d.sap_value,
                 float(res.sap_value_unrounded),
                 "sap rating (rounded)", 0.01)


def check_fee(d, res):
    if res.fee == "":
        return

    check_basic_nonsystem_results("FEE", d, res.fee)
    check_result("FEE", d.fee_rating,
                 float(res.fee.fee_rating),
                 "fee rating", 0.05)


def check_der(d, res):
    if res.der == "":
        logging.warn("No DER section")
        return

    check_basic_calc_results("DER", d, res.der)
    check_emissions_results("DER", d, res.der)
    check_result("DER", d.der_rating,
                 float(res.der.der_rating),
                 "der", 0.01)


def check_ter(d, res):
    if res.ter == "":
        logging.warn("No TER section")
        return

    check_basic_calc_results("TER", d, res.ter)
    # Emissions in TER results use 2006 values, so these checks will
    # be wrong because I use 2010 values and then adjust it later
    # check_emissions_results("TER",d,res.ter)
    check_result("TER", d.ter_rating,
                 float(res.ter.ter_rating),
                 "ter", 0.01)


def check_improvements(d, res):
    if res.improvements == "":
        logging.warning("No TER section")
        return

    if res.improvements.effects == "(none)":
        if len(d.improvement_effects) != 0:
            print(("ERROR: Mismatched number of improvements: %d vs 0" % (len(d.improvements),)))
        return

    if len(d.improvement_effects) != len(res.improvements.effects):
        print(("ERROR: Mismatched number of recommended improvements %d vs %d" % (len(d.improvement_effects), len(res.improvements.effects))))

    for calculated_improvement, correct_improvement in zip(d.improvement_effects, res.improvements.effects):
        if calculated_improvement.tag != correct_improvement.measure:
            print(("ERROR: Mismatched effect tags: %s vs %s" % (
                calculated_improvement.tag, correct_improvement.measure)))
            continue

        check_result("EPC Improvements", calculated_improvement.cost_change,
                     float(correct_improvement.cost_change),
                     "improvement %s cost" % (calculated_improvement.tag,), 1)

        check_result("EPC Improvements", calculated_improvement.sap_change,
                     float(correct_improvement.sap_change),
                     "improvement %s sap" % (calculated_improvement.tag,), .1)

        check_result("EPC Improvements", calculated_improvement.co2_change,
                     float(correct_improvement.co2_change),
                     "improvement %s co2" % (calculated_improvement.tag,), 1)


def check_results(dwelling, dwelling_data):
    # print d.fee_results.report.print_report()
    # print d.er_results.report.print_report()
    # print d.der_results.report.print_report()
    # print d.ter_results.report.print_report()

    check_er_results("ER", dwelling.er_results, dwelling_data.er)
    check_fee(dwelling.fee_results, dwelling_data)
    check_der(dwelling.der_results, dwelling_data)
    check_ter(dwelling.ter_results, dwelling_data)
    check_improvements(dwelling.improvement_results, dwelling_data)
    #check_er_results("EPC improved",d.improved_results,res.improved)


def is_err_calc(res):
    # Some of the tests cases don't have results because they
    # demonstrate invalid calculation inputs
    return res.er_results == ""
