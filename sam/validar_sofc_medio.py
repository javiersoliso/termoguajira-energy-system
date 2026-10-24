"""Valida con SSC el punto medio de la SOFC con la FV limitada a ~500 MWdc (escala de Guayepo I&II)."""
import csv, json, numpy as np, diseno, ssc
from correr_diseno_final import DISENO
CASOS = [  # (nombre, cambios)
    ("SOFC 110 · FV 300 · bat 60/480", dict(batt_kw=60_000, batt_kwh=480_000)),
    ("SOFC 100 · FV 350 · bat 80/640", dict(fc_kw=100_000, pv_kwdc=350_000, batt_kw=80_000, batt_kwh=640_000)),
    ("SOFC 90 · FV 400 · bat 100/960", dict(fc_kw=90_000, pv_kwdc=400_000, batt_kw=100_000, batt_kwh=960_000)),
    ("SOFC 90 · FV 400 · bat 120/1280", dict(fc_kw=90_000, pv_kwdc=400_000, batt_kw=120_000, batt_kwh=1_280_000)),
    ("SOFC 80 · FV 450 · bat 120/1280", dict(fc_kw=80_000, pv_kwdc=450_000, batt_kw=120_000, batt_kwh=1_280_000)),
    ("SOFC 80 · FV 450 · bat 150/1600", dict(fc_kw=80_000, pv_kwdc=450_000, batt_kw=150_000, batt_kwh=1_600_000)),
    ("SOFC 70 · FV 500 · bat 150/2000", dict(fc_kw=70_000, pv_kwdc=500_000, batt_kw=150_000, batt_kwh=2_000_000)),
    ("SOFC 60 · FV 500 · bat 150/2400", dict(fc_kw=60_000, pv_kwdc=500_000, batt_kw=150_000, batt_kwh=2_400_000)),
]
OUT = []
for nombre, cambio in CASOS:
    p = {**DISENO, **cambio, "batt_carga_desde_fc": 1}
    r = ssc.run(diseno.entradas(**p), outputs=diseno.SALIDAS)
    s = {k: np.asarray(v[:8760], float) for k, v in r.items() if isinstance(v, list)}
    L = s["load"]; dfc = s["grid_to_load"]; exc = s["system_to_grid"] + s["fuelcell_to_grid"]; dis = s["batt_to_load"]
    eff = np.where(s["fuelcell_electrical_efficiency"] > 0, s["fuelcell_electrical_efficiency"] / 100, np.nan)
    h2 = np.nansum(s["fuelcell_power"] / eff) / 33.33 / 1000
    pv = p["pv_kwdc"] / 1000
    row = dict(caso=nombre, sofc_MW=p["fc_kw"] / 1000, pv_MWdc=pv, bat_MW=p["batt_kw"] / 1000, bat_MWh=p["batt_kwh"] / 1000,
               cobertura_pct=round((1 - dfc.sum() / L.sum()) * 100, 2), deficit_GWh=round(dfc.sum() / 1e6, 1), horas_deficit=int((dfc > 1).sum()),
               pct_horas=round((dfc > 1).mean() * 100, 1), deficit_max_MW=round(dfc.max() / 1000, 1), excedente_GWh=round(exc.sum() / 1e6),
               H2_t=round(h2), pct_H2_Colombia=round(h2 / 150000 * 100, 1), ahorro_H2_t=round(45221 - h2),
               terreno_FV_ha_modulos=round(pv * 1000 / 0.19 / 0.3 / 1e4), terreno_FV_ha_Guayepo=round(pv * 1110 / 486.7),
               bateria_MUSD=f'{round(p["batt_kwh"] * 0.12 / 1000)}-{round(p["batt_kwh"] * 0.35 / 1000)}', firme_MW=(p["fc_kw"] + p["batt_kw"]) / 1000)
    OUT.append(row); print(json.dumps(row, ensure_ascii=False))
with open("validacion_sofc_medio_SAM.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(OUT[0])); w.writeheader(); w.writerows(OUT)
