import collections
import sys
import logging

import sap.sap_tables


def constant(k):
    return lambda x: k

def temp_val(k):
    return constant(k)

def dwelling_val(key):
    return lambda x: getattr(x,key)

def dwelling_val_or_zero(key):
    return lambda x: getattr(x,key) if hasattr(x,key) else 0

def unused():
    return lambda x: -999

def as_int(l):
    return lambda x: int(l(x))

def as_percent(l):
    return lambda x: 100*l(x)

class element_property:
    def __init__(self,element,prop):
        self.element=element
        self.prop=prop

    def __call__(self,d):
        els=[x for x in d.heat_loss_elements if x.name==self.element]

        if len(els)==1:
            return getattr(els[0],self.prop)
        elif len(els)==0:
            return 0
        else:
            raise RuntimeError("Too many elements found: %s" % (self.element,))

class element_property_win_U:
    def __init__(self,element,prop):
        self.element=element
        self.prop=prop

    def __call__(self,d):
        els=[x for x in d.heat_loss_elements if x.name==self.element]

        if len(els)==1:
            return 1/(1/getattr(els[0],self.prop)-0.04)
        elif len(els)==0:
            return 0
        else:
            raise RuntimeError("Too many elements found: %s" % (self.element,))


class opening_property:
    def __init__(self,opening,prop):
        self.opening=opening
        self.prop=prop

    def __call__(self,d):
        els=[x for x in d.openings if x.name==self.opening]

        if len(els)==1:
            return getattr(els[0].type,self.prop)
        elif len(els)==0:
            return 0
        else:
            logging.error("Too many openings found: %s" % (self.opening,))
            return getattr(els[0].type,self.prop)
            

def water_heater_type(dwelling):
    # Valid values:
    # boiler/heat pump
    # electric immersion
    # electric pou instantaneous

    if hasattr(dwelling,'instantaneous_pou_water_heating') and dwelling.instantaneous_pou_water_heating:
        return "electric pou instantaneous"
    elif sap.sap_tables.getTable3Row(dwelling)==1:
        return "electric immersion"
    else:
        return "boiler/heat pump"

def space_heating_type(dwelling):
    # Valid values:
    # boiler
    # room heater
    # storage heater
    # non-storage room heater
    # heat pump

    # !!! Incomplete

    sys=dwelling.main_sys_1
    TYPES=sap.sap_tables.HeatingSystem.TYPES
    if sys.system_type in [TYPES.combi, TYPES.cpsu, TYPES.electric_boiler, TYPES.boiler]:
        return "boiler"
    elif sys.system_type==TYPES.storage_heater:
        return "storage heater"
    elif sys.system_type==TYPES.integrated_system:
        #raise RuntimeError("HELP!")
        # !!! Can't really do this type of system, what is closest we can do?
        return "storage heater"
    elif sys.system_type==TYPES.heat_pump:
        return "heat pump"
    elif sys.system_type==TYPES.room_heater:
        return "room heater"
    elif sys.system_type==TYPES.warm_air:
        # !!! Check this
        return "room heater"
    else:
        # Misc type
        raise RuntimeError("HELP!")

def pressure_test_result(dwelling):
    if hasattr(dwelling,'pressurisation_test_result'):
        return dwelling.pressurisation_test_result
    elif hasattr(dwelling,'pressurisation_test_result_average'):
        return dwelling.pressurisation_test_result_average+2
    else:
        return 0

