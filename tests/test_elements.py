import unittest

from epctk.elements import DwellingType


class TestElements(unittest.TestCase):
    def test_dwelling_type(self):
        self.assertEqual(DwellingType(1), DwellingType.HOUSE)

        self.assertEqual(DwellingType.from_string("house"), DwellingType.HOUSE)