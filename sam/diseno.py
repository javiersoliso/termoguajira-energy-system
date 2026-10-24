"""Modelo del SEI Fuel Cell + PV + BESS (config. SAM "Fuel Cell - Commercial") para La Guajira.

`entradas(**p)` arma las entradas SSC a partir de los valores por defecto de SAM, replicando las
ecuaciones de la interfaz para el tamaño de la batería y de la celda de combustible.
`simular(**p)` corre pvwattsv8 -> fuelcell -> battery -> grid y devuelve series + indicadores
calculados con las fórmulas de la guía (sección 6).
"""
import math
from pathlib import Path
import numpy as np
import ssc

AQUI = Path(__file__).parent
# SSC no abre rutas con tildes ni eñes: el repositorio debe estar en una ruta solo ASCII
CLIMA = str((AQUI.parent / "data" / "DIBULLA_1254249_11.17_-73.70_tmy-2025.csv").resolve())
UMBRAL_KW = 1.0   # residuos numéricos de SAM (1e-9 a 1e-3 kW) no cuentan como horas con déficit/excedente
CARGA = np.loadtxt(AQUI.parent / "demanda" / "carga_SAM_la_guajira_8760_kW.csv", skiprows=1)   # 1a línea = encabezado (SAM la ignora)

BASE = dict(
    # PV (PVWatts)
    pv_kwdc=250_000, dc_ac=1.25, array_type=3, tilt=0, azimuth=180, gcr=0.35, module_type=0,
    inv_eff=96.0, losses=None,
    # Celda de combustible (SOFC, H2)
    fc_kw=70_000, fc_unidades=14, fc_min_pct=30, fc_rampa_pct_h=100, fc_despacho=1, fc_operacion=1,
    fc_degr_pct_anual=2.0, fc_arranque_h=24, fc_iniciada=1,
    # Batería (LFP, AC, BTM)
    batt_kw=60_000, batt_kwh=240_000, batt_despacho=5, batt_min_soc=15, batt_max_soc=95,
    batt_carga_desde_fc=0,
    # Simulación
    vida_util=0,
)


def entradas(**p):
    q = {**BASE, **p}
    d = ssc.defaults()
    d["solar_resource_file"] = CLIMA
    d["load"] = CARGA.tolist()
    d["system_use_lifetime_output"] = q["vida_util"]
    if not q["vida_util"]:
        d["analysis_period"] = 1

    # ---------------- PV
    d.update(system_capacity=q["pv_kwdc"], dc_ac_ratio=q["dc_ac"], array_type=q["array_type"],
             tilt=q["tilt"], azimuth=q["azimuth"], gcr=q["gcr"], module_type=q["module_type"],
             inv_eff=q["inv_eff"])
    if q["losses"] is not None:
        d["losses"] = q["losses"]

    # ---------------- Celda de combustible (ecuaciones de la página Fuel Cell)
    n = int(q["fc_unidades"]); unit = q["fc_kw"] / n
    d.update(fuelcell_unit_max_power=unit, fuelcell_number_of_units=n,
             fuelcell_unit_min_power=unit * q["fc_min_pct"] / 100,
             fuelcell_dynamic_response_up=unit * q["fc_rampa_pct_h"] / 100,
             fuelcell_dynamic_response_down=unit * q["fc_rampa_pct_h"] / 100,
             fuelcell_degradation=unit * q["fc_degr_pct_anual"] / 100 / 8760,
             fuelcell_dispatch_choice=q["fc_despacho"], fuelcell_operation_options=q["fc_operacion"],
             fuelcell_startup_time=q["fc_arranque_h"], fuelcell_shutdown_time=q["fc_arranque_h"],
             fuelcell_is_started=q["fc_iniciada"])
    # campos de interfaz (solo informativos)
    d.update(fuelcell_power_nameplate=q["fc_kw"], fuelcell_power_kw=unit, fuelcell_power_total=q["fc_kw"])

    # ---------------- Batería (ecuaciones de "Battery Bank Sizing", unidades DC)
    vnom, qfull = d["batt_Vnom_default"], d["batt_Qfull"]
    series = math.ceil(d["batt_bank_voltage"] / vnom)
    strings = round(q["batt_kwh"] * 1000 / (qfull * series * vnom))
    cap = qfull * strings * series * vnom / 1000
    p_dc = q["batt_kw"] * cap / q["batt_kwh"]
    d.update(batt_computed_series=series, batt_computed_strings=strings, batt_computed_bank_capacity=cap,
             batt_power_discharge_max_kwdc=p_dc, batt_power_charge_max_kwdc=p_dc,
             batt_power_discharge_max_kwac=p_dc * d["batt_dc_ac_efficiency"] / 100,
             batt_power_charge_max_kwac=p_dc / (d["batt_ac_dc_efficiency"] / 100),
             batt_current_discharge_max=p_dc * 1000 / (series * vnom),
             batt_current_charge_max=p_dc * 1000 / (series * vnom),
             batt_mass=cap * 1000 / d["batt_specific_energy_per_mass"],
             batt_surface_area=cap / d["batt_unit_capacity"] * d["batt_unit_surface_area"],
             batt_Qfull_flow=qfull * strings, LeadAcid_q20_computed=qfull * strings,
             batt_bank_power=q["batt_kw"], batt_bank_size=q["batt_kwh"], batt_bank_size_ui=q["batt_kwh"],
             batt_dispatch_choice=q["batt_despacho"], batt_minimum_SOC=q["batt_min_soc"],
             batt_maximum_SOC=q["batt_max_soc"],
             batt_dispatch_auto_can_fuelcellcharge=q["batt_carga_desde_fc"])
    return d