# Valid values:
# mains gas
# bulk lpg
# bottled lpg
# electricity
# solid
# oil
# biomass
FUEL_MAPPING={
    sap.sap_tables.MAINS_GAS:'mains gas',
    sap.sap_tables.BULK_LPG:'bulk lpg',
    sap.sap_tables.BOTTLED_LPG:'bottled lpg',
    sap.sap_tables.LPG_COND18:'bulk lpg', # !!! Best I can do
    sap.sap_tables.HEATING_OIL:'oil',
    sap.sap_tables.COAL:'solid',
    sap.sap_tables.SMOKELESS_FUEL:'solid',
    sap.sap_tables.ANTHRACITE:'solid',
    sap.sap_tables.WOOD_LOGS:'biomass',
    sap.sap_tables.WOOD_PELLETS_MAIN:'biomass',
    sap.sap_tables.WOOD_PELLETS_SECONDARY:'biomass',
    sap.sap_tables.WOOD_CHIPS:'biomass',
    sap.sap_tables.DUAL_FUEL:'solid',
    sap.sap_tables.B30K:'oil',
    sap.sap_tables.BIODIESEL_UCO:'oil',
    sap.sap_tables.ELECTRICITY_STANDARD:'electricity',
    sap.sap_tables.ELECTRICITY_7HR:'electricity',
    sap.sap_tables.ELECTRICITY_10HR:'electricity',
    sap.sap_tables.ELECTRICITY_24HR:'electricity',

}

ORIENTATIONS={
    0:'N',
    45:'NE/NW',
    90:'E/W',
    135:'SE/SW',
    180:'S',
    225:'SE/SW',
    270:'E/W',
    315:'NE/NW',
}

VENTILATION_TYPES={
    sap.sap_tables.VentilationTypes.NATURAL:'natural ventilation',
    sap.sap_tables.VentilationTypes.MEV_CENTRALISED:'mev',
    sap.sap_tables.VentilationTypes.MEV_DECENTRALISED:'mev',
    sap.sap_tables.VentilationTypes.MVHR:'balance whole house mv',
}

