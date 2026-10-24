"""Valida con el motor de SAM (SSC) las configuraciones candidatas para cerrar el déficit."""
import json, numpy as np, diseno, ssc
from correr_diseno_final import DISENO
CASOS = {
    "Diseño entregado (300/110/20-160)": {},
    "A · batería 60 MW / 480 MWh": dict(batt_kw=60_000, batt_kwh=480_000),
    "B · batería 60/640 + carga desde SOFC": dict(batt_kw=60_000, batt_kwh=640_000, batt_carga_desde_fc=1),
    "C · FV 400 + batería 60/480 + carga desde SOFC": dict(pv_kwdc=400_000, batt_kw=60_000, batt_kwh=480_000, batt_carga_desde_fc=1),
    "D · FV 400 + batería 80/640 + carga desde SOFC": dict(pv_kwdc=400_000, batt_kw=80_000, batt_kwh=640_000, batt_carga_desde_fc=1),
    "E · SOFC 130 (batería 20/160)": dict(fc_kw=130_000),
    "F · rampa SOFC 40 %/h": dict(fc_rampa_pct_h=40),
    "G · SOFC 120 + batería 40/320 + carga desde SOFC": dict(fc_kw=120_000, batt_kw=40_000, batt_kwh=320_000, batt_carga_desde_fc=1),
}
OUT = []
for nombre, cambio in CASOS.items():
    p = {**DISENO, **cambio}
    r = ssc.run(diseno.entradas(**p), outputs=diseno.SALIDAS)
    s = {k: np.asarray(v[:8760], float) for k, v in r.items() if isinstance(v, list)}
    L = s["load"]; dfc = s["grid_to_load"]; exc = s["system_to_grid"] + s["fuelcell_to_grid"]
    dis = s["batt_to_load"]; eff = np.where(s["fuelcell_electrical_efficiency"] > 0, s["fuelcell_electrical_efficiency"] / 100, np.nan)
    h2 = np.nansum(s["fuelcell_power"] / eff) / 33.33 / 1000
    land = p["pv_kwdc"] / 0.19 / 0.3 / 1e4 + p["fc_kw"] / 1000 * 107 / 1e4 + p["batt_kwh"] / 1000 * 12.14 / 1e4
    row = dict(caso=nombre, pv_MWdc=p["pv_kwdc"] / 1000, sofc_MW=p["fc_kw"] / 1000, rampa=p["fc_rampa_pct_h"], bat_MW=p["batt_kw"] / 1000,
               bat_MWh=p["batt_kwh"] / 1000, carga_desde_sofc=p.get("batt_carga_desde_fc", 0), firme_MW=(p["fc_kw"] + p["batt_kw"]) / 1000,
               cobertura_pct=round((1 - dfc.sum() / L.sum()) * 100, 2), deficit_GWh=round(dfc.sum() / 1e6, 2),
               horas_deficit=int((dfc > 1).sum()), pct_horas_deficit=round((dfc > 1).mean() * 100, 1), deficit_max_MW=round(dfc.max() / 1000, 1),
               excedente_GWh=round(exc.sum() / 1e6, 1), H2_t=round(h2), ciclos_bat=round(dis.sum() / p["batt_kwh"], 0), terreno_ha=round(land))
    OUT.append(row); print(json.dumps(row, ensure_ascii=False))
import csv
with open("validacion_brecha_SAM.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(OUT[0])); w.writeheader(); w.writerows(OUT)
