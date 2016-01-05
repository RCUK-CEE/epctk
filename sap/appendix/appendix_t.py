"""
Appendix T : Improvement measures
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


"""
from ..tables import table_2a_hot_water_vol_factor
from .. import worksheet
from ..configure import lookup_sap_tables
from ..dwelling import DwellingResults
from ..sap_types import HeatingTypes, PVOvershading


def apply_low_energy_lighting(base, dwelling):
    """
    Apply low energy lighting improvement
    :param base: base performance is ignored, but necessary to maintain consisten interface
    :param dwelling:
    :return:
    """
    if ((dwelling.get('low_energy_bulb_ratio') and dwelling.low_energy_bulb_ratio == 1) or
                dwelling.lighting_outlets_low_energy == dwelling.lighting_outlets_total):
        return False

    dwelling.low_energy_bulb_ratio = 1
    return True


def needs_separate_solar_cylinder(base):
    """

    Args:
        base: The base dwelling configuration
    Returns:

    """
    if base.water_sys.system_type in [HeatingTypes.cpsu,
                                      HeatingTypes.combi,
                                      HeatingTypes.storage_combi,
                                      HeatingTypes.heat_pump,
                                      HeatingTypes.pcdf_heat_pump]:
        return True

    if base.get('instantaneous_pou_water_heating'):
        return True

    if base.water_sys.system_type == HeatingTypes.community and base.get('hw_cylinder_volume') is None:
        return True

    if (base.water_sys.system_type == HeatingTypes.microchp
        and base.water_sys.has_integral_store):
        return True

    return False


def apply_solar_hot_water(base, dwelling):
    """
    Apply the solar hot water improvement
    Args:
        base: The base dwelling configuration
        dwelling: The improved dwelling configuration

    Returns:

    """
    if dwelling.is_flat:
        return False

    if dwelling.get('solar_collector_aperture', 0) > 0:
        return False

    dwelling.solar_collector_aperture = 3
    dwelling.collector_zero_loss_effy = .7
    dwelling.collector_heat_loss_coeff = 1.8
    dwelling.collector_orientation = 180.
    dwelling.collector_pitch = 30.
    dwelling.collector_overshading = PVOvershading.MODEST
    dwelling.has_electric_shw_pump = True
    dwelling.solar_dedicated_storage_volume = 75.

    if needs_separate_solar_cylinder(base):
        dwelling.solar_storage_combined_cylinder = False
    else:
        assert dwelling.hw_cylinder_volume > 0
        dwelling.solar_storage_combined_cylinder = True

        if dwelling.hw_cylinder_volume < 190 and dwelling.get('measured_cylinder_loss'):
            old_vol_fac = table_2a_hot_water_vol_factor(dwelling.hw_cylinder_volume)
            new_vol_fac = table_2a_hot_water_vol_factor(190)
            dwelling.measured_cylinder_loss *= new_vol_fac * 190 / (old_vol_fac * dwelling.hw_cylinder_volume)
            dwelling.hw_cylinder_volume = 190
        else:
            dwelling.hw_cylinder_volume = max(dwelling.hw_cylinder_volume, 190.)

    return True


def apply_pv(base, dwelling):
    """
    Apply PV improvements. Only valid if the dwelling is not a flat
    and there are no photovoltaic systems already installed

    Args:
        base: The base dwelling configuration
        dwelling: The improved dwelling configuration

    Returns:
        Update the dwelling configuration and return bool indicating
        whether the PV improvement applies
    """
    # TODO: check whether the is_flat etc checks should be on the base dwelling or the improved one
    if dwelling.is_flat:
        return False

    if len(dwelling.get('photovoltaic_systems', [])) > 0:
        return False

    pv_system = dict(
            kWp=2.5,
            pitch=30,
            orientation=180,
            overshading_category=PVOvershading.MODEST
    )
    dwelling.photovoltaic_systems = [pv_system, ]
    return True


def apply_wind(base, dwelling):
    """

    Args:
        base: The base dwelling configuration
        dwelling: The improved dwelling configuration

    Returns:
        Update the dwelling configuration and return bool indicating
        whether the wind improvement applies
    """
    if dwelling.is_flat:
        return False

    if dwelling.get('N_wind_turbines', 0) > 0:
        return False

    dwelling.N_wind_turbines = 1
    dwelling.wind_turbine_rotor_diameter = 2.0
    dwelling.wind_turbine_hub_height = 2.0
    return True