SALIDAS = ["load", "gen", "gen_without_battery", "ac", "fuelcell_power", "fuelcell_power_thermal",
           "fuelcell_electrical_efficiency", "fuelcell_percent_load", "batt_SOC", "system_to_batt",
           "fuelcell_to_batt", "grid_to_batt", "batt_to_load", "batt_to_grid", "system_to_load",
           "fuelcell_to_load", "grid_to_load", "system_to_grid", "fuelcell_to_grid", "interconnection_loss",
           "batt_power", "batt_computed_bank_capacity"]


def simular(**p):
    r = ssc.run(entradas(**p), outputs=SALIDAS)
    s = {k: np.asarray(v[:8760], float) for k, v in r.items() if isinstance(v, list)}
    s["pv_kw"] = s["ac"] / 1000.0
    return s, indicadores(s, p)


def indicadores(s, p=None):
    q = {**BASE, **(p or {})}
    dem, gen = s["load"], s["gen_without_battery"]            # generación PV + FC antes de la batería
    carga = s["system_to_batt"] + s["fuelcell_to_batt"] + s["grid_to_batt"]
    desc = s["batt_to_load"] + s["batt_to_grid"]
    deficit = np.maximum(0, dem - gen - desc)
    exced = np.maximum(0, gen - dem - carga)
    cobert = dem - deficit
    cap_kwh = q["batt_kwh"]
    e_pv, e_fc = s["pv_kw"].sum(), s["fuelcell_power"].sum()
    # combustible (LHV) a partir de la eficiencia eléctrica horaria
    eff = np.where(s["fuelcell_electrical_efficiency"] > 0, s["fuelcell_electrical_efficiency"] / 100, np.nan)
    comb_kwh = np.nansum(s["fuelcell_power"] / eff)
    return dict(
        E_dem_GWh=dem.sum() / 1e6, E_pv_GWh=e_pv / 1e6, E_fc_GWh=e_fc / 1e6,
        cobertura_pct=cobert.sum() / dem.sum() * 100,
        renovable_directa_pct=None,
        deficit_GWh=deficit.sum() / 1e6, horas_deficit=int((deficit > UMBRAL_KW).sum()), deficit_max_MW=deficit.max() / 1e3,
        excedente_GWh=exced.sum() / 1e6, horas_exced=int((exced > UMBRAL_KW).sum()),
        carga_bat_GWh=carga.sum() / 1e6, desc_bat_GWh=desc.sum() / 1e6,
        ciclos=desc.sum() / cap_kwh, eta_rt_pct=desc.sum() / max(carga.sum(), 1) * 100,
        fc_CF_pct=e_fc / (q["fc_kw"] * 8760) * 100, pv_yield=e_pv / q["pv_kwdc"],
        H2_t=comb_kwh / 33.33 / 1000, calor_fc_GWh=s["fuelcell_power_thermal"].sum() / 1e6,
        soc_min=s["batt_SOC"].min(), soc_max=s["batt_SOC"].max(),
    )
