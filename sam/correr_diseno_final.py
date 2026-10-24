"""Corre el diseño final del SEI con la cadena completa de SAM (Fuel Cell - Commercial) y guarda:
  - resultados_referencia/serie_horaria_referencia.csv : 8760 h con los nombres de variables de SAM
  - resultados_referencia/indicadores_referencia.json  : indicadores anuales (fórmulas de la guía)
  - para_SAM/ : archivos listos para cargar en la interfaz (carga 8760 y clima), sin tildes en el nombre
Sirve para comprobar que la configuración hecha a mano en SAM da los mismos resultados.
"""
import json, shutil
from pathlib import Path
import numpy as np
import pandas as pd
import diseno, ssc

AQUI = Path(__file__).parent
DISENO = dict(pv_kwdc=300_000, dc_ac=1.25, array_type=3, tilt=0, azimuth=180, gcr=0.3,
              fc_kw=110_000, fc_unidades=1, fc_min_pct=30, fc_rampa_pct_h=20, fc_despacho=1, fc_operacion=1,
              fc_degr_pct_anual=2.0, fc_arranque_h=24, fc_iniciada=1,
              batt_kw=20_000, batt_kwh=160_000, batt_despacho=5, batt_min_soc=15, batt_max_soc=95)

# Nombre SSC -> etiqueta que muestra SAM en Time Series (unidades SAM)
ETIQUETAS = {
    "load": "Electricity load (year 1) | (kW)",
    "gen": "System power generated | (kW)",
    "gen_without_battery": "Power produced without the battery or curtailment | (kW)",
    "ac": "AC inverter output power | (W)",
    "fuelcell_power": "Electricity from fuel cell | (kW)",
    "fuelcell_power_thermal": "Heat from fuel cell | (kWt)",
    "fuelcell_electrical_efficiency": "Fuel cell electrical efficiency | (%)",
    "system_to_batt": "Electricity to battery from system AC | (kW)",
    "fuelcell_to_batt": "Electricity to battery from fuel cell AC | (kW)",
    "grid_to_batt": "Electricity to battery from grid AC | (kW)",
    "batt_to_load": "Electricity to load from battery AC | (kW)",
    "batt_to_grid": "Electricity to grid from battery AC | (kW)",
    "batt_SOC": "Battery state of charge | (%)",
    "system_to_load": "Electricity to load from system AC | (kW)",
    "fuelcell_to_load": "Electricity to load from fuel cell | (kW)",
    "grid_to_load": "Electricity to load from grid AC | (kW)",
    "system_to_grid": "Electricity to grid from system AC | (kW)",
    "fuelcell_to_grid": "Electricity to grid from fuel cell | (kW)",
    "interconnection_loss": "Electricity loss due to curtailment interconnection outage | (kW)",
    "gh": "Weather file global horizontal irradiance | (W/m2)",
    "dn": "Weather file beam irradiance | (W/m2)",
    "poa": "Plane of array irradiance | (W/m2)",
    "tamb": "Weather file ambient temperature | (C)",
}


def main():
    d = diseno.entradas(vida_util=1, **DISENO)
    d["analysis_period"] = 1          # igual que en la interfaz: Financial Parameters > Analysis period = 1
    d["debt_fraction"] = 0
    r = ssc.run(d, modules=ssc.FUELCELL_COMMERCIAL, outputs=list(ETIQUETAS) + ["batt_computed_bank_capacity"])
    s = {k: np.asarray(v, float) for k, v in r.items() if isinstance(v, list)}
    s["pv_kw"] = s["ac"] / 1000
    ind = diseno.indicadores(s, DISENO)
    ind["batt_nominal_kWh_calculada"] = r["batt_computed_bank_capacity"]

    out = AQUI / "resultados_referencia"; out.mkdir(exist_ok=True)
    fechas = pd.date_range("2024-01-01", periods=8784, freq="h")
    fechas = fechas[~((fechas.month == 2) & (fechas.day == 29))]
    df = pd.DataFrame({"Time stamp": fechas.strftime("%b %d, %I:%M %p")})
    for k, lab in ETIQUETAS.items():
        df[lab] = s[k]
    df.to_csv(out / "serie_horaria_referencia.csv", index=False, encoding="utf-8-sig")
    with open(out / "indicadores_referencia.json", "w", encoding="utf-8") as f:
        json.dump({k: (float(v) if v is not None else None) for k, v in ind.items()} | {"diseno": DISENO}, f, indent=2, ensure_ascii=False)

    sam = AQUI / "para_SAM"; sam.mkdir(exist_ok=True)
    shutil.copy(AQUI.parent / "demanda" / "carga_SAM_la_guajira_8760_kW.csv", sam / "carga_SAM_la_guajira_8760_kW.csv")
    shutil.copy(AQUI.parent / "data" / "DIBULLA_1254249_11.17_-73.70_tmy-2025.csv", sam / "DIBULLA_1254249_11.17_-73.70_tmy-2025.csv")
    for k, v in ind.items():
        print(f"{k:28s} {v:,.3f}" if isinstance(v, (int, float)) else f"{k:28s} {v}")


if __name__ == "__main__":
    main()