ETI_MAPPING=[
    ('Case_Number',             dwelling_val('casenum')),
    ('Weights',                 constant(1)),
    ('ConstructionDate',        constant(1)), # Choose an early construction date to get correct floor infiltration
    ('BuildType',               temp_val(1)),
    ('Volume',                  dwelling_val('volume')),
    ('TFA',                     dwelling_val('GFA')),
    ('Number_Occupants',        dwelling_val('Nocc')),
    ('Degree_day',              constant(22)), # 7 is closest to SAP temperatures dwelling_val('sap_region')),
    ('Height',                  constant(0)), # Height above sea level
    ('Z1_percent',              as_percent(dwelling_val('living_area_fraction'))),
    ('Interzone_Links',         constant("stairs do not link z1 & z2 directly")), # Only matters if Z2 is unheated
    ('Total_WallArea (exc openings)',
                                element_property('Walls (1)','area')),
    ('Primary_WallType',        temp_val("cavity insulated")),
    ('Primary_WallUval',        element_property('Walls (1)','Uvalue')),
    ('Primary_Wallkval',       lambda d: d.thermal_mass_parameter*d.GFA/element_property('Walls (1)','area')(d)), # All of thermal mass is lumped into wall kval
    ('Secondary_WallType',      constant('cavity insulated')),
    ('Secondary_WallUval',      constant(0)),
    ('Secondary_Wallkval',      constant(0)),
    ('Proportion_SecondaryWall',constant(0)),
    ('Gnd_Floor_Area',          dwelling_val('eti_extfloor_area')),
    ('Floor_Uval',              dwelling_val('eti_extfloor_Uvalue')),
    ('Roof_Area',               element_property('Roof (1)','area')),
    ('Roof_Uval',               element_property('Roof (1)','Uvalue')),
    ('Door_Area',               element_property('Doors','area')),
    ('Door_Uval',               element_property('Doors','Uvalue')),
    ('Party_wall_area',         element_property('Party wall','area')),
    ('Party_wall_Uval',         element_property('Party wall','Uvalue')),
    ('Window_Area',             dwelling_val('eti_win_area')),
    ('Window_Uval',             dwelling_val('eti_win_Uvalue')),
    ('Rooflight_Area',          element_property('Roof windows (1)','area')),
    ('Rooflight_Uval',          element_property('Roof windows (1)','Uvalue')),
    ('Curtains_Present',        constant(0)), # So that window u value correction is applied
    ('Norm',                    constant(0.9)),
    ('Th_bridge_fac',           dwelling_val('Uthermalbridges')),
    ('orientation',             lambda x: ORIENTATIONS[dwelling_val('orientation')(x)]),
    ('Trans_fac',               dwelling_val('eti_win_gvalue')),
    ('frame_fac',               dwelling_val('eti_win_frame_factor')),
    ('shading_fac',             dwelling_val('solar_access_factor_winter')),
    ('basement',                constant(0)),
    ('basement_FA',             constant(0)),
    ('Basement_floor_kval',     constant(0)),
    ('Floor_kval',              constant(0)),
    ('Basement_wall',           constant(0)),
    ('Basement_wall_kval',      constant(0)),
    ('Roof_kval',               constant(0)),
    ('Roof_ins',                unused()),
    ('Party_wall_kval',         constant(0)),
    ('party_floor',             constant(0)),
    ('party_floor_kval',        constant(0)),
    ('party_ceiling',           constant(0)),
    ('party_ceiling_kval',      constant(0)),
    ('IntwallA',                constant(0)),
    ('Intwallkval',             constant(0)),
    ('internal_floorA',         constant(0)),
    ('internal_floor_kval',     constant(0)),
    ('internal_ceilingA',       constant(0)),
    ('internal_ceiling_kval',   constant(0)),
    ('No_Chimneys',             as_int(dwelling_val('Nchimneys'))),
    ('No_flues',                as_int(dwelling_val('Nflues'))),
    ('No_fans_vents',           as_int(dwelling_val('Nfansandpassivevents'))),
    ('no_flueless_gas',         as_int(dwelling_val('Nfluelessgasfires'))),
    ('pressurisation_test_result',pressure_test_result),
    ('Prop_sus',               lambda d: 1 if hasattr(d,'floor_infiltration') and d.floor_infiltration>0 else 0),
    ('No_Storeys',              dwelling_val('Nstoreys')),
    ('Loft_hatch',              constant(0)),
    ('Draught_lobby',           as_int(dwelling_val_or_zero('has_draught_lobby'))),
    ('win_infil_rate',          dwelling_val_or_zero('window_infiltration')),
    ('wall_infil_rate',         dwelling_val_or_zero('structural_infiltration')),
    ('Sheltered_Sides',         as_int(dwelling_val('Nshelteredsides'))),
    ('Site_Exposure',           dwelling_val('eti_site_exposure')),
    ('Avg_wind_speed',          constant(4.5)), # Closest match to sap vals
    ('vent_type',              lambda d: VENTILATION_TYPES[d.ventilation_type]),
    ('HeatRec_Eff',             dwelling_val_or_zero('mvhr_effy')),
    ('percent_LELights',        as_percent(dwelling_val('low_energy_bulb_ratio'))),
    ('CHPump',                  as_int(dwelling_val('has_ch_pump'))),
    ('OilBoiler',               as_int(dwelling_val('has_oil_pump'))),
    ('CHPump_HeatedSpace',      constant(1)),
    ('NonOilBoiler',            as_int(dwelling_val('has_flue_fan'))),
    ('WarmAirFan',              as_int(dwelling_val('eti_haswarmairfan'))),
    ('RoomHeater_Fan',          temp_val(0)),
    ('combi_keephot',           temp_val("NA")),
    ('VentFan_Power',           dwelling_val_or_zero('adjusted_fan_sfp')),
    ('VentHeatRec_eff',         temp_val(0)),
    ('InUse_fan',               constant(1)), # merged with sfp
    ('InUse_HeatRec',           temp_val(0)),
    ('SolarWH_Pump_type',       temp_val("None")),
    ('Cooking_fuel',            constant("gas/electric")),
    ('KitchenINZone',           constant(1)),
    ('Glazing_Transmittance_fac',dwelling_val('eti_win_light_transmittance')),
    ('lights_access_fac',       dwelling_val('light_access_factor')),
    ('Z1Demand_Temp',           constant(21)),
    ('Temp_diff',               constant(3)),
    ('Temp_penalty',            constant(0)),
    ('level_Z2TempCtrl',       lambda d: 0 if d.heating_control_type==1 else 1),
    ('Frac_Z2heated',           constant(100)),
    ('fstOn_Z1wkday',           unused()),
    ('fstOn_Z1wkend',           unused()),
    ('fstOn_Z2wkday',           unused()),
    ('fstOn_Z2wkend',           unused()),
    ('fstOff_Z1wkday',          constant(7)),
    ('fstOff_Z1wkend',          constant(0)),
    ('fstOff_Z2wkday',         lambda x: 9 if x.heating_control_type==3 else 7),
    ('fstOff_Z2wkend',         lambda x: 9 if x.heating_control_type==3 else 0),
    ('secOn_Z1wkday',           unused()),
    ('secOn_Z1wkend',           unused()),
    ('secOn_Z2wkday',           unused()),
    ('secOn_Z2wkend',           unused()),
    ('secOff_Z1wkday',          constant(8)),
    ('secOff_Z1wkend',          constant(8)),
    ('secOff_Z2wkday',          constant(8)),
    ('secOff_Z2wkend',          constant(8)),
    ('DelayedStart',            constant(0)),
    ('Temp_Adjustment',         dwelling_val('temperature_adjustment')),
    ('Cooling_Demand_temp',     constant(24)),
    ('Frac_AirConditioned',     dwelling_val('fraction_cooled')),
    ('Cooling_SEER',            temp_val(2)),
    ('PriSH_fuel',             lambda d: FUEL_MAPPING[d.main_sys_1.fuel]),
    ('PriSH_Type',              space_heating_type),
    ('Boiler_Type',             dwelling_val('eti_boiler_type')),
    ('PriSH_Eff',               dwelling_val('eti_effy')),
    ('PriSH_responsiveness',    dwelling_val('heating_responsiveness')),
    ('SecSH_Eff',              lambda d: d.secondary_sys.effy if hasattr(d,'secondary_sys') else 100),
    ('SecSH_responsiveness',    dwelling_val('heating_responsiveness')),
    ('H_proportion_secsys',    lambda d: 100-100*d.fraction_of_heat_from_main),
    ('Boiler_interlock',        as_int(dwelling_val('has_boiler_interlock'))),
    ('PriWH_Type',              water_heater_type),
    ('secWH_eff',               constant(100)), # No secondard HW system in tests cases
    ('HW_proportion_secsys',    constant(0)),
    ('Manufacturer_declared_loss',dwelling_val_or_zero('measured_cylinder_loss')),
    ('temp_factor',             dwelling_val_or_zero('temperature_factor')),
    ('Tank',                    as_int(dwelling_val('has_hw_cylinder'))),
    ('Tank_vol',                dwelling_val_or_zero('hw_cylinder_volume')),
    ('Tank_Ins_type',           dwelling_val_or_zero('hw_cylinder_insulation_type')),
    ('tank_ins_thickness',      dwelling_val_or_zero('hw_cylinder_insulation')),
    ('pri_energy_circuitloss',  dwelling_val('primary_circuit_loss_annual')),
    ('Additional_combi_loss',  lambda d: d.combi_loss(100) if hasattr(d,'combi_loss') else 0), # !!! Not quite right - assumes daily water use of 100 litres
    ('Collector_ApertureA',     constant(0)),
    ('Collector_Tilt',          constant(0)),
    ('OverShading_Fac',         constant(0)),
    ('solar_storage_vol',       constant(120)),
    ('Tcylinder_volume',        constant(0)),
    ('solar_water_heating',     unused()),
    ('Occupied_Area',           unused()),
    ('Electricity_tariff',      temp_val("Standard")),
    ('Immersion_Heater_Type',   temp_val("")),
    ('HeatPump_EmitterType',    constant("radiators without weather/load comp")), # give correct effy factor for the only heat pump tests case
    ('PercentHotWater_HeatPump',constant(100)), # Test cases are all 100% HW heat pumps?
    ('SecSH_fuel',              temp_val("mains gas")),
    ('Income',                  unused()),
]

