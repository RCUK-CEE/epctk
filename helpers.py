
from sap import sap_tables
from sap.dwelling import Dwelling

# TODO: figure out how to avoid using this global calc stage var
CALC_STAGE = 1
ALL_PARAMS = [set(), set(), set(), set(), set(), set(), set()]

def log_sap_obj(param_set, prefix, k, v):
    """
    Customized logging of SAP objects
    """
    param_set.add(prefix + k)

    if isinstance(v, str):
        return

    if k in ["opening_types"]:
        # This is a dict, but the keys aren't interesting (e.g. things
        # like Windows (1), Windows (2), etc)
        for entry in v.values():
            log_sap_obj(param_set, prefix, "_" + k, entry)
        return

    try:
        # If this is a dict,dump the entries
        for key, value in v.items():
            log_sap_obj(param_set, prefix + k + ".", key, value)
        return
    except AttributeError:
        pass

    try:
        # If this is a list,dump the entries
        for entry in v:
            log_sap_obj(param_set, prefix, k, entry)
        return
    except TypeError:
        pass

    try:
        if (isinstance(v, sap_tables.Fuel) or
                isinstance(v, sap_tables.ElectricityTariff)):
            return
        # If this is an object, dump it's dict
        for key, value in list(v.__dict__.items()):
            log_sap_obj(param_set, prefix + k + ".", key, value)
        return
    except AttributeError:
        pass


class TrackedDict(dict):

    def __init__(self, d, prefix):
        dict.__init__(self, d)
        self.prefix = prefix + "."

        for key in list(d.keys()):
            ALL_PARAMS[CALC_STAGE].add(self.prefix + key)

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        ALL_PARAMS[CALC_STAGE].add(self.prefix + key)


class ParamTrackerDwelling(Dwelling):

    def __init__(self):
        global CALC_STAGE
        Dwelling.__init__(self)
        CALC_STAGE = 1

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
        global CALC_STAGE
        CALC_STAGE += 1


