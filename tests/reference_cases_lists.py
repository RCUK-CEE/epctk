SKIP = [

     # FIXME no code 495xxx in PCDF database
    "EW-3k-semi - with Test Database-index 495006.rtf",
    "EW-3L-semi - with Test Database-index 495007.rtf",

    # FIXME: NO codes for 493xxx boilers in PCDF database
    "EW-5d-detached-oil- as 1m but database boiler 493072_ fuel UCOME oil.rtf",
    "EW-5e-detached-oil- as 1m but database boiler 493071_ any biodiesel.rtf",  # secondary heating manuf data
    "EW-5f-detached-oil- as 1m but Database index 493075 efficiency 90_2_fuel B30K oil.rtf",
    "EW-5g-detached-oil- as 1m but database boiler 493074_ mineral or bio oil.rtf",  # wwhr
    "EW-5h-detached-oil- as 1m but database boiler 493073_ fuel rapeseed oil.rtf",
    "EW-5i-detached-oil- with bioethanol secondary.rtf",  # secondary sys fuel?
    "EW-5j-detached-oil- with B30K secondary.rtf",  # second sys manuf data

    "EW-10a- Heatpump - s-1_v-1(variable) higher PSR.rtf",
    "EW-10b- Heatpump - s-1_v-2(variable).rtf",
    "EW-10c- Heatpump - s-1_v-3(variable).rtf",
    "EW-10d- Heatpump - s-2_v-1(variable).rtf",
    "EW-10e- Heatpump - s-2_v-2(variable).rtf",
    "EW-10f- Heatpump - s-2_v-3(variable).rtf",
    "EW-10g- Heatpump - s-3_v-4(variable).rtf",
    "EW-10h-Heatpump- s-1_v-1(variable) with lower PSR.rtf",
    "EW-10i-Heatpump - s-1_v-1(24-hour).rtf",
    "EW-10j- Heatpump - s-1_v-1(16-hour).rtf",
    "EW-10k-Heatpump - s-1_v-1(11-hour).rtf",
    "EW-10r- Heatpump - warm air 493194.rtf",


    # FIXME: NO code 492xxx boilers in PCDF database
    "EW-9c- mCHP - oil - service 1 vessel 1 - test database 492023.rtf",  # fan and pump gain is odd?
    "EW-9d- mCHP - Ex 3_ service 1 vessel 1.rtf",
    "EW-9e- m-CHP - Ex 3_ service 1 vessel 1.rtf",
    "EW-9f- mCHP - Ex 3_ service 1 vessel 3.rtf",
    "EW-9g- mCHP - Ex 3_ service 2 vessel 1.rtf",
    "EW-9h- mCHP - Ex 3_ service 2 vessel 3.rtf",
    "EW-9i- mCHP - Ex 3_ service 3 vessel 4.rtf",

    # Fixme: Bug with this one, does not load water storage loss factor
    "EW-10m- Heatpump Daikin index 100013 -10-hour.rtf",

    # This one doesn't parse
    "EW-10s- semi - heat pump with PSR too large.rtf",


]

