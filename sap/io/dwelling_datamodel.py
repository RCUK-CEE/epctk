from .validator import required, one_of, attribute, group, required_if_and_only_if, \
    main_heating_is_oil_boiler, has_second_main_heating, optional_group, required_if

ATTRIBUTES = [
    required("GFA", float),
    required("volume", float),
    required("Nstoreys", int),
    required("thermal_mass_parameter", float),
    required("Uthermalbridges", float),
    required("low_water_use", bool),
    required("sap_region", int),
    required("overshading", int),  # enum

    required("ventilation_type", int),  # enum
    required("Nflues", int),
    required("Nintermittentfans", int),
    required("Nchimneys", int),
    required("Npassivestacks", int),
    required("Nshelteredsides", int),
    one_of("air tightness",
           attribute("pressurisation_test_result_average", float),
           attribute("pressurisation_test_result", float),
           group(
               attribute("has_draught_lobby", bool),
               attribute("floor_type", int),  # enum
               attribute("draught_stripping", float),
               attribute("wall_type", int))),  # enum

    one_of("low energy lighting",
           group(
               attribute("lighting_outlets_low_energy", int),
               attribute("lighting_outlets_total", int)),
           attribute("low_energy_bulb_ratio", float)),

    one_of("living area",
           attribute("living_area_fraction", float),
           attribute("living_area", float)),

    one_of("main heating type",
           attribute("main_heating_pcdf_id", int),
           attribute("main_heating_type_code", int)),
    # attribute("main_sys_fuel",int), # Errr?
    attribute("control_type_code", int),
    required_if_and_only_if(
        main_heating_is_oil_boiler,
        attribute("main_heating_oil_pump_inside_dwelling", bool)),
    # required_if_and_only_if(
    #    main_heating_uses_table_4d,
    # attribute("heating_emitter_type",int)), # enum
    # required_if_and_only_if(
    #    main_heating_is_gas_or_oil_boiler,
    #    attribute("sys1_has_boiler_interlock",bool)),
    required_if_and_only_if(
        has_second_main_heating,
        attribute("main_heating_fraction", float)),

    # optional_group(
    #    attribute("secondary_heating_type_code",int),
    # attribute("secondary_sys_fuel",int)), # errr?

    required("water_heating_type_code", int),
    # required("water_sys_fuel",int), # err

    optional_group(
        attribute("use_immersion_heater_summer", bool)),
    required_if(
        lambda d: hasattr(
            d, "use_immersion_heater_summer") and d.use_immersion_heater_summer,
        attribute("immersion_type", int)),  # enum

    optional_group(
        # attribute("hw_cylinder_type",int), # enum
        one_of(
            attribute("measured_cylinder_loss", float),
            group(
                attribute("hw_cylinder_volume", float),
                attribute("hw_cylinder_insulation_type", int),  # enum
                attribute("hw_cylinder_insulation", float)))),
    #        attribute("cylinder_in_heated_space",bool),
    #        attribute("has_cylinderstat",bool),
    #        attribute("has_hw_time_control",bool),
    #        attribute("primary_pipework_insulated",bool)),

    optional_group(
        # !!! Also need orientation inputs
        attribute("PV_kWp", float),
        attribute("pv_overshading_category", int)),

    optional_group(
        attribute("hydro_electricity", float)),

    optional_group(
        attribute("wind_turbine_hub_height", float),
        attribute("N_wind_turbines", int),
        attribute("wind_turbine_rotor_diameter", float)),
    required("terrain_type", int),  # enum - but only really required
    # when there is a wind turbine?

    optional_group(
        one_of("cooled area",
               attribute("cooled_area", float),
               attribute("fraction_cooled", float)),
        attribute("cooling_compressor_control", str),
        attribute("cooling_packaged_system", bool),
        attribute("cooling_energy_label", str),
    ),
]





class Dwellng():
    GFA = required(float)
    volume = required(float)
    Nstoreys = required(int)

    # ... and so on...
    # BUT
    # seems like a good idea until you get the case where you need one of a list of attributes
    # which is hard to model as object properties. Think its therefore a better fit
    # for a dict/json type validation scheme



    required("Nstoreys", int)
    required("thermal_mass_parameter", float)
    required("Uthermalbridges", float)
    required("low_water_use", bool)
    required("sap_region", int)
    required("overshading", int)  # enum

    required("ventilation_type", int)  # enum
    required("Nflues", int)
    required("Nintermittentfans", int)
    required("Nchimneys", int)
    required("Npassivestacks", int)
    required("Nshelteredsides", int)
    one_of("air tightness",
           attribute("pressurisation_test_result_average", float),
           attribute("pressurisation_test_result", float),
           group(
               attribute("has_draught_lobby", bool),
               attribute("floor_type", int),  # enum
               attribute("draught_stripping", float),
               attribute("wall_type", int))),  # enum

    one_of("low energy lighting",
           group(
               attribute("lighting_outlets_low_energy", int),
               attribute("lighting_outlets_total", int)),
           attribute("low_energy_bulb_ratio", float)),

    one_of("living area",
           attribute("living_area_fraction", float),
           attribute("living_area", float)),

    one_of("main heating type",
           attribute("main_heating_pcdf_id", int),
           attribute("main_heating_type_code", int)),
    # attribute("main_sys_fuel",int), # Errr?
    attribute("control_type_code", int),
    required_if_and_only_if(
        main_heating_is_oil_boiler,
        attribute("main_heating_oil_pump_inside_dwelling", bool)),
    # required_if_and_only_if(
    #    main_heating_uses_table_4d,
    # attribute("heating_emitter_type",int)), # enum
    # required_if_and_only_if(
    #    main_heating_is_gas_or_oil_boiler,
    #    attribute("sys1_has_boiler_interlock",bool)),
    required_if_and_only_if(
        has_second_main_heating,
        attribute("main_heating_fraction", float)),

    # optional_group(
    #    attribute("secondary_heating_type_code",int),
    # attribute("secondary_sys_fuel",int)), # errr?

    required("water_heating_type_code", int),
    # required("water_sys_fuel",int), # err

    optional_group(
        attribute("use_immersion_heater_summer", bool)),
    required_if(
        lambda d: hasattr(
            d, "use_immersion_heater_summer") and d.use_immersion_heater_summer,
        attribute("immersion_type", int)),  # enum

    optional_group(
        # attribute("hw_cylinder_type",int), # enum
        one_of(
            attribute("measured_cylinder_loss", float),
            group(
                attribute("hw_cylinder_volume", float),
                attribute("hw_cylinder_insulation_type", int),  # enum
                attribute("hw_cylinder_insulation", float)))),
    #        attribute("cylinder_in_heated_space",bool),
    #        attribute("has_cylinderstat",bool),
    #        attribute("has_hw_time_control",bool),
    #        attribute("primary_pipework_insulated",bool)),

    optional_group(
        # !!! Also need orientation inputs
        attribute("PV_kWp", float),
        attribute("pv_overshading_category", int)),

    optional_group(
        attribute("hydro_electricity", float)),

    optional_group(
        attribute("wind_turbine_hub_height", float),
        attribute("N_wind_turbines", int),
        attribute("wind_turbine_rotor_diameter", float)),
    required("terrain_type", int),  # enum - but only really required
    # when there is a wind turbine?

    optional_group(
        one_of("cooled area",
               attribute("cooled_area", float),
               attribute("fraction_cooled", float)),
        attribute("cooling_compressor_control", str),
        attribute("cooling_packaged_system", bool),
        attribute("cooling_energy_label", str),
    )