def print_eti_inputs(eti_in):
    #for k,v in eti_in.items():
    #    print "%s=%s" % (k,v,)

    first=True
    for k,v in list(eti_in.items()):
        if not first:
            sys.stdout.write(",")
        first=False
        sys.stdout.write("%s" % (v,))
    sys.stdout.write("\n")
    sys.stdout.flush()

# The boiler type from appendix d and the adjustment that needs to be
# made to the winter effy to get the sap 2009 effy
appendix_d_mapping_gas={
    '101':('on/off regular',.9,-9.2),
    '102':('modulating regular',1,-9.7),
    '103':('on/off combi',.8,-8.5),
    '104':('modulating combi',.9,-9.2),
    '105':('on/off storage combi',.7,-7.2),
    '106':('modulating storage combi',.8,-8.3),
    '107':('cpsu',.22,-1.64),
}

appendix_d_mapping_oil={
    '201':('regular',1.1,-10.6),
    '202':('combi',1,-8.5),
    '203':('storage combi',.9,-7.2),
}

def best_match(app_d_mappings,winter_effy,summer_effy):
    best=None
    best_err=999
    for btype in list(app_d_mappings.values()):
        effy_diff=btype[1]-btype[2]
        this_err=abs((winter_effy-summer_effy)-effy_diff)
        if this_err<best_err:
            best_err=this_err
            best=btype

    logging.info("Inferred SAP boiler type as %s", best[0])
    return best


