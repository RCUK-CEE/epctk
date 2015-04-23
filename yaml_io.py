import yaml
import copy
import numpy

from collections import OrderedDict
from sap import worksheet
from sap import tables
from sap.dwelling import Dwelling


def elec_tariff_representer(dumper, data):
    return dumper.represent_mapping('!fuel', dict(fuel_code=data.on_peak_fuel_code))


def fuel_constructor(loader, node):
    data = loader.construct_mapping(node)
    return tables.fuel_from_code(data['fuel_code'])


def fuel_representer(dumper, data):
    return dumper.represent_mapping('!fuel', dict(fuel_code=data.fuel_id))


def opening_type_representer(dumper, data):
    real_data = dict(data.__dict__)
    del real_data["light_transmittance"]
    return dumper.represent_mapping('!OpeningType', real_data)


def opening_representer(dumper, data):
    real_data = dict(data.__dict__)
    real_data["opening_type"] = data.opening_type.name
    return dumper.represent_mapping('!Opening', real_data)


def array_as_list_representer(dumper, data):
    l = list(map(float, data))
    return dumper.represent_sequence("!Array", l)


def array_as_list_constructor(loader, node):
    data = loader.construct_sequence(node)
    return numpy.array(data)


class SimpleTagMapper(object):

    def __init__(self, tag):
        self.tag = tag

    def __call__(self, dumper, data):
        return dumper.represent_mapping('!%s' % (self.tag,), data.__dict__)


class SimpleTagUnMapper(object):

    def __init__(self, otype):
        self.otype = otype

    def __call__(self, loader, node):
        data = loader.construct_mapping(node)
        return self.otype(**data)


def ordered_dict_presenter(dumper, data):
    return dumper.represent_dict(data.ordered_items())


def create_mapper(otype, tag):
    yaml.add_representer(otype, SimpleTagMapper(tag))
    yaml.add_constructor("!%s" % (tag,), SimpleTagUnMapper(otype))


def configure_yaml():
    # Don't think you need special treatment for ordereddict
    # yaml.add_representer(OrderedDict, ordered_dict_presenter)

    yaml.add_representer(tables.ElectricityTariff, elec_tariff_representer)
    yaml.add_representer(tables.Fuel, fuel_representer)
    yaml.add_constructor('!fuel', fuel_constructor)

    create_mapper(worksheet.HeatLossElement, "HeatLossElement")
    create_mapper(worksheet.ThermalMassElement, "ThermalMassElement")
    create_mapper(worksheet.Opening, "Opening")

    yaml.add_representer(worksheet.OpeningType, opening_type_representer)
    yaml.add_constructor(
        "!OpeningType", SimpleTagUnMapper(worksheet.OpeningType))

    yaml.add_representer(numpy.ndarray, array_as_list_representer)
    yaml.add_constructor("!Array", array_as_list_constructor)


def to_yaml(d, stream):
    configure_yaml()
    data = copy.deepcopy(d._attrs)

    del data["Tcooling"]
    del data["living_area_Theating"]
    del data["parser_use_input_file_store_params"]

    stream.write(yaml.dump(data, width=200))


def from_yaml(fname):
    configure_yaml()
    with open(fname, 'r') as f:
        loaded = yaml.load(f)

    dwelling = Dwelling()
    for k, v in list(loaded.items()):
        setattr(dwelling, k, v)

    return dwelling
