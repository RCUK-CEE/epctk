import unittest

from epctk.elements import DwellingType


class TestElements(unittest.TestCase):
    def test_dwelling_type(self):
        self.assertEqual(DwellingType('house'), DwellingType.HOUSE)
