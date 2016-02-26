import unittest

from epctk.elements import geographic
from epctk.elements.geographic import Country, Region
from epctk.utils import SAPInputError


class TestGeo(unittest.TestCase):

    def test_country_from_iso(self):

        iso_code = "GB-EAW"
        country = Country.from_iso(iso_code)

        self.assertEqual(country, Country.England)

        iso_code = "GB-ENG"

        country = Country.from_iso(iso_code)

        self.assertEqual(country, Country.England)

        iso_code = "GB-WLS"
        country = Country.from_iso(iso_code)

        self.assertEqual(country, Country.Wales)

        with self.assertRaises(SAPInputError):
            Country.from_iso("Blub")


    def test_country_from_region(self):
        country = geographic.country_from_region(1)
        self.assertEqual(country, Country.England)

        country = geographic.country_from_region(14)
        self.assertEqual(country, Country.Scotland)

        country = geographic.country_from_region(13)
        self.assertEqual(country, Country.Wales)

        # Region out of range
        with self.assertRaises(SAPInputError):
            geographic.country_from_region(42)