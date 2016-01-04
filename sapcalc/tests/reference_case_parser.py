import logging
from pyparsing import (ParserElement, Optional, Literal,
                       Word, SkipTo, alphas, nums, Group,
                       LineEnd, Forward, OneOrMore, NotAny, Combine)

# WARNING: enabling packrat parse caching can sometimes cause problems with complex grammars.
# Should be fine with this use case
logging.warning("PARSING WITH CACHING ENABLED.")
ParserElement.enablePackrat()

# \ul - underline
# \cf - colour
# \tx - tabstops
# \pard - reset paragraph styles
# \fiN - first line indent
# \liN - line indent
# \fN - ??
integer = Optional("-") + Word("0123456789")
rtf_underline = Literal("\\ulnone") | Literal("\\ul")
rtf_bold = Literal("\\b0") | Literal("\\b")
rtf_colour = Literal("\\cf") + integer
rtf_tabstop = Literal("\\tx") + integer
rtf_para_default = Literal("\\pard")
rtf_indents = (Literal("\\fi") + integer) | (Literal("\\li") + integer)
rtf_superscript = Literal("\\'b")
irrelevant_rtf_codes = rtf_underline | rtf_bold | rtf_colour | rtf_tabstop | rtf_para_default | rtf_indents | rtf_superscript | (
    Literal("\\f") + integer)


"""
BNF:

tab ::= \tab
para_end ::= \par

note ::= LPAREN SkipTo(RPAREN) RPAREN

field_label ::= alphas Optional(note) (SkipTo(:) without containing tab or para_end)
field_text ::= alphas Optional(note)

field ::= field_label : field_value+
field_value ::= field|field_text

primary_field ::= para_end field_label
primary_input ::= primary_field : field_value


"""

tab = Literal("\\tab").suppress()
para_end = Literal("\\par").suppress()

lparen = Literal("(")
rparen = Literal(")")

field_label_separator = Optional(Literal(":").suppress())

note = (lparen.suppress() + SkipTo(rparen, failOn=(para_end | tab)
                                   )('note') + rparen.suppress())

field_value_with_paren = Word(alphas + "-<>=.,+/%()#'& " + nums)('value')
field_value_no_paren = Word(alphas + "-<>=.,+/%#'& " + nums)('value')

# Very annoying - one field in first section is missing a colon
field_label_exception = Literal("Water use <= 125 litres/person/day")

# Ideally field_label should be allowed to contain parentheses iff
# they are balanced
field_label = (field_value_no_paren('label') + Optional(note) + Literal(":") |
               field_label_exception('label')
               )

# Ideally field text should be marked as running to end of line?
field_text = Group(field_value_no_paren + note +
                   LineEnd().suppress()) | Group(field_value_with_paren)

# This misses the "model qualifier" field as that field spans two lines
field_value = Forward()
field = Group(field_label +
              field_label_separator +
              Optional(para_end + OneOrMore(tab)) +
              Group(field_value)('vals'))
field_value << (field | field_text)

primary_field_label = para_end + field_label
table_label = Word(alphas + nums + "().,/- ")
table_entry = Word(alphas + nums + "().,/-[] ")

table_header_row = Group(para_end +
                         Optional(table_label, "") +
                         OneOrMore(OneOrMore(tab) + table_label))
table_row = Group(para_end +
                  Optional(tab) +
                  table_label +
                  OneOrMore(tab + Optional(table_entry, default="")))
table = Group(table_header_row("column_headings") +
              Group(OneOrMore(table_row))("rows"))

primary_input = Group(
    primary_field_label +
    field_label_separator +
    OneOrMore(tab) +
    Group(OneOrMore(table | (Optional(para_end + OneOrMore(tab)) +
                    field_value))
          )('vals'))


heading = Literal("Openings") | Literal(
    "Opening types (continued)") | Literal("Opening types")
blank_line = para_end + (heading | LineEnd())

# filename_line=para_end+Literal("Filename:")+SkipTo(LineEnd())
case_id_line = para_end + Word(alphas + nums) + LineEnd()
postcode_line = para_end + \
    Word(alphas + nums) + Word(alphas + nums) + LineEnd()
title_line = para_end + Literal("Test-") + SkipTo(LineEnd())
filename_line = para_end + \
    Literal("Filename:") + SkipTo(para_end + Literal("Country:"))
year_completed_line = para_end + Literal("Year completed:") + tab
thermal_bridge_table_key_1 = para_end + \
    tab + tab + Literal("[A] accredited detail")
