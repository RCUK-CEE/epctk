from jsonschema import validate

from ..elements import OpeningType
from .dwelling_schema import sap_schema



def dwelling_object_from_json_like_dict(dwelling):
    # most of this will already be fine. Main thing is to convert e.g. openings to objects...
    opening_types = dwelling['opening_types']

    opening_types_objects = []
    for opening_def in opening_types:
        OpeningType(**opening_def)