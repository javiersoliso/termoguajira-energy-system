"""Construye el perfil horario (8760 h) de demanda de La Guajira 2024 para SAM.

Entradas
  sui_raw_2024.py                              energía facturada por empresa y sector (SUI, kWh/mes)
  xm_demacome_caribe_sol_2024_horario_kWh.csv  demanda comercial horaria XM, mercado CARIBE SOL
                                               (regulado / no regulado), 8784 h

Método
  1. Energía mensual por sector = suma de todas las empresas (SUI).
  2. Air-e no reportó sep y oct 2024: se estiman como  r_prom x E_XM_reg(mes), donde r_prom es la
     relación promedio Air-e(La Guajira) / demanda regulada XM Caribe Sol en los meses normales.
     El reparto por sector usa la composición promedio de Air-e en esos mismos meses.
  3. Gecelca (industrial) facturó en diciembre el consumo de enero (hallazgo del 1er corte):
     se reparte (ene + dic) por partes iguales.
  4. Perfil horario: la energía de Air-e se distribuye con la forma horaria regulada de XM y la del
     resto de comercializadores con la forma no regulada, mes a mes.
  5. SAM usa años de 8760 h: se elimina el 29 de febrero (se conserva la potencia media de febrero).
"""
import csv, importlib.util
from pathlib import Path
import numpy as np
import pandas as pd

AQUI = Path(__file__).parent
spec = importlib.util.spec_from_file_location("raw", AQUI / "sui_raw_2024.py")
raw = importlib.util.module_from_spec(spec); spec.loader.exec_module(raw)

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
SECT = ["residencial", "industrial", "comercial", "oficial", "otros"]
IDX = {"residencial": 6, "industrial": 7, "comercial": 8, "oficial": 9, "otros": 10}
NORMALES = [1, 2, 3, 4, 5, 6, 7, 8, 11]          # meses con Air-e completo y sin anomalías
FALTANTES = [9, 10]                              # Air-e sin reporte

# ---------------------------------------------------------------- 1. SUI por empresa y sector
filas = []
for mm, lines in raw.RAW.items():
    for l in lines:
        p = l.split(",")
        v = list(map(int, p[-12:]))
        emp = ",".join(p[1:-13])
        filas.append({"mes": int(mm), "empresa": emp, **{s: v[IDX[s]] for s in SECT}})
sui = pd.DataFrame(filas)
sui["grupo"] = np.where(sui.empresa.str.startswith("AIR-E"), "Air-e (regulado)", "Otros comercializadores")
sui["total"] = sui[SECT].sum(axis=1)

por_grupo = sui.groupby(["grupo", "mes"])[SECT].sum()
aire = por_grupo.loc["Air-e (regulado)"].astype(float)
otros = por_grupo.loc["Otros comercializadores"].astype(float)

# ---------------------------------------------------------------- XM horario
xm = pd.read_csv(AQUI / "xm_demacome_caribe_sol_2024_horario_kWh.csv", parse_dates=["fecha"])
xm["mes"] = xm.fecha.dt.month
xm_mes = xm.groupby("mes")[["regulado_kWh", "no_regulado_kWh"]].sum()

# ---------------------------------------------------------------- 2. Air-e sep/oct
aire_tot = aire.sum(axis=1)
r = aire_tot / xm_mes["regulado_kWh"]
r_prom = r.loc[NORMALES].mean()
comp = (aire.loc[NORMALES].sum() / aire.loc[NORMALES].sum().sum())
aire_aj = aire.copy()
for m in FALTANTES:
    aire_aj.loc[m] = comp * r_prom * xm_mes.loc[m, "regulado_kWh"]

# ---------------------------------------------------------------- 3. Gecelca ene/dic
gec = sui[sui.empresa.str.startswith("GENERADORA Y COMERCIALIZADORA")].set_index("mes")["industrial"]
otros_aj = otros.copy()
media_gec = (gec.loc[1] + gec.loc[12]) / 2
otros_aj.loc[1, "industrial"] += media_gec - gec.loc[1]
otros_aj.loc[12, "industrial"] += media_gec - gec.loc[12]