thermal_bridge_table_key_2 = para_end + \
    tab + tab + Literal("[N] not accredited detail")
thermal_bridge_table_key_3 = para_end + tab + \
    tab + Literal("[D] default value SAP Table K1")

awkward_input = filename_line | case_id_line | postcode_line | title_line | year_completed_line | thermal_bridge_table_key_1 | thermal_bridge_table_key_2 | thermal_bridge_table_key_3

inputs = table | primary_input
section_end = Literal("\\sect").suppress()

result_summary_section = Group(para_end + Literal("EPC language") +
                               SkipTo(section_end) +
                               # Skip next section too (improvements summary)
                               section_end +
                               SkipTo(section_end))

floatnum = Word(nums + "-.")
der_word = Word(alphas + nums + "\\/,.+-'():=%_&>").suppress()


def gen_monthly_result_parser(label, name, id):
    return (Literal(label) + Optional(para_end) +
            OneOrMore(tab) +
            Group(((floatnum | no_result) + tab.suppress()) * 12)(name) +
            Literal("(%d)" % (id,)))


def monthly_result(label, name, id):
    global results
    results = results | gen_monthly_result_parser(label, name, id)


def gen_fuel_result_parser(label, name, id):
    cost_name = "cost_%s" % (name,)
    energy_name = "energy_%s" % (name,)
    return (Literal(label) +
            Optional(Literal("(") + SkipTo(")") + Literal(")")) +
            OneOrMore(tab) +
            floatnum(energy_name) + tab +
            (floatnum | no_result) + tab +
            floatnum(cost_name) + tab +
            Literal("(%s)" % (id,)))


def fuel_cost_result(label, name, id):
    global results
    results = results | gen_fuel_result_parser(label, name, id)


def fuel_cost_result_no_label(name, id):
    global results

    cost_name = "cost_%s" % (name,)
    energy_name = "energy_%s" % (name,)
    results = results | (floatnum(energy_name) + tab +
                        (floatnum | no_result) + tab +
                         floatnum(cost_name) + tab +
                         Literal("(%s)" % (id,)))


def emissions_result(label, name, id):
    global results
    emission_name = "emissions_%s" % (name,)
    results = results | (Literal(label) +
                         Optional(Literal("(") + SkipTo(")") + Literal(")")) +
                         OneOrMore(tab) +
                         floatnum + tab +
                        (floatnum | no_result) + tab +
                         floatnum(emission_name) + tab +
                         Literal("(%d)" % (id,)))


def emissions_result_no_label(name, id):
    global results
    emission_name = "emissions_%s" % (name,)
    results = results | (floatnum + tab +
                        (floatnum | no_result) + tab +
                         floatnum(emission_name) + tab +
                         Literal("(%d)" % (id,)))


def labelled_result(label, name, id):
    global results
    results = results | (Literal(label) +
                         OneOrMore(tab) +
                         floatnum(name) +
                         OneOrMore(tab) + Literal("(%s)" % (id,)))


def unnumbered_result(label, name):
    global results
    results = results | (Literal(label) +
                         OneOrMore(tab) +
                         floatnum(name))


def unlabelled_result(name, id):
    global results
    results = results | (floatnum(name) +
                         OneOrMore(tab) + Literal("(%s)" % (id,)))

fee_result = floatnum("fee_rating") + tab + Literal("(109")

# This is used to capture the section of the results sheets that uses
# PCDF prices (which otherwise overwrites the table12 prices section)
results_section_10a_using_pcdf_prices = (
    Literal("Fuel costs using PCDF prices (rev 322)") + SkipTo(Literal("(255)")))("res10a")
results_section_10b_using_pcdf_prices = (
    Literal("Fuel costs using PCDF prices (rev 322)") + SkipTo(Literal("(355)")))("res10b")


# Captures primary energy results section to stop it masking emissions
# section (uses same equations numbers, etc)
results_section_13a = (Literal("Primary energy")
                       + SkipTo(Literal("Primary energy kWh")))("res13a")
results_section_13a_improved = (Literal("Primary energy") + SkipTo(
    Literal("Primary energy (with improvements"), failOn="(272)"))

results = (fee_result)

res_label = Combine(OneOrMore(Word(alphas + "()-")), adjacent=False)
no_result = Literal("\endash").setParseAction(lambda x: 0)

eqn_id = Combine(Literal("(") + integer + Literal(")"))("eqn_id")
mres = Group(res_label("label") + Optional(para_end) +
             OneOrMore(tab) +
             Group(((floatnum | no_result) + tab.suppress()) * 12)("result") +
             eqn_id)


