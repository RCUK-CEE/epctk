from unittest import TestCase, main

from tests.test_case_parser import *


class TestFieldValue(TestCase):

    def parse_single_field(self, txt):
        results = field_value.parseString(txt)
        self.assertEqual(1, len(results))
        return results[0]

    def test_simple_field(self):
        inp = self.parse_single_field("lab1:val1")
        self.assertEqual("lab1", inp.label)
        self.assertEqual(1, len(inp.vals))
        self.assertEqual("val1", inp.vals[0].value)

    def test_simple_field_specialchars(self):
        inp = self.parse_single_field("lab1:val1-<>=.,+-/%# ")
        self.assertEqual("lab1", inp.label)
        self.assertEqual(1, len(inp.vals))
        self.assertEqual("val1-<>=.,+-/%# ", inp.vals[0].value)

    def test_water_use_field(self):
        inp = self.parse_single_field(
            "Water use <= 125 litres/person/day val1")
        self.assertEqual(1, len(inp.vals))
        self.assertEqual("val1", inp.vals[0].value)

    def test_simple_field_with_note(self):
        inp = self.parse_single_field("lab1:val1 (extra)")
        self.assertEqual("lab1", inp.label)
        self.assertEqual(1, len(inp.vals))
        # note: whitespace ends up in val1
        self.assertEqual("val1 ", inp.vals[0].value)
        self.assertEqual("extra", inp.vals[0].note)

    def test_simple_field_with_bracket_in_value(self):
        inp = self.parse_single_field("lab1:val1 (extra")
        self.assertEqual("lab1", inp.label)
        self.assertEqual(1, len(inp.vals))
        self.assertEqual("val1 (extra", inp.vals[0].value)

    def test_field_with_brackets_in_value(self):
        inp = self.parse_single_field("lab1:val1 (blah) val2")
        self.assertEqual("lab1", inp.label)
        self.assertEqual(1, len(inp.vals))
        self.assertEqual("val1 (blah) val2", inp.vals[0].value)

    def test_simple_compound_field(self):
        inp = self.parse_single_field("lab1: sublab:val1")
        self.assertEqual("lab1", inp.label)
        self.assertEqual(1, len(inp.vals))
        self.assertEqual("sublab", inp.vals[0].label)
        self.assertEqual(1, len(inp.vals[0].vals))
        self.assertEqual("val1", inp.vals[0].vals[0].value)

    def test_compound_field_with_brackets_in_label(self):
        inp = self.parse_single_field("lab1 (312): sublab:val1")
        self.assertEqual("lab1 ", inp.label)
        self.assertEqual("312", inp.note)
        self.assertEqual(1, len(inp.vals))
        self.assertEqual("sublab", inp.vals[0].label)
        self.assertEqual(1, len(inp.vals[0].vals))
        self.assertEqual("val1", inp.vals[0].vals[0].value)

    def test_compound_field_with_note_with_colons(self):
        inp = self.parse_single_field("lab1: val1 (a: 1, b: 2, c: 3)")
        self.assertEqual("lab1", inp.label)
        self.assertEqual(1, len(inp.vals))
        self.assertEqual("val1 ", inp.vals[0].value)
        self.assertEqual("a: 1, b: 2, c: 3", inp.vals[0].note)