bruto = aire + otros
ajust = aire_aj + otros_aj

# ---------------------------------------------------------------- 4. perfil horario (8784 h)
xm["E_aire"] = xm.mes.map(aire_aj.sum(axis=1))
xm["E_otros"] = xm.mes.map(otros_aj.sum(axis=1))
xm["f_reg"] = xm.regulado_kWh / xm.mes.map(xm_mes.regulado_kWh)
xm["f_noreg"] = xm.no_regulado_kWh / xm.mes.map(xm_mes.no_regulado_kWh)
xm["P_aire_kW"] = xm.E_aire * xm.f_reg            # kWh en 1 h = kW medio
xm["P_otros_kW"] = xm.E_otros * xm.f_noreg
xm["P_kW"] = xm.P_aire_kW + xm.P_otros_kW

# ---------------------------------------------------------------- 5. quitar 29-feb
sam = xm[~((xm.fecha.dt.month == 2) & (xm.fecha.dt.day == 29))].reset_index(drop=True)
assert len(sam) == 8760

# ---------------------------------------------------------------- salidas
out = AQUI
tabla = pd.DataFrame({"Mes": MESES})
for s in SECT:
    tabla[f"{s}_bruto_kWh"] = bruto[s].values
for s in SECT:
    tabla[f"{s}_ajustado_kWh"] = ajust[s].round().astype(int).values
tabla["total_bruto_kWh"] = bruto.sum(axis=1).values
tabla["total_ajustado_kWh"] = ajust.sum(axis=1).round().astype(int).values
tabla["aire_bruto_kWh"] = aire_tot.values
tabla["xm_caribe_sol_regulado_kWh"] = xm_mes.regulado_kWh.values
tabla["xm_caribe_sol_no_regulado_kWh"] = xm_mes.no_regulado_kWh.values
tabla["relacion_aire_xmreg"] = r.values
tabla["horas_2024"] = xm.groupby("mes").size().values
tabla["P_media_MW"] = tabla.total_ajustado_kWh / tabla.horas_2024 / 1000
tabla.to_csv(out / "demanda_mensual_la_guajira_2024.csv", index=False, encoding="utf-8-sig")

sam_out = pd.DataFrame({
    "fecha_hora": sam.fecha + pd.to_timedelta(sam.hora_inicio, unit="h"),
    "mes": sam.mes,
    "P_regulado_AirE_kW": sam.P_aire_kW.round(3),
    "P_otros_kW": sam.P_otros_kW.round(3),
    "P_demanda_kW": sam.P_kW.round(3),
})
sam_out.to_csv(out / "perfil_horario_la_guajira_8760.csv", index=False, encoding="utf-8-sig")
# archivo para importar en SAM (Electric Load > Edit array > Import): una columna; SAM ignora la 1a línea (encabezado)
np.savetxt(out / "carga_SAM_la_guajira_8760_kW.csv", sam.P_kW.values, fmt="%.3f", header="Electric load (kW)", comments="")

print(f"r_prom Air-e/XMreg = {r_prom:.4f}   (min {r.loc[NORMALES].min():.4f}, max {r.loc[NORMALES].max():.4f}, dic {r.loc[12]:.4f})")
print(tabla[["Mes", "total_bruto_kWh", "total_ajustado_kWh", "relacion_aire_xmreg", "P_media_MW"]].to_string(index=False))
print(f"Anual ajustado 2024: {tabla.total_ajustado_kWh.sum()/1e6:,.1f} GWh  | 8760 h SAM: {sam.P_kW.sum()/1e6:,.1f} GWh")
print(f"Perfil SAM: media {sam.P_kW.mean()/1e3:.1f} MW, pico {sam.P_kW.max()/1e3:.1f} MW "
      f"({sam_out.fecha_hora[sam.P_kW.idxmax()]}), mínimo {sam.P_kW.min()/1e3:.1f} MW")
print("Participación anual por sector (ajustado):",
      {s: f"{ajust[s].sum()/ajust.values.sum()*100:.1f}%" for s in SECT})