cres = Group(res_label + Optional(Literal("(") + SkipTo(")") + Literal(")")) +
             OneOrMore(tab) + floatnum + tab + (floatnum | no_result) + tab + floatnum + tab + eqn_id)

# results=results|mres#|cres

unnumbered_result("Output from water heater (annual)", "water_heater_output")
unnumbered_result("Output from immersion (annual)",
                  "water_heater_immersion_output")

labelled_result("Total electricity for the above", "fan_and_pump_energy", 231)
labelled_result("Electricity for pumps and fans", "fan_and_pump_energy", 231)
labelled_result("Total electricity for the above", "fan_and_pump_energy", 331)
labelled_result("Electricity for pumps and fans", "fan_and_pump_energy", 331)
labelled_result("Space heating (October to May)", "heat_required", 98)
labelled_result("Space cooling (June to August)", "cooling_required", 107)
labelled_result("SAP rating", "sap_value", 258)
labelled_result("SAP rating (with improvements)", "sap_value", 258)

unnumbered_result("SAP value", "sap_value_unrounded")

labelled_result("SAP rating", "sap_value", 358)
labelled_result(
    "Dwelling Carbon Dioxide Emission Rate (DER)", "der_rating", 273)
labelled_result(
    "Dwelling Carbon Dioxide Emission Rate (DER)", "der_rating", 384)
labelled_result("Target Carbon Dioxide Emission Rate (TER)", "ter_rating", 273)

labelled_result("Total energy cost", "cost_total", 255)
labelled_result("Total energy cost", "cost_total", 355)
labelled_result("Total kg/year", "emissions_total", 272)
labelled_result("Total kg/year", "emissions_total", 383)
labelled_result("Primary energy kWh/year", "primary_energy_total", 272)
labelled_result("Primary energy kWh/year", "primary_energy_total", 383)
labelled_result(
    "Primary energy (with improvements) kWh/year", "primary_energy_total", 272)
labelled_result(
    "Primary energy (with improvements) kWh/year", "primary_energy_total", 383)

monthly_result("Total gains", "total_internal_heat_gain", 84)
monthly_result("Solar gains", "solar_heat_gain", 83)
monthly_result("Heat transfer coeff", "heat_loss", 39)

monthly_result("Space heating fuel (main heating system)",
               "space_heat_fuel_main", 211)
monthly_result("Space heating fuel (main heating system 1)",
               "space_heat_fuel_1_main", 211)
monthly_result("Space heating fuel (main heating system 2)",
               "space_heat_fuel_2_main", 213)
monthly_result("Space heating fuel (secondary)",
               "space_heat_fuel_secondary", 215)
monthly_result("Water heating fuel", "water_heat_fuel", 219)
monthly_result("Water heating fuel   (boiler)", "water_heat_fuel", 219)
monthly_result("Water heating fuel   (heat pump)", "water_heat_fuel", 219)
monthly_result("Water heating fuel   (micro-CHP)", "water_heat_fuel", 219)
monthly_result("Water heating fuel  (immersion)",
               "water_heat_fuel_immersion", 219)
monthly_result("Space cooling fuel", "space_cooling_fuel", 221)

unlabelled_result("space_heat_fuel_community_1", "307a")
unlabelled_result("space_heat_fuel_community_2", "307b")
unlabelled_result("space_heat_fuel_community_3", "307c")
unlabelled_result("space_heat_fuel_community_4", "307d")
unlabelled_result("space_heat_fuel_community_5", "307e")


labelled_result("Space heating fuel for secondary system",
                "space_heat_fuel_secondary", 309)

fuel_cost_result("Space heating - main system", "heating_main", 240)
fuel_cost_result("Space heating - main system 1", "heating_main_1", 240)
fuel_cost_result("Space heating - main system 2", "heating_main_2", 241)
fuel_cost_result("High-rate cost", "heating_main_high_rate", 240)
fuel_cost_result("Low-rate cost", "heating_main_low_rate", 240)
fuel_cost_result_no_label("heating_community_1", "340a")
fuel_cost_result_no_label("heating_community_2", "340b")
fuel_cost_result_no_label("heating_community_3", "340c")
fuel_cost_result_no_label("heating_community_4", "340d")
fuel_cost_result_no_label("heating_community_5", "340e")
fuel_cost_result("Space heating - secondary", "heating_secondary", 242)
fuel_cost_result("Space heating (secondary)", "heating_secondary", 341)
fuel_cost_result("High-rate cost", "water_heat_high_rate", 245)
fuel_cost_result("Low-rate cost", "water_heat_low_rate", 246)
fuel_cost_result(
    "Water heating  (summer immersion)", "water_heat_immersion", 247)