def best_match_gas(winter_effy,summer_effy):
    return best_match(appendix_d_mapping_gas,winter_effy,summer_effy)

def best_match_oil(winter_effy,summer_effy):
    return best_match(appendix_d_mapping_oil,winter_effy,summer_effy)

def set_eti_boiler_type_and_effy(d):
    # Ignore second main system
    sys=d.main_sys_1
    if sys.fuel.type()==sap.sap_tables.FuelTypes.GAS and hasattr(sys,'sap_appendixD_eqn'):
        # A boiler from PCDF, which gives the appendix d equation directly
        appendix_d_type=appendix_d_mapping_gas[sys.sap_appendixD_eqn]
        d.eti_boiler_type=appendix_d_type[0]
        d.eti_effy=sys.heating_effy_winter-appendix_d_type[1]
    else:
        # A sap system, need to trick eti model into using correct
        # winter and summer effys
        if sys.system_type==sap.sap_tables.HeatingSystem.TYPES.cpsu:
            boiler_type=best_match_gas(sys.heating_effy_winter,sys.heating_effy_summer)
            d.eti_boiler_type=boiler_type[0]
            d.eti_effy=sys.heating_effy_winter-boiler_type[1]
        elif hasattr(sys,'heating_effy_winter'):
            if sys.heating_effy_winter>sys.heating_effy_summer:
                if FUEL_MAPPING[sys.fuel]=="oil":
                    btype=best_match_oil(sys.heating_effy_winter,
                                         sys.heating_effy_summer)
                else:
                    btype=best_match_gas(sys.heating_effy_winter,
                                         sys.heating_effy_summer)

                d.eti_boiler_type=btype[0]
                d.eti_effy=sys.heating_effy_winter-btype[1]
            else:
                # Most likely a solid fuel boiler
                d.eti_effy=sys.heating_effy_winter 
                d.eti_boiler_type="regular" 
        else:
            d.eti_boiler_type="regular" if FUEL_MAPPING[sys.fuel]=="oil" else "on/off regular"
            d.eti_effy=sys.space_heat_effy(0)
            if hasattr(sys,'space_mult'):
                d.eti_effy/=sys.space_mult
            if hasattr(sys,'space_adj'):
                d.eti_effy-=sys.space_adj

