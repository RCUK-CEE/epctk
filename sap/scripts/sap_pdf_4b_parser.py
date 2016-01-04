from pyparsing import *

integer=Word(nums)
floatnum=Combine(Optional(Word("+-"))+Word(nums)+Optional(Literal(".")+Optional(Word(nums))))
year=Word(nums,exact=4)

description=OneOrMore(Word(alphas+"()/-+,")|year).setResultsName("description").setParseAction(lambda tokens: " ".join(tokens))
code=integer.setResultsName("code")
effy_winter=integer.setResultsName("effy_winter")
effy_summer=integer.setResultsName("effy_summer")

regular_line=Group(description+
                   effy_winter+effy_summer+
                   code+
                   Optional(Literal('rd')))

data=OneOrMore(regular_line)

datafile=open('table4bdata.txt')
txt=datafile.read()

res=[]
for srvrtokens,startloc,endloc in data.scanString(txt):
    res.append(srvrtokens)

if len(res)>1:
    print("Error parsing data!")
    exit(-1)

for system in res[0]:
    print(("%s,%s,%s,\"%s\"" % (system.code,system.effy_winter,system.effy_summer,system.description)))