fuel_cost_result("Water heating  (micro-CHP) ", "water_heat", 247)
fuel_cost_result("Water heating", "water_heat", 247)
fuel_cost_result_no_label("community_water_heat_1", "342a")
fuel_cost_result_no_label("community_water_heat_2", "342b")
fuel_cost_result_no_label("community_water_heat_3", "342c")
fuel_cost_result_no_label("community_water_heat_4", "342d")
fuel_cost_result_no_label("community_water_heat_5", "342e")
fuel_cost_result("Space cooling", "cooling", 248)
fuel_cost_result("Pumps and fans for heating", "fans_and_pumps", 249)
fuel_cost_result("Electric keep-hot", "fans_and_pumps_keep_hot", 249)
fuel_cost_result("Pump for solar water heating", "solar_water_pump", 249)
fuel_cost_result("Mech vent fans", "mech_vent", 249)
fuel_cost_result("Pumps and fans for heating", "fans_and_pumps", 349)
fuel_cost_result("Electricity for lighting", "lighting", 250)
fuel_cost_result("Electricity for lighting", "lighting", 350)
fuel_cost_result("Electricity generated - PVs", "pv", 252)
fuel_cost_result("Electricity generated - wind", "wind", 252)
fuel_cost_result("Net electricity generated - mCHP", "chp", 252)

results = results | (Literal("Additional standing charges") +
                     Optional(Literal("(") + SkipTo(")") + Literal(")")) +
                     OneOrMore(tab) +
                     floatnum("cost_standing") + tab +
                     Literal("(251)"))
results = results | (Literal("Additional standing charges") +
                     Optional(Literal("(") + SkipTo(")") + Literal(")")) +
                     OneOrMore(tab) +
                     floatnum("cost_standing") + tab +
                     Literal("(351)"))

emissions_result("Space heating - main system", "heating_main", 261)
emissions_result("Space heating - main system 1", "heating_main_1", 261)
emissions_result("Space heating - main system 2", "heating_main_2", 262)
emissions_result("High-rate cost", "heating_main_high_rate", 261)
emissions_result("Low-rate cost", "heating_main_low_rate", 261)
emissions_result("Space heating - secondary", "heating_secondary", 263)
emissions_result("Space heating, secondary", "heating_secondary", 374)
emissions_result("Water heating  (immersion)", "water_heat_immersion", 264)
emissions_result("Water heating", "water_heat", 264)
emissions_result("Water heating  (micro-CHP) ", "water_heat", 264)
emissions_result("CO2 emissions from boilers", "water_heat", 367)
emissions_result_no_label("community_1", 367)
emissions_result_no_label("community_2", 368)
emissions_result_no_label("community_3", 369)
emissions_result_no_label("community_4", 370)
emissions_result_no_label("community_5", 371)
emissions_result("Space cooling", "cooling", 266)
emissions_result("Pumps and fans", "fans_and_pumps", 267)
emissions_result("Pumps and fans", "fans_and_pumps", 378)
emissions_result("Pumps/fans/keep-hot", "fans_and_pumps", 267)
emissions_result("Electricity for lighting", "lighting", 268)
emissions_result("Electricity for lighting", "lighting", 379)
emissions_result("Electricity generated - PVs", "pv", 269)
emissions_result("Electricity generated - wind", "wind", 269)
emissions_result("Net electricity generated - mCHP", "chp", 269)

emissions_result("Space heating from CHP", "heating_main_chp", 363)
emissions_result("less credit emissions for electricity",
                 "heating_main_chp_elec_credits", 364)
emissions_result("Water heating from CHP", "water_heat_chp", 365)
emissions_result("less credit emissions for electricity",
                 "water_heat_chp_elec_credits", 366)

emissions_result(
    "Electrical energy for heat distribution", "community_distribution", 372)

results = results | (
    results_section_10a_using_pcdf_prices |
    results_section_10b_using_pcdf_prices |
    results_section_13a |
    results_section_13a_improved)


input_section_begin = (
    (Literal("SAP 2009 input data (new dwelling as ") | Literal("SAP 2009 input data  (existing dwelling)"))
    + SkipTo(para_end)
    ).suppress()

#input_section_begin=Literal("Property description").suppress()
input_section = (input_section_begin +
                 OneOrMore(inputs | blank_line.suppress() | awkward_input.suppress()) +
                 # official tests cases have this
                 Optional(result_summary_section) +
                 section_end)


