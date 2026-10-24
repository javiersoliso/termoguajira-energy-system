"""Corre las configuraciones finalistas con la cadena completa de SAM (Fuel Cell - Commercial, como la interfaz)
y guarda los valores de control para comprobar la configuración hecha a mano en SAM:

  - finalistas_brecha_SAM.csv         : indicadores + valores de Results > Summary + sumas de las columnas del Anexo 1
  - finalistas_brecha_mensual_SAM.csv : déficit y horas con déficit por mes y por finalista
"""
import csv
import numpy as np
import diseno, ssc
from correr_diseno_final import DISENO
from barrido_fino_brecha import terreno_ha

FINALISTAS = {
    "Diseño entregado": dict(),
    "B (referencia)": dict(batt_kw=60_000, batt_kwh=640_000, batt_carga_desde_fc=1),
    "F1 · solo batería 70/640": dict(batt_kw=70_000, batt_kwh=640_000, batt_carga_desde_fc=1),
    "F2 · SOFC 120 + batería 70/480": dict(fc_kw=120_000, batt_kw=70_000, batt_kwh=480_000, batt_carga_desde_fc=1),
    "F3 · FV 400 + batería 80/640 (= D)": dict(pv_kwdc=400_000, batt_kw=80_000, batt_kwh=640_000, batt_carga_desde_fc=1),
}
SUMAS = ["load", "ac", "fuelcell_power", "gen_without_battery", "system_to_batt", "fuelcell_to_batt", "batt_to_load",
         "grid_to_load", "system_to_grid", "fuelcell_to_grid", "fuelcell_power_thermal"]
MESES = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def correr(cambio):
    p = {**DISENO, **cambio}
    d = diseno.entradas(vida_util=1, **p)
    d["analysis_period"] = 1; d["debt_fraction"] = 0          # igual que en la interfaz (guía, Financial Parameters)
    r = ssc.run(d, modules=ssc.FUELCELL_COMMERCIAL, outputs=diseno.SALIDAS + [
        "annual_energy", "average_battery_roundtrip_efficiency", "annual_fuel_usage"])
    s = {k: np.asarray(v[:8760], float) for k, v in r.items() if isinstance(v, list)}
    return p, r, s


def main():
    filas, mensual = [], []
    mes = np.repeat(np.arange(12), [m * 24 for m in MESES])
    for nombre, cambio in FINALISTAS.items():
        p, r, s = correr(cambio)
        dfc = s["grid_to_load"]; exc = s["system_to_grid"] + s["fuelcell_to_grid"] + s["batt_to_grid"]
        eff = np.where(s["fuelcell_electrical_efficiency"] > 0, s["fuelcell_electrical_efficiency"] / 100, np.nan)
        fila = dict(
            caso=nombre, pv_MWdc=p["pv_kwdc"] / 1000, sofc_MW=p["fc_kw"] / 1000, rampa_pct_h=p["fc_rampa_pct_h"],
            bat_MW=p["batt_kw"] / 1000, bat_MWh=p["batt_kwh"] / 1000, carga_desde_sofc=p.get("batt_carga_desde_fc", 0),
            firme_MW=(p["fc_kw"] + p["batt_kw"]) / 1000,
            cobertura_pct=round((1 - dfc.sum() / s["load"].sum()) * 100, 2), deficit_GWh=round(dfc.sum() / 1e6, 2),
            horas_deficit=int((dfc > 1).sum()), pct_horas_deficit=round((dfc > 1).mean() * 100, 1),
            deficit_max_MW=round(dfc.max() / 1000, 1), excedente_GWh=round(exc.sum() / 1e6, 1),
            H2_t=round(np.nansum(s["fuelcell_power"] / eff) / 33.33 / 1000), terreno_ha=round(terreno_ha(p["pv_kwdc"] / 1000, p["fc_kw"] / 1000, p["batt_kwh"] / 1000)),
            # Results > Summary de la interfaz
            annual_energy_kWh=round(r["annual_energy"]), batt_roundtrip_pct=round(r["average_battery_roundtrip_efficiency"], 1),
            annual_fuel_usage_kWht=round(r["annual_fuel_usage"]), nominal_bank_kWh=round(r["batt_computed_bank_capacity"]),
        )
        for k in SUMAS:                                        # sumas de las columnas del Anexo 1 (GWh; FV viene en W)
            fila[f"suma_{k}_GWh"] = round(s[k].sum() / (1e9 if k == "ac" else 1e6), 2)
        filas.append(fila)
        dm, hm = np.bincount(mes, dfc, 12) / 1e6, np.bincount(mes, dfc > 1, 12)
        for i in range(12):
            mensual.append(dict(caso=nombre, mes=i + 1, deficit_GWh=round(dm[i], 3), horas_deficit=int(hm[i])))
        print(fila)
    for nom, data in [("finalistas_brecha_SAM.csv", filas), ("finalistas_brecha_mensual_SAM.csv", mensual)]:
        with open(nom, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0])); w.writeheader(); w.writerows(data)


if __name__ == "__main__":
    main()