OFFICIAL_CASES_THAT_WORK = [
    "EW-1a-detached.rtf",  # manufacturer's data
    "EW-1b-detached with semi-exposed elements.rtf",  # manufacturer's data
    "EW-1c-detached.rtf",
    "EW-1d-detached.rtf",
    "EW-1e-detached.rtf",
    "EW-1f-detached.rtf",
    "EW-1g-detached.rtf",
    "EW-1h-detached.rtf",
    "EW-1i-detached.rtf",
    "EW-1j-detached.rtf",
    "EW-1k-detached.rtf",
    "EW-1L-detached.rtf",
    "EW-1m-detached.rtf",
    "EW-1n-detached.rtf",
    "EW-1p-detached.rtf",  # solar hot water, manuf data for secondary heating

    "EW-2a-semi with semi-exposed elements-basic.rtf",
    "EW-2b-semi with WWHR-regular boiler.rtf",
    "EW-2c-semi with WWHR+solar water heating.rtf",  # sedbuk data, range cooker
    "EW-2d-semi with WWHR+solar water heating+FGHRS.rtf",  # fghrs
    "EW-2e-semi with CPSU fired by LPG.rtf",  # manufacturer's data, lpg cpsu
    "EW-2f-semi - integrated storage_direct 7-hour.rtf",
    "EW-2g-semi - 7-hour electric boiler.rtf",  # thermal mass from k values
    "EW-2h-semi -10-hour electric boiler.rtf",
    "EW-2i-semi - underfloor 7-hour.rtf",
    "EW-2j-semi - underfloor 10-hour.rtf",
    "EW-2k-semi - electric CPSU_10-hour 180 litres.rtf",  # On Peak CPSU
    "EW-2L-semi - electric CPSU_10-hour 300 litres.rtf",  # On peak CPSU
    "EW-2m-semi - direct acting - boiler.rtf",  # thermal mass from k values
    "EW-2n -semi - electric ceiling heating _ water from single immersion.rtf",  # thermal mass from k values
    "EW-2p-semi -electric underfloor, water - oil range cooker.rtf",  # thermal mass from k values
    "EW-2r-semi - room heaters - water by immersion with solar panel.rtf",  # WWHR, aappendix q generation
    "EW-2s-semi - Electricaire - water by Range with solar panel.rtf",  # APP q

    "EW-3a-mid-terrace.rtf",  # manuf data
    "EW-3b-mid-terrace with solid fuel boiler.rtf",
    "EW-3c - MidTerrace - pellet stove - with solar DHW a1 is 20.rtf",
    "EW-3d - MT-biomass room heaters and no dedicated cylinder for solar DHW.rtf",
    "EW-3e - MT-gas warm air and MVHR checking Table 5a.rtf",
    "EW-3f - MT-gas warm air and flueless gas fire - water from immersion.rtf",
    "EW-3g -EndTerrace-LPG warm air and decorative bottled gas fire.rtf",
    # different offpeak fraction for mech vent fans?
    "EW-3h - MT-oil range cooker_ secondary oil and water oil.rtf",  # manuf second heat # MV fans on peak fraction
    "EW-3i- flat - mid floor_gas boiler 01840 and DHW thermal store.rtf",  # FGHR
    "EW-3j- flat - mid floor_gas boiler 01840 and integrated thermal store.rtf",  # FGHR
    "EW-3k-semi - with Test Database-index 495006.rtf",  # pcdf combi loss calc
    "EW-3L-semi - with Test Database-index 495007.rtf",  # FGHR
    "EW-3m-semi - with Database-index 08088 keep-hot_FGHRS 60001 and WWHR.rtf",  # fghrs
    "EW-3n-semi - non-cond combi 09977 keep-hot_NO interlock - with Enh_load_comp - no adj.rtf",  # WWHR
    "EW-3p-semi - Cond-combi 10222 keep-hot_underfloor+weather compensator - immersion water_so +3 adj.rtf",  # WWH
    "EW-3r-semi - non-cond Combi 09506 keep-hot_underfloor+weather comp_immersion DHW - no adj.rtf",
    "EW-3s-semi - LPG Non-cond Regular 09529_weather compens_underfloor_immersion DHW_adj +2r.rtf",
    "EW-3t-semi - OIL RegularCond 08584_weather compens_underfloor_immersion DHW so +2 adj.rtf",

    "EW-4a - detached basic - electric CPSU_bottled gas room heater_MVHR.rtf",  # Elec CPSU
    "EW-4b - flat ground floor - database 05983 combi secondary store.rtf",  # App Q
    "EW-4c - MT with garage - gas boiler 04162 with primary store.rtf",
    "EW-4d - detached - LPG boiler 09978_gas timed keep-hot_water from secondary 606.rtf",
    "EW-4e - detached LARGE_m-CHP Baxi with separate DHW.rtf",  # microCHP
    "EW-4f - semi with garage_anthracite range cooker code 160.rtf",
    "EW-4g - bungalow semi_gas heat pump with radiators.rtf",  # in use factors messed up?
    "EW-4h - bungalow L-shaped detached_electric heatpump with fan coil unit.rtf",  # in use factors messed up?
    "EW-4i - flat - upper Maisonette_LPG warm air heatpump.rtf",
    "EW-4j - flat - mid floor_electric air-to air heatpump_DHW from HP.rtf",
    "EW-4k - flat - upper floor_community heating CHP and boilers.rtf",  # community heating
    "EW-4k(a) - flat - upper floor_community heating CHP and boilers.rtf",
    "EW-4k(b) - flat - upper floor_community heating CHP and boilers.rtf",
    "EW-4L - mid-terrace _community  Heatpump with cylinder in dwelling and Solar.rtf",
    # community heating - TER fuel factor,etc
    "EW-4m - mid-terrace_integrated storage+direct acting.rtf",
    "EW-4n - terraced - three storey_Electric CPSU code192.rtf",  # electric cpsu
    "EW-4p - bung with room in room_dual fuel  open fire with Back Boiler code 156.rtf",  # WWHR, half glazed door
    "EW-4r - semi with garage -5 storey_oil-fired warm air code 513_DHW from secondary.rtf",  # WWHR

    "EW-5a-semi with WWHR+solar+FGHRS_09899 fuelled by LPG special cond 18.rtf",
    "EW-5b- flat - mid floor_gas boiler 01840 and integrated thermal store_ as 3i but fuelled by LNG.rtf",  # fghrs
    "EW-5c-detached-oil- as 1m but Manufacturers efficiency 89_6_ fuel UCOME oil.rtf",  # SEDBUK data
    "EW-5d-detached-oil- as 1m but database boiler 493072_ fuel UCOME oil.rtf",
    "EW-5e-detached-oil- as 1m but database boiler 493071_ any biodiesel.rtf",  # secondary heating manuf data
    "EW-5f-detached-oil- as 1m but Database index 493075 efficiency 90_2_fuel B30K oil.rtf",
    "EW-5g-detached-oil- as 1m but database boiler 493074_ mineral or bio oil.rtf",  # wwhr
    "EW-5h-detached-oil- as 1m but database boiler 493073_ fuel rapeseed oil.rtf",
    "EW-5i-detached-oil- with bioethanol secondary.rtf",  # secondary sys fuel?
    "EW-5j-detached-oil- with B30K secondary.rtf",  # second sys manuf data

    "EW-6a- detached LARGE_community heating - mixture of 2 systems.rtf",
    "EW-6b - detached LARGE_community heating - several boilers.rtf",
    "EW-6c - detached LARGE_community heating - several boilers +Heatpump.rtf",
    "EW-6d - detached LARGE_community heating - mixture of 5 systems.rtf",
    "EW-6e - flat - mid floor_community 5 sources _ water by main community with WWHR.rtf",
    "EW-6f - semi with garage_range cooker heating_separate community DHW.rtf",
    "EW-6g- semi with garage_community heating_separate community DHW.rtf",
    "EW-6h - detached LARGE_community heating - several boilers+Heatpump+Geothermal.rtf",
    "EW-6i- detached LARGE_community heating - mixture of 2 systems.rtf",

    "EW-7a - semi with garage_NEW Appendix Q.rtf",  # app Q
    "EW-7b - semi with garage_NEW Appendix Q  air change rates.rtf",  # app Q
    "EW-7c - FlowSmart.rtf",  # fghrs

    "EW-8a - semi - with multiboiler heating - 2 boilers - DHW from 2nd boiler.rtf",
    "EW-8b - semi - with multiboiler heating - 2 boilers - DHW from 1st boiler.rtf",
    "EW-8c - semi - with multiboiler heating - 2 boilers - gas 16013 and oil 15482_DHW from 1st.rtf",  # FGHRS with PV
    "EW-8d - semi - with multiboiler heating - 2 boilers - gas 16013 and oil 15482_DHW from 2nd-WWHR.rtf",
    "EW-8e- semi existing - with multi-system heating - heatpump 100073  and gas boiler_DHW from 1st.rtf",
    # PCDF heat pump
    "EW-8f- semi - with multi-system heating - heatpump 100033 and gas boiler_DHW from 1st.rtf",  # PCDF heat pump
    "EW-8g- semi - with multi-system heating - Electric boiler _WOOD STOVE  room heaters _water from immersion.rtf",

    "EW-9a- micro-CHP Baxi Ecogen - index 40001 - bad insulation.rtf",
    "EW-9b- micro-CHP Baxi Ecogen - index 40001- good insulation.rtf",
    "EW-9c- mCHP - oil - service 1 vessel 1 - test database 492023.rtf",  # fan and pump gain is odd?
    "EW-9d- mCHP - Ex 3_ service 1 vessel 1.rtf",
    "EW-9e- m-CHP - Ex 3_ service 1 vessel 1.rtf",
    "EW-9f- mCHP - Ex 3_ service 1 vessel 3.rtf",
    "EW-9g- mCHP - Ex 3_ service 2 vessel 1.rtf",
    "EW-9h- mCHP - Ex 3_ service 2 vessel 3.rtf",
    "EW-9i- mCHP - Ex 3_ service 3 vessel 4.rtf",

    "EW-10a- Heatpump - s-1_v-1(variable) higher PSR.rtf",
    "EW-10b- Heatpump - s-1_v-2(variable).rtf",
    "EW-10c- Heatpump - s-1_v-3(variable).rtf",
    "EW-10d- Heatpump - s-2_v-1(variable).rtf",
    "EW-10e- Heatpump - s-2_v-2(variable).rtf",
    "EW-10f- Heatpump - s-2_v-3(variable).rtf",
    "EW-10g- Heatpump - s-3_v-4(variable).rtf",
    "EW-10h-Heatpump- s-1_v-1(variable) with lower PSR.rtf",
    "EW-10i-Heatpump - s-1_v-1(24-hour).rtf",
    "EW-10j- Heatpump - s-1_v-1(16-hour).rtf",
    "EW-10k-Heatpump - s-1_v-1(11-hour).rtf",
    "EW-10L- Heatpump Nibe Fighter 360 index 100101- 7-hour.rtf",
    "EW-10L2 as 10L but smaller house.rtf",
    "EW-10m- Heatpump Daikin index 100013 -10-hour.rtf",
    "EW-10n- Heatpump Dimplex index 100043 - 7-hour.rtf",
    "EW-10p- Heatpump Mitsubishi - index 100052 -10 hour.rtf",
    "EW-10q- Heatpump Vaillant - index 100081 - standatd tariff.rtf",
    "EW-10r- Heatpump - warm air 493194.rtf",
    "EW-10s- semi - heat pump with PSR too large.rtf",
]

OFFICIAL_CASES = [
    "EW-1a-detached.rtf",  # manufacturer's data

]
