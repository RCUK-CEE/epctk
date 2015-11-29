from pyparsing import *

"""
BNF:

integer ::= 0-9*
float ::=

type ::= alphas+whitespace (skip to first number)
rd ::= 'rd'
xref ::= alphas
code ::= integer

line ::= type integer float xref code Optional('rd')

"""

integer = Word(nums)
floatnum = Combine(Optional(Word("+-")) + Word(nums) + Optional(Literal(".") + Optional(Word(nums))))

description = OneOrMore(Word(alphas + "()/-+,")).setResultsName("description").setParseAction(
    lambda tokens: " ".join(tokens))
code = integer.setResultsName("code")

Tadjustment = floatnum.setResultsName("Tadjustment")
control = integer.setResultsName("control")

xref = (Combine(Literal("Table ") + Word(alphas + nums + "()")) | Literal("n/a"))("xref")

regular_line = Group(description +
                     control + Tadjustment +
                     xref + code +
                     Optional(Literal('rd')))

data = OneOrMore(regular_line)

datafile = open('table4edata.txt')
txt = datafile.read()

res = []
for srvrtokens, startloc, endloc in data.scanString(txt):
    res.append(srvrtokens)

if len(res) > 1:
    print("Error parsing data!")
    exit(-1)

for system in res[0]:
    print(
        ("%s,%s,%s,\"%s\",\"%s\"" % (system.code, system.control, system.Tadjustment, system.xref, system.description)))

