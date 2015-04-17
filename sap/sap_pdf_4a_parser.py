from pyparsing import *

"""
BNF:

integer ::= 0-9*
float ::=

type ::= alphas+whitespace (skip to first number)
rd ::= 'rd'
line ::= type integer integer integer float integer Optional('rd')

"""

integer = Word(nums)
floatnum = Combine(Word(nums) + Optional(Literal(".") + Optional(Word(nums))))
year = Word(nums, exact=4)

description = OneOrMore(Word(alphas + "()/-+,") | year).setResultsName(
    "type").setParseAction(lambda tokens: " ".join(tokens))
system_code = integer.setResultsName("code")
responsiveness = floatnum.setResultsName("responsiveness")
effy = integer.setResultsName("effy")
effy_hetas = integer.setResultsName("effy_hetas")
flue_type = Word(alphas)("flue_type")

heat_pump_str = Group(OneOrMore(Word(alphas + "4()/-,")))


solid_fuel_boiler_line = Group(description +
                               effy_hetas + effy + integer + responsiveness +
                               system_code +
                               Optional(Literal('rd')))
regular_line = Group(description +
                     effy + integer + responsiveness +
                     system_code +
                     Optional(Literal('rd')))
heat_pump_line = Group(description +
                       effy + heat_pump_str +
                       system_code +
                       Optional(Literal('rd')))

room_heater_with_flue_line = Group(description +
                                   flue_type +
                                   effy + integer + integer + responsiveness +
                                   system_code +
                                   Optional(Literal('rd')))

dedicated_hw_system_line = Group(description +
                                 effy +
                                 system_code +
                                 Optional(Literal('rd')))

data = OneOrMore(solid_fuel_boiler_line |
                 regular_line |
                 heat_pump_line |
                 room_heater_with_flue_line |
                 dedicated_hw_system_line)

datafile = open('table4adata.txt')
txt = datafile.read()

res = []
for srvrtokens, startloc, endloc in data.scanString(txt):
    res.append(srvrtokens)

if len(res) > 1:
    print("Error parsing data!")
    print((res[1]))
    exit(-1)

for system in res[0]:
    if system.responsiveness != '':
        print(("%s,\"%s\",%s,%s" % (system.code, system.type, system.effy, system.responsiveness)))
    else:
        print(("%s,\"%s\",%s,emitter" % (system.code, system.type, system.effy)))
