import unittest

from epctk.elements import Country
from  epctk.io import rdsap_converter
from epctk.tables import tables_appendix_s
from epctk.tables.tables_appendix_s import AgeBand, WallMaterial, WallInsulation, table_s9_u_roof
from epctk.utils import SAPInputError


class TestRdSAPInput(unittest.TestCase):

    # def test_country_from_region(self):
        # country = rd_sap_converter.country_from_region(1)

    def test_lookup_u_values(self):
        u = tables_appendix_s.lookup_wall_u_values(Country.England, AgeBand.A, WallMaterial.STONE_HARD, WallInsulation.NONE)
        self.assertEqual(u, 2.4)

        u = tables_appendix_s.lookup_wall_u_values(Country.Scotland, AgeBand.J, WallMaterial.TIMBER, WallInsulation.INTERNAL)
        self.assertEqual(u, 0.3)

        with self.assertRaises(SAPInputError):
             t = tables_appendix_s.table_s3_wall_thickness(AgeBand.A, WallMaterial.TIMBER, WallInsulation.EXTERNAL)

    def test_lookup_wall_thickness(self):
        t = tables_appendix_s.table_s3_wall_thickness(AgeBand.A, WallMaterial.STONE_HARD, WallInsulation.NONE)
        self.assertEqual(t, 0.5)

        with self.assertRaises(SAPInputError):
             t = tables_appendix_s.table_s3_wall_thickness(AgeBand.A, WallMaterial.TIMBER, WallInsulation.EXTERNAL)


    def test_table_s9(self):
        t = table_s9_u_roof(10)
        self.assertEqual(t, 2.3)


        t = table_s9_u_roof(100)
        self.assertEqual(t, 0.4)

        t = table_s9_u_roof(300)
        self.assertEqual(t, 0.13)

        t = table_s9_u_roof(500)
        self.assertEqual(t, 0.13)