def calc_average_window(d):
    area_sum=0
    Uvalue_sum=0
    gvalue_sum=0
    frame_factor_sum=0
    light_transmittance_sum=0
    
    for o in d.openings:
        area_sum+=o.area
        frame_factor_sum+=o.type.frame_factor*o.area
        light_transmittance_sum+=o.type.light_transmittance*o.area
        gvalue_sum+=o.type.gvalue*o.area
        Uvalue_sum+=o.type.Uvalue*o.area

    d.eti_win_area=area_sum
    d.eti_win_gvalue=gvalue_sum/area_sum
    d.eti_win_frame_factor=frame_factor_sum/area_sum
    d.eti_win_light_transmittance=light_transmittance_sum/area_sum
    d.eti_win_Uvalue=Uvalue_sum/area_sum

def calc_average_external_floor(d):
    A1=element_property('Ground floor','area')(d)
    A2=element_property('Exposed floor','area')(d)
    A3=element_property('Conservatory floor','area')(d)

    U1=element_property('Ground floor','Uvalue')(d)
    U2=element_property('Exposed floor','Uvalue')(d)
    U3=element_property('Conservatory floor','Uvalue')(d)
    d.eti_extfloor_area=A1+A2+A3
    d.eti_extfloor_Uvalue=(U1*A1+U2*A2+U3*A3)/(A1+A2+A3) if A1+A2+A3>0 else 0

def calc_site_exposure(d):
    sap_shelterfactor=1-0.075*d.Nshelteredsides
    bredem_shelterfactor=1-.05*d.Nshelteredsides
    d.eti_site_exposure=sap_shelterfactor/bredem_shelterfactor

import numpy
if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s: %(message)s')

    casenums_skip_test_case=[16,20,30]
    casenums_cannot_run=[#25,
                         12, # Has a dedicated HW system and secondary heating
                         20, # Has 3 heating systems
                         21, # Has 3 heating systems
                         ]
    casenums_more_than_1_orientation=[6,7,8,]
    casenums_immersion_summer=[9,14,15,21,]

    casenums=numpy.arange(29)+2
    #casenums=[29,]
    for casenum in casenums:
        logging.info("RUNNING %d" % (casenum,))
        if casenum in casenums_skip_test_case: 
            logging.error("Skipping this tests case")
            continue
        if casenum in casenums_cannot_run: 
            logging.error("Can't run this one")
            continue
        if casenum in casenums_immersion_summer:
            logging.warn("Uses immersion heater in summer")
        if casenum in casenums_more_than_1_orientation:
            logging.warn("More than one window orientation")

        res,d=v0.run_dwelling(casenum)
        d.casenum=casenum
        set_eti_boiler_type_and_effy(d)
        calc_average_window(d)
        calc_average_external_floor(d)
        calc_site_exposure(d)

        d.eti_haswarmairfan=d.main_sys_1.has_warm_air_fan or (
            hasattr(d,'main_sys_2') and d.main_sys_2.has_warm_air_fan)


        if not (d.main_sys_1.fuel.type()==sap.sap_tables.FuelTypes.GAS or
                d.main_sys_1.fuel.type()==sap.sap_tables.FuelTypes.OIL):
            # Needed to make sure interlock penalty isn't applied to
            # solid fuel boilers
            logging.info("Forcing interlock")
            d.has_boiler_interlock=True

        eti_in=collections.OrderedDict()
        
        for mapping in ETI_MAPPING:
            eti_in[mapping[0]]=mapping[1](d)

        print_eti_inputs(eti_in)

""" Useful SQL
DELETE FROM ETI.dbo.SAPTestCases;

BULK
 INSERT ETI.dbo.SAPTestCases
 FROM 'C:\\UCL\SAP\test_cases\eti.txt'
 WITH
 (
 FIELDTERMINATOR = ',',
 ROWTERMINATOR = '\n'
 );

DROP TABLE ETI.dbo.inputs;

SELECT * INTO ETI.dbo.inputs from ETI.dbo.SAPTestCases

"""