main_results = OneOrMore(results | (der_word + NotAny(section_end))) + der_word

der_section = Optional(main_results) + Optional(section_end)

ter_section = OneOrMore(results | der_word) + SkipTo(section_end) + section_end
fee_section = main_results + section_end
er_section = main_results + section_end
er_section_v2 = OneOrMore(results | der_word)

improved_dwelling_section = main_results + section_end
regulations_report_section = SkipTo(section_end) + section_end
overheating_section = SkipTo(section_end) + section_end


improvement_line = Group(
    para_end +
    SkipTo(tab)("measure") +
    tab +
    SkipTo(tab)("description") +
    tab +
    (Literal("Recommended") |
     Literal("Not considered") |
     Literal("Not applicable") |
     Literal("SAP increase too small") |
     Literal("Already installed"))("status"))

improvement_effect = Group(
    para_end +
    SkipTo(tab, failOn=LineEnd())("measure") +
    tab +
    SkipTo(tab, failOn=LineEnd())("description") +
    tab +
    SkipTo(tab, failOn=LineEnd())("sap_change").setParseAction(lambda toks: ''.join(toks).replace(' ', '')) +
    tab +
    SkipTo(tab, failOn=LineEnd())("cost_change").setParseAction(lambda toks: ''.join(toks).replace(' ', '').replace("\\'a3", '')) +
    tab +
    SkipTo(LineEnd())("co2_change").setParseAction(lambda toks: ''.join(toks).replace(' ', '').split("kg")[0]))

improvement_effects = (Group(OneOrMore(improvement_effect)) |
                      (para_end + Literal("(none)")))

improvements_section = (
    (SkipTo("(For testing purposes):") +
     Literal("(For testing purposes):")).suppress() +
    Group(OneOrMore(improvement_line))("improvements") +
    OneOrMore(para_end) +
    Literal("Recommended measures") + SkipTo(LineEnd()) +
    improvement_effects("effects") +
    Optional(para_end + para_end +
             Literal("Measures omitted - SAP change or cost saving too small:") +
             improvement_effects("effects_omitted")) +
    para_end + Literal("__") +
    SkipTo("}").suppress())

dummy_word = Word(alphas + nums + "\\/,.+-_'():;=%{}*&").suppress()
input_section_header = OneOrMore(
    dummy_word + NotAny(input_section_begin)) + dummy_word


def section(label, parser):
    section_begin = Literal(label).suppress()
    section_header = OneOrMore(dummy_word + NotAny(section_begin)) + dummy_word
    return section_header + section_begin + parser

full_file = (input_section_header + Group(input_section)("inputs") +
             section("CALCULATION OF FABRIC ENERGY EFFICIENCY",
                     Group(fee_section)("fee")) +
             section("CALCULATION OF ENERGY RATINGS",
                     Group(er_section)("er")) +
             section("CALCULATION OF DWELLING EMISSIONS FOR REGULATIONS COMPLIANCE",
                     Group(der_section)("der")) +
             section("CALCULATION OF TARGET EMISSIONS",
                     Group(ter_section)("ter")) +
             section("CALCULATION OF ENERGY RATINGS FOR IMPROVED DWELLING",
                     Group(improved_dwelling_section)("improved")) +
             section("REGULATIONS COMPLIANCE REPORT ",
                     Group(regulations_report_section)("regulations_report")) +
             Optional(section("SAP 2009 OVERHEATING ASSESSMENT FOR NEW DWELLING AS BUILT",
                              Group(overheating_section)("overheating"))) +
             Optional(section("SAP 2009 OVERHEATING ASSESSMENT FOR NEW DWELLING AS DESIGNED",
                              Group(overheating_section)("overheating"))) +
                      section("SAP 2009 IMPROVEMENTS",
                              Group(improvements_section)("improvements"))
            )

reduced_file = (input_section_header + Group(input_section)("inputs") +
              section("CALCULATION OF ENERGY RATINGS",
                      Group(er_section_v2)("er")))

reduced_file2 = (input_section_header + Group(input_section)("inputs") +
    section("CALCULATION OF ENERGY RATINGS",
            Group(er_section)("er")) +
    section("CALCULATION OF ENERGY RATINGS FOR IMPROVED DWELLING",
            Group(improved_dwelling_section)("improved")) +
    section("SAP 2009 IMPROVEMENTS",
            Group(improvements_section)("improvements")))

whole_file = full_file | reduced_file2
whole_file.ignore(irrelevant_rtf_codes)
