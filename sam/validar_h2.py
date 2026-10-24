"""Valida con el motor de SAM (SSC) diseños con menos hidrógeno: SOFC pequeña + FV y batería grandes."""
import csv, json, numpy as np, diseno, ssc
from correr_diseno_final import DISENO
CASOS = {
    "Entregado: FV 300 · SOFC 110 · bat 20/160": {},
    "B: FV 300 · SOFC 110 · bat 60/640 + carga SOFC": dict(batt_kw=60_000, batt_kwh=640_000, batt_carga_desde_fc=1),
    "H1: FV 600 · SOFC 60 · bat 150/2000 + carga SOFC": dict(pv_kwdc=600_000, fc_kw=60_000, batt_kw=150_000, batt_kwh=2_000_000, batt_carga_desde_fc=1),
    "H2: FV 700 · SOFC 40 · bat 200/3200 + carga SOFC": dict(pv_kwdc=700_000, fc_kw=40_000, batt_kw=200_000, batt_kwh=3_200_000, batt_carga_desde_fc=1),
    "H3: FV 900 · SOFC 20 · bat 250/2400 + carga SOFC": dict(pv_kwdc=900_000, fc_kw=20_000, batt_kw=250_000, batt_kwh=2_400_000, batt_carga_desde_fc=1),
    "H4: FV 1100 · SOFC 1 · bat 250/3200 (casi sin H2)": dict(pv_kwdc=1_100_000, fc_kw=1_000, batt_kw=250_000, batt_kwh=3_200_000, batt_carga_desde_fc=1),
}
OUT = []
for nombre, cambio in CASOS.items():
    p = {**DISENO, **cambio}
    r = ssc.run(diseno.entradas(**p), outputs=diseno.SALIDAS)
    s = {k: np.asarray(v[:8760], float) for k, v in r.items() if isinstance(v, list)}
    L = s["load"]; dfc = s["grid_to_load"]; exc = s["system_to_grid"] + s["fuelcell_to_grid"]; dis = s["batt_to_load"]
    eff = np.where(s["fuelcell_electrical_efficiency"] > 0, s["fuelcell_electrical_efficiency"] / 100, np.nan)
    h2 = np.nansum(s["fuelcell_power"] / eff) / 33.33 / 1000
    pv_ha = p["pv_kwdc"] / 0.19 / 0.3 / 1e4
    row = dict(caso=nombre, pv_MWdc=p["pv_kwdc"] / 1000, sofc_MW=p["fc_kw"] / 1000, bat_MW=p["batt_kw"] / 1000, bat_MWh=p["batt_kwh"] / 1000,
               cobertura_pct=round((1 - dfc.sum() / L.sum()) * 100, 2), deficit_GWh=round(dfc.sum() / 1e6, 1), horas_deficit=int((dfc > 1).sum()),
               pct_horas=round((dfc > 1).mean() * 100, 1), deficit_max_MW=round(dfc.max() / 1000, 1), excedente_GWh=round(exc.sum() / 1e6),
               H2_t=round(h2), pct_H2_Colombia=round(h2 / 150000 * 100, 1), sofc_GWh=round(s["fuelcell_power"].sum() / 1e6), fv_GWh=round(s["ac"].sum() / 1e9),
               bat_entrega_GWh=round(dis.sum() / 1e6), terreno_FV_ha=round(pv_ha), terreno_total_ha=round(pv_ha + p["fc_kw"] / 1000 * 107 / 1e4 + p["batt_kwh"] / 1000 * 12.14 / 1e4),
               bateria_MUSD=f'{round(p["batt_kwh"] * 0.12 / 1000)}-{round(p["batt_kwh"] * 0.35 / 1000)}')
    OUT.append(row); print(json.dumps(row, ensure_ascii=False))
with open("validacion_h2_SAM.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(OUT[0])); w.writeheader(); w.writerows(OUT)
