import copy

import numpy
import yaml

from .. import fuels
from ..elements import HeatLossElement, ThermalMassElement, Opening, OpeningType
from ..dwelling import Dwelling


def elec_tariff_representer(dumper, data):
    return dumper.represent_mapping('!fuel', dict(fuel_code=data.on_peak_fuel_code))


def fuel_constructor(loader, node):
    data = loader.construct_mapping(node)
    return fuels.fuel_from_code(data['fuel_code'])


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

    yaml.add_representer(fuels.ElectricityTariff, elec_tariff_representer)
    yaml.add_representer(fuels.Fuel, fuel_representer)
    yaml.add_constructor('!fuel', fuel_constructor)

    create_mapper(HeatLossElement, "HeatLossElement")
    create_mapper(ThermalMassElement, "ThermalMassElement")
    create_mapper(Opening, "Opening")

    yaml.add_representer(OpeningType, opening_type_representer)
    yaml.add_constructor(
        "!OpeningType", SimpleTagUnMapper(OpeningType))

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
    for key, value in loaded.items():
        dwelling[key] = value

    return dwelling


# Work in progres....
def rejig_heating_for_sanity(dwelling):
    """
    Idea to put main_1 and main_2 into main_heating = [main_1, main_2]
    Args:
        dwelling:

    Returns:

    """

    main_heating = []

    system_data = {}

    system_data['type_code'] = dwelling.pop('main_heating_type_code')
    system_data['hetas_approved'] = dwelling.pop('sys1_hetas_approved')
    # system_data["effy_hetas"] is loaded from system data
    system_data['fuel'] = dwelling.pop('main_sys_fuel')
    system_data['manuf_effy'] = dwelling.pop('main_sys_manuf_effy')
    system_data['heating_control_type'] = dwelling.pop('heating_control_type_sys1')

    system_data['heating_fraction'] = dwelling.pop('main_heating_fraction', 0)

    # maybe...
    system_data['pcdf_id'] = dwelling.pop('main_heating_pcdf_id')
    system_data['sedbuk_2005_effy'] = dwelling.pop('sys1_sedbuk_2005_effy')
    system_data['sedbuk_2009_effy'] = dwelling.pop('sys1_sedbuk_2009_effy')
    system_data['sedbuk_range_case_loss_at_full_output'] = dwelling.pop('sys1_sedbuk_range_case_loss_at_full_output')
    system_data['sedbuk_range_full_output'] = dwelling.pop('sys1_sedbuk_range_full_output')
    system_data['sedbuk_type'] = dwelling.pop('sys1_sedbuk_type')
    system_data['sedbuk_fan_assisted'] = dwelling.pop('sys1_sedbuk_fan_assisted')


    main_heating.append(system_data)



    system_data = {}

    system_data['type_code'] = dwelling.pop('sys2_heating_type_code')
    system_data['hetas_approved'] = dwelling.pop('main_hetas_approved')
    # system_data["effy_hetas"] is loaded from system data
    system_data['fuel'] = dwelling.pop('main_sys_2_fuel')
    system_data['manuf_effy'] = dwelling.pop('main_sys_manuf_effy') #doesn't exist though...
    system_data['heating_control_type'] = dwelling.pop('heating_control_type_sys2')

    system_data['heating_fraction'] = dwelling.pop('main_heating_2_fraction', 0)

    # maybe...
    system_data['pcdf_id'] = dwelling.pop('main_heating_2_pcdf_id')
    system_data['sedbuk_2005_effy'] = dwelling.pop('sys2_sedbuk_2005_effy')
    system_data['sedbuk_2009_effy'] = dwelling.pop('sys2_sedbuk_2009_effy')
    system_data['sedbuk_range_case_loss_at_full_output'] = dwelling.pop('sys2_sedbuk_range_case_loss_at_full_output')
    system_data['sedbuk_range_full_output'] = dwelling.pop('sys2_sedbuk_range_full_output')
    system_data['sedbuk_type'] = dwelling.pop('sys2_sedbuk_type')
    system_data['sedbuk_fan_assisted'] = dwelling.pop('sys2_sedbuk_fan_assisted')

    main_heating.append(system_data)
    # dwelling['main_heating'] = mean_heating

    return main_heating