class test_primary_input(TestCase):

    def test_simple_primary_input(self):
        results = primary_input.parseString("\\par primlab1:\\tab val1")
        self.assertEqual(1, len(results))
        input = results[0]
        self.assertEqual(1, len(input.vals))
        self.assertEqual("primlab1", input.label)
        self.assertEqual("val1", input.vals[0].value)

    def test_compount_primary_input(self):
        results = primary_input.parseString(
            "\\par primlab1:\\tab lab1:val1 (note)")
        self.assertEqual(1, len(results))

        pinput = results[0]
        self.assertEqual("primlab1", pinput.label)
        self.assertEqual(1, len(pinput.vals))
        inp = pinput.vals[0]
        self.assertEqual("lab1", inp.label)
        self.assertEqual(1, len(inp.vals))
        self.assertEqual("val1 ", inp.vals[0].value)
        self.assertEqual("note", inp.vals[0].note)

    def test_multi_child_primary_input(self):
        results = primary_input.parseString(
            "\\par primlab1:\\tab val1 \n val2")
        self.assertEqual(1, len(results))
        pinput = results[0]
        self.assertEqual(2, len(pinput.vals))
        self.assertEqual("primlab1", pinput.label)
        self.assertEqual("val1 ", pinput.vals[0].value)
        self.assertEqual("val2", pinput.vals[1].value)

    def test_multi_child_primary_input_with_tabs_before_2nd_input(self):
        results = primary_input.parseString(
            "\\par primlab1:\\tab val1 \n\\par \\tab \\tab val2")
        self.assertEqual(1, len(results))
        pinput = results[0]
        self.assertEqual("primlab1", pinput.label)
        self.assertEqual(2, len(pinput.vals))
        self.assertEqual("val1 ", pinput.vals[0].value)
        self.assertEqual("val2", pinput.vals[1].value)

    def test_two_line_subkey(self):
        results = primary_input.parseString(
            "\\par primlab1:\\tab val1 \n\\par \\tab\\tab lab2:\n\\par \\tab\\tab val2")
        self.assertEqual(1, len(results))
        pinput = results[0]
        self.assertEqual("primlab1", pinput.label)
        self.assertEqual(2, len(pinput.vals))
        self.assertEqual("val1 ", pinput.vals[0].value)

        self.assertEqual("lab2", pinput.vals[1].label)
        self.assertEqual(1, len(pinput.vals[1].vals))
        self.assertEqual("val2", pinput.vals[1].vals[0].value)


class test_table(TestCase):

    def test_entry_special_chars(self):
        results = table_entry.parseString("hello12().,/- ")
        self.assertEqual(1, len(results))
        self.assertEqual("hello12().,/- ", results[0])

    def test_label_special_chars(self):
        results = table_label.parseString("hello12().,/- ")
        self.assertEqual(1, len(results))
        self.assertEqual("hello12().,/- ", results[0])

    def test_simple_table(self):
        results = table.parseString(
            "\\par\\tabcol1\\tabcol2\n\\parrow1\\tabval1\\tabval2\n")
        self.assertEqual(1, len(results))
        ptable = results[0]
        cols = ptable.column_headings
        self.assertEqual(3, len(cols))
        self.assertEqual('', cols[0])
        self.assertEqual('col1', cols[1])
        self.assertEqual('col2', cols[2])

        rows = ptable.rows
        self.assertEqual(1, len(rows))

        row1 = rows[0]
        self.assertEqual(3, len(row1))
        self.assertEqual('row1', row1[0])
        self.assertEqual('val1', row1[1])
        self.assertEqual('val2', row1[2])

    def test_two_row_table(self):
        results = table.parseString(
            "\\par\\tabcol1\\tabcol2\n\\parrow1\\tabval1\\tabval2\n\\parrow2\\tabval12\\tabval22\n")
        self.assertEqual(1, len(results))
        ptable = results[0]
        rows = ptable.rows
        self.assertEqual(2, len(rows))

        row = rows[1]
        self.assertEqual(3, len(row))
        self.assertEqual('row2', row[0])
        self.assertEqual('val12', row[1])
        self.assertEqual('val22', row[2])


class TestInputSection(TestCase):

    """
    def test_simple_input_section(self):
        results=input_section.parseString("Property description\n\\par primlab1:\\tab val1\n\\sect")
        self.assertEqual(1,len(results))
        pinput=results[0]
        self.assertEqual(1,len(pinput.vals))
        self.assertEqual("primlab1",pinput.label)
        self.assertEqual("val1",pinput.vals[0].value)
       
    def test_two_input_section(self):
        results=input_section.parseString("Property description\n\\par primlab1:\\tab val1\n\\par primlab2:\\tab val2\n\\sect")
        self.assertEqual(2,len(results))
        pinput0=results[0]
        self.assertEqual(1,len(pinput0.vals))
        self.assertEqual("primlab1",pinput0.label)
        self.assertEqual("val1",pinput0.vals[0].value)

        pinput1=results[1]
        self.assertEqual(1,len(pinput1.vals))
        self.assertEqual("primlab2",pinput1.label)
        self.assertEqual("val2",pinput1.vals[0].value)

       
    def test_blank_lines(self):
        results=input_section.parseString("Property description\n\\par primlab1:\\tab val1\n\\par\n\\par primlab2:\\tab val2\n\\sect")
        self.assertEqual(2,len(results))
        pinput0=results[0]
        self.assertEqual(1,len(pinput0.vals))
        self.assertEqual("primlab1",pinput0.label)
        self.assertEqual("val1",pinput0.vals[0].value)

        pinput1=results[1]
        self.assertEqual(1,len(pinput1.vals))
        self.assertEqual("primlab2",pinput1.label)
        self.assertEqual("val2",pinput1.vals[0].value)
        """


