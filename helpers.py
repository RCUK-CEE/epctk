from sap import sap_tables
from sap.dwelling import Dwelling

# TODO: figure out how to avoid using this global calc stage var
CALC_STAGE = 0
ALL_PARAMS = [set(), set(), set(), set(), set(), set(), set()]


def log_dwelling_params(dwelling, prefix=""):
    """
    Log all the dwelling parameters
    :param dwelling:
    :param prefix:
    :return:
    """
    # FIXME dodgy use of global Calc_stage
    param_set = ALL_PARAMS[CALC_STAGE]

    for k, v in dwelling.items():
        # if k != "_attrs":
        pass
        # log_sap_obj(param_set, prefix, k, v)


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
        for key, value in v.__dict__.items():
            log_sap_obj(param_set, prefix + k + ".", key, value)
        return
    except AttributeError:
        pass


# FIXME: find out if this is actually used anywhere...
# class TrackedDict(dict):
#     def __init__(self, data, prefix):
#         super(TrackedDict, self).__init__(data)
#         self.prefix = prefix + "."
#
#         for key in list(data.keys()):
#             ALL_PARAMS[CALC_STAGE].add(self.prefix + key)
#
#     def __setitem__(self, key, value):
#         dict.__setitem__(self, key, value)
#         ALL_PARAMS[CALC_STAGE].add(self.prefix + key)
#

class ParamTrackerDwelling(Dwelling):
    def __init__(self):
        super(ParamTrackerDwelling, self).__init__()
        self.calc_stage = 1

    # def __setattr__(self, k, v):
    #     """if k!="ordered_attrs":
    #         if isinstance(v,dict):
    #             v=TrackedDict(v,k)
    #
    #         all_params[calc_stage].add(k)
    #         try:
    #             for key in v.keys():
    #                 all_params[calc_stage].add(k+"."+key)
    #         except AttributeError:
    #             pass"""
    #
    #     Dwelling.__setattr__(self, k, v)

    # TODO: overload dwelling's setitem/getitem (at least for results) so that you can track changes for each stage...

    def next_stage(self):
        self.calc_stage += 1