IMPROVEMENTS = [
    ("E", 0.45, apply_low_energy_lighting),
    ("N", 0.95, apply_solar_hot_water),
    ("U", 0.95, apply_pv),
    ("V", 0.95, apply_wind),
]


def apply_previous_improvements(base, target, previous):
    for improvement in previous:
        name, min_val, improve = [improve for improve in IMPROVEMENTS if improve[0] == improvement.tag][0]
        improve(base, target)
        improve(base, target)


def run_improvements(dwelling):
    """
    Need to run the dwelling twice: once with pcdf fuel prices to
    get cost change, once with normal SAP fuel prices to get change
    in SAP rating

    :param dwelling:
    :return:
    """

    base_dwelling_pcdf_prices = DwellingResults(dwelling)
    # print('478: ', dwelling.get('hw_cylinder_volume'))
    # print('479: ', base_dwelling_pcdf_prices.get('hw_cylinder_volume'))

    base_dwelling_pcdf_prices.reduced_gains = False
    base_dwelling_pcdf_prices.use_pcdf_fuel_prices = True
    lookup_sap_tables(base_dwelling_pcdf_prices)

    worksheet.perform_full_calc(base_dwelling_pcdf_prices)
    worksheet.sap(base_dwelling_pcdf_prices)

    dwelling.improvement_results = ImprovementResults()

    base_cost = base_dwelling_pcdf_prices.fuel_cost
    base_sap = dwelling.sap_value
    base_co2 = dwelling.emissions

    # Now improve the dwelling
    for name, min_improvement, improve in IMPROVEMENTS:
        dwelling_pcdf_prices = DwellingResults(dwelling)
        dwelling_pcdf_prices.reduced_gains = False
        dwelling_pcdf_prices.use_pcdf_fuel_prices = True

        dwelling_regular_prices = DwellingResults(dwelling)
        dwelling_regular_prices.reduced_gains = False
        dwelling_regular_prices.use_pcdf_fuel_prices = False

        apply_previous_improvements(
                base_dwelling_pcdf_prices,
                dwelling_regular_prices,
                dwelling.improvement_results.improvement_effects)

        apply_previous_improvements(
                base_dwelling_pcdf_prices,
                dwelling_pcdf_prices,
                dwelling.improvement_results.improvement_effects)

        if not improve(base_dwelling_pcdf_prices, dwelling_pcdf_prices):
            continue

        improve(base_dwelling_pcdf_prices, dwelling_regular_prices)

        lookup_sap_tables(dwelling_pcdf_prices)
        worksheet.perform_full_calc(dwelling_pcdf_prices)
        worksheet.sap(dwelling_pcdf_prices)

        lookup_sap_tables(dwelling_regular_prices)
        worksheet.perform_full_calc(dwelling_regular_prices)
        worksheet.sap(dwelling_regular_prices)

        sap_improvement = dwelling_regular_prices.sap_value - base_sap

        if sap_improvement > min_improvement:
            dwelling.improvement_results.add(ImprovementResult(
                    name,
                    sap_improvement,
                    dwelling_pcdf_prices.fuel_cost - base_cost,
                    dwelling_regular_prices.emissions - base_co2))

            base_cost = dwelling_pcdf_prices.fuel_cost
            base_sap = dwelling_regular_prices.sap_value
            base_co2 = dwelling_regular_prices.emissions

    improved_dwelling = DwellingResults(dwelling)
    improved_dwelling.reduced_gains = False
    improved_dwelling.use_pcdf_fuel_prices = False

    for improvement in dwelling.improvement_results.improvement_effects:
        name, min_val, improve = [x for x in IMPROVEMENTS if x[0] == improvement.tag][0]
        improve(base_dwelling_pcdf_prices, improved_dwelling)

    lookup_sap_tables(improved_dwelling)

    worksheet.perform_full_calc(improved_dwelling)
    worksheet.sap(improved_dwelling)

    dwelling.report.build_report()
    # print improved_dwelling.report.print_report()

    dwelling.improved_results = improved_dwelling.results


class ImprovementResult:
    def __init__(self, tag, sap_change, cost_change, co2_change):
        self.tag = tag
        self.sap_change = sap_change
        self.co2_change = co2_change
        self.cost_change = cost_change


class ImprovementResults:
    def __init__(self):
        self.improvement_effects = []

    def add(self, i):
        self.improvement_effects.append(i)