class TestProblemCases(TestCase):

    def test_252(self):
        string = "Electricity generated - PVs  (0.50\\'d712.02 + 0.50\\'d711.46)\\tab     -288\\tab   11.74\\tab\\ul    -33.86\\ulnone\\tab (252)"
        parser = gen_fuel_result_parser(
            "Electricity generated - PVs", "pv", 252)
        parser.ignore(irrelevant_rtf_codes)
        res = parser.parseString(string)
        self.assertEqual("-288", res.energy_pv)

    def test_342a(self):
        string = "Water heating from community boilers \\tab    2541\\tab     3.78\\tab     96.04\\tab (342a)"
        parser = gen_fuel_result_parser(
            "Water heating from community boilers", "water_heat", "342a")
        parser.ignore(irrelevant_rtf_codes)
        res = parser.parseString(string)
        self.assertEqual("2541", res.energy_water_heat)

    def test_missing_heat_coeff_from_4c(self):
        string = "Heat transfer coeff\\tab     94.6790\\tab     93.5985\\tab     93.5985\\tab     91.4376\\tab     89.9969\\tab     89.2766\\tab     88.5563\\tab     88.5563\\tab     90.3571\\tab     91.4376\\tab     92.5180\\tab     93.5985\\tab   (39)"
        parser = gen_monthly_result_parser(
            "Heat transfer coeff", "heat_loss", 39)
        parser.ignore(irrelevant_rtf_codes)
        res = parser.parseString(string)
        self.assertEqual("94.6790", res.heat_loss[0])

    def test_thermal_bridge_table_header(self):
        string = "\\par \\f0\\tab\\ul Length\\ulnone\\tab\\ul\\f1 Y\\f2 -value\\ulnone"
        parser = table_header_row
        parser.ignore(irrelevant_rtf_codes)
        res = parser.parseString(string)

    def test_thermal_bridge_table_row(self):
        string = "\\par \\tab   25.00\\tab   0.210 [N]    E2    Lintels, not steel with perf. base plate"
        parser = table_row
        parser.ignore(irrelevant_rtf_codes)
        res = parser.parseString(string)

        """
    def test_tricky(self):
        fname="tests.rtf"
        f=open(fname,'r')
        txt=f.read()
        txt=txt.replace('\\\'b','')
        txt=txt.replace('\\f1','')
        string=txt.replace('\\f2','')
    
        parser=(input_section_header+Group(input_section)("inputs"))
        parser.ignore(irrelevant_rtf_codes)
        res=parser.parseString(string)"""

    def test_tricky2(self):
        fname = "test2.rtf"
        f = open(fname, 'r')
        txt = f.read()
        txt = txt.replace('\\\'b', '')
        txt = txt.replace('\\f1', '')
        string = txt.replace('\\f2', '')

        parser = improvements_section
        """parser=(section("CALCULATION OF ENERGY RATINGS FOR IMPROVED DWELLING",
                        Group(improved_dwelling_section)("improved"))+
                section("REGULATIONS COMPLIANCE REPORT ",
                        Group(regulations_report_section)("regulations_report"))+
                Optional(section("SAP 2009 OVERHEATING ASSESSMENT FOR NEW DWELLING AS BUILT",
                        Group(overheating_section)("overheating")))+
                section("SAP 2009 IMPROVEMENTS",
                        Group(improvements_section)("improvements")))"""

        parser.ignore(irrelevant_rtf_codes)
        res = parser.parseString(string)

        print(res.improvements.effects)

        # print res
        for imp in res.improvements.effects:
            print((imp.measures, float(imp.sap_change), float(imp.cost_change), float(imp.co2_change)))
        # for imp in res.improvements:
        #    print imp.measure,imp.description

        # print res

if __name__ == '__main__':
    main()
