
from sap import tables, worksheet
from sap.dwelling import Dwelling

from tests.test_official_cases import all_params

# TODO: figure out how to avoid using this global calc stage var
calc_stage = 1

def log_obj(param_set, prefix, k, v):
    """
    Customized logging of SAP objects
    """
    param_set.add(prefix + k)

    if isinstance(v, str):
        return

    if k in ["opening_types"]:
        # This is a dict, but the keys aren't interesting (e.g. things
        # like Windows (1), Windows (2), etc)
        for entry in list(v.values()):
            log_obj(param_set, prefix, "_" + k, entry)
        return

    try:
        # If this is a dict,dump the entries
        for key, value in list(v.items()):
            log_obj(param_set, prefix + k + ".", key, value)
        return
    except AttributeError:
        pass

    try:
        # If this is a list,dump the entries
        for entry in v:
            log_obj(param_set, prefix, k, entry)
        return
    except TypeError:
        pass

    try:
        if (isinstance(v, tables.Fuel) or
                isinstance(v, tables.ElectricityTariff)):
            return
        # If this is an object, dump it's dict
        for key, value in list(v.__dict__.items()):
            log_obj(param_set, prefix + k + ".", key, value)
        return
    except AttributeError:
        pass


class TrackedDict(dict):

    def __init__(self, d, prefix):
        dict.__init__(self, d)
        self.prefix = prefix + "."

        for key in list(d.keys()):
            all_params[calc_stage].add(self.prefix + key)

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        all_params[calc_stage].add(self.prefix + key)


class ParamTrackerDwelling(Dwelling):

    def __init__(self):
        global calc_stage
        Dwelling.__init__(self)
        calc_stage = 1

    def __setattr__(self, k, v):
        """if k!="ordered_attrs":
            if isinstance(v,dict):
                v=TrackedDict(v,k)

            all_params[calc_stage].add(k)
            try:
                for key in v.keys():
                    all_params[calc_stage].add(k+"."+key)
            except AttributeError:
                pass"""

        Dwelling.__setattr__(self, k, v)

    def nextStage(self):
        global calc_stage
        calc_stage += 1