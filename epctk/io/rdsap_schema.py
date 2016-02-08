
{
'main': [
    {'fuel_type': 'asd',
     'hetas_approved': False},
    {'fuel_type': 'csd'}
]
}


sap_schema = {
    "$schema": "http://json-schema.org/schema#",
    "title": "SAP dwelling input",
    "description": "inputs required to perform a SAP calculation",
    "type": "object",
    "additionalProperties": False,

    "definitions": {
        "water_system_definition": {
            "properties": {
                "water_system":{
                    "type": "object",
                    "properties": {
                        "has_interlock": {
                            "type": "bool"
                        }
                    }
                }
            }
        },
        "wall_definition": {
            "properties": {
                "wall_material": {
                    "type": "string",
                    "enum": ["stone_hard", "stone_sandstone", "solid_brick", "cob", "cavity", "timber", "system"]
                },
                "wall_insulation": {
                    "type": "string",
                    "enum": ["internal", "external", "fill", "none"]
                },
                "wall_type": {
                    "type": "int"
                },

                "wall_u_value": {
                    "type": "float"
                },
            },

            "oneOf": [
                {
                    "required": [
                        "wall_u_value"
                    ]
                },
                {
                    "required": [
                        "wall_material", "wall_insulation"
                    ]
                }]
        },
        "opening_type": {
            "properties": {
                "glazing_type": {
                    "type": "int"
                },
                "gvalue": {
                    "type": "float"
                },
                "frame_factor": {
                    "type": "float"
                },
                "Uvalue": {
                    "type": "float"
                },
                "roof_window": {
                    "type": "bool"
                },
                "bfrc_data": {
                    "type": "bool"
                }
            },
            "required": [
                "glazing_type",
                "gvalue",
                "frame_factor",
                "Uvalue",
                "roof_window"
            ]
        },
        "pressure_test": {
            "properties": {
                "pressurisation_test_result_average": {
                    "type": "float"
                },
                "pressurisation_test_result": {
                    "type": "float"
                },
                "has_draught_lobby": {
                    "type": "bool"
                },
                "draught_stripping": {
                    "type": "float"
                }
            },
            "oneOf": [
                {
                    "required": [
                        "pressurisation_test_result_average"
                    ]
                },
                {
                    "required": [
                        "pressurisation_test_result"
                    ]
                },
                {
                    "required": [
                        # Lobby inferred from building type for RdSAP
                        # "has_draught_lobby",
                        # stripping inferred from opening types for RdSAP
                        # "draught_stripping",
                        "floor_type",
                        "wall_type"
                    ]
                }
            ]
        },
        "living_area": {
            "properties": {
                "living_area_fraction": {
                    "type": "float"
                },
                "living_area": {
                    "type": "float"
                }
            },
            "oneOf": [
                {
                    "required": [
                        "living_area"
                    ]
                },
                {
                    "required": [
                        "living_area_fraction"
                    ]
                }
            ]
        },
        "main_heating": {
            "properties": {
                "main_heating_type_code": {
                    "type": "int"
                },
                "main_heating_pcdf_id": {
                    "type": "int"
                }
            },
            "oneOf": [
                {
                    "required": [
                        "main_heating_pcdf_id"
                    ]
                },
                {
                    "required": [
                        "main_heating_type_code"
                    ]
                }
            ]
        },
        "immersion_heater": {
            "properties": {
                "use_immersion_heater_summer": {
                    "type": "bool"
                },
                "immersion_type": {
                    "type": "int"
                }
            }
        },
        "cylinder_loss": {
            "oneOf": [
                {
                    "properties": {
                        "measured_cylinder_loss": {
                            "type": "float"
                        }
                    },
                    "required": [
                        "measured_cylinder_loss"
                    ]
                },
                {
                    "properties": {
                        "hw_cylinder_volume": {
                            "type": "float"
                        },
                        "hw_cylinder_insulation_type": {
                            "type": "int"
                        },
                        "hw_cylinder_insulation": {
                            "type": "float"
                        }
                    },
                    "required": [
                        "hw_cylinder_volume",
                        "hw_cylinder_insulation_type",
                        "hw_cylinder_insulation"
                    ]
                }
            ]
        },
        "pv": {
            # TODO need 'all or nothing' so i think you want oneOf with [{}, {...}]?
            #      "oneOf": [{}, ]
            "properties": {
                "PV_kWp": {
                    "type": "float"
                },
                "pv_overshading_category": {
                    "type": "int"
                }
            },
            "required": [
                "PV_kWp",
                "pv_overshading_category"
            ]
        },
        "wind_turbines": {
            "properties": {
                "wind_turbine_hub_height": {
                    "type": "float"
                },
                "N_wind_turbines": {
                    "type": "int"
                },
                "wind_turbine_rotor_diameter": {
                    "type": "float"
                }
            }
        },
        "cooling": {
            "properties": {
                "cooled_area": {
                    "type": "float"
                },
                "fraction_cooled": {
                    "type": "float"
                },
                "cooling_compressor_control": {
                    "type": "string"
                },
                "cooling_packaged_system": {
                    "type": "bool"
                },
                "cooling_energy_label": {
                    "type": "string"
                }
            }
        }
    },
    "allOf": [
        {
            "$ref": "#/definitions/pressure_test"
        },
        {
            "$ref": "#/definitions/living_area"
        },
        {
            "$ref": "#/definitions/main_heating"
        },
        {
            "$ref": "#/definitions/immersion_heater"
        },
        {
            "$ref": "#/definitions/cylinder_loss"
        },
        {
            "$ref": "#/definitions/wall_definition"
        },
        {
            "properties": {
                # TODO: many INT properties are actually ENUMS
                # TODO: might actually want to do Dict validation so we can reuse Enum definitions...
                "sap_region": {
                    "type": "int",
                    "enum": [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20]
                },
                "country_code": {
                    "type": "string",
                    # country codes follow ISO 3166-1
                    "enum": ["GB-EAW", "GB-ENG", "GB-NIR", "GB-SCT", "GB-WLS"]
                },
                "dwelling_type": {
                    "type": "string",
                    "enum": ["house", "flat", "bungalow", "maisonette"]
                },
                "n_rooms": {
                    "type": "int"
                },


                "GFA": {
                    "type": "float"
                },
                "volume": {
                    "type": "float"
                },
                "Nstoreys": {
                    "type": "int"
                },
                "thermal_mass_parameter": {
                    "type": "float"
                },
                "Uthermalbridges": {
                    "type": "float"
                },
                "low_water_use": {
                    "type": "bool"
                },
                "Nflues": {
                    "type": "int"
                },
                "Nintermittentfans": {
                    "type": "int"
                },
                "Nchimneys": {
                    "type": "int"
                },
                "Npassivestacks": {
                    "type": "int"
                },
                "Nshelteredsides": {
                    "type": "int"
                },
                "water_heating_type_code": {
                    "type": "int"
                },
                # enums

                "overshading": {
                    "type": "int"
                },
                "ventilation_type": {
                    "type": "int"
                },
                "control_type_code": {
                    "type": "int"
                },
                # enums
                "floor_type": {
                    "type": "int"
                },

                # has if and only if constraint, might have to rethink or have extra validation step
                "main_heating_oil_pump_inside_dwelling": {
                    "type": "bool"
                },
                "main_heating_fraction": {
                    "type": "float"
                },
                "hydro_electricity": {
                    "type": "float"
                },
                "terrain_type": {
                    "type": "int"
                }
            },
            "required": [
                "sap_region"
                "GFA",
                "volume",
                "Nstoreys",
                "thermal_mass_parameter",
                "Uthermalbridges",
                "low_water_use",
                "sap_region",
                "overshading",
                "ventilation_type",
                "Nflues",
                "Nintermittentfans",
                "Nchimneys",
                "Npassivestacks",
                # "Nshelteredsides", rdsap could be inferred
                "control_type_code",
                "water_heating_type_code"
            ],
        }
    ]
}
