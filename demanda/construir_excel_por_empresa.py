"""Excel de una sola hoja: demanda horaria 2024 de La Guajira, empresa por empresa (8760 h, kW).

Misma metodología y mismas cifras que construir_perfil.py (el total por hora es idéntico a
perfil_horario_la_guajira_8760.csv), pero sin sumar las empresas: cada comercializador recibe su
energía mensual del SUI repartida con la forma horaria de XM (Air-e: regulado; resto: no regulado).
"""
import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter as L

AQUI = Path(__file__).parent
spec = importlib.util.spec_from_file_location("raw", AQUI / "sui_raw_2024.py")
raw = importlib.util.module_from_spec(spec); spec.loader.exec_module(raw)

SECT = ["residencial", "industrial", "comercial", "oficial", "otros"]
IDX = {"residencial": 6, "industrial": 7, "comercial": 8, "oficial": 9, "otros": 10}
NORMALES = [1, 2, 3, 4, 5, 6, 7, 8, 11]
FALTANTES = [9, 10]

# ---- energía mensual (kWh) por empresa
filas = []
for mm, lines in raw.RAW.items():
    for l in lines:
        p = l.split(","); v = list(map(int, p[-12:]))
        filas.append({"mes": int(mm), "empresa": ",".join(p[1:-13]), "E": sum(v[IDX[s]] for s in SECT)})
sui = pd.DataFrame(filas)
sui["empresa"] = sui.empresa.str.replace("�", "Ú")           # "PÚBLICAS" mal codificado en la fuente
E = sui.pivot_table(index="mes", columns="empresa", values="E", aggfunc="sum").reindex(range(1, 13)).fillna(0.0)

AIRE = "AIR-E S.A.S. E.S.P."
GEC = "GENERADORA Y COMERCIALIZADORA DE ENERGIA DEL CARIBE S.A E.S.P"
xm = pd.read_csv(AQUI / "xm_demacome_caribe_sol_2024_horario_kWh.csv", parse_dates=["fecha"])
xm["mes"] = xm.fecha.dt.month
xm_mes = xm.groupby("mes")[["regulado_kWh", "no_regulado_kWh"]].sum()

# Air-e sep/oct sin reporte: r_prom x demanda regulada XM
r = E[AIRE] / xm_mes.regulado_kWh
r_prom = r.loc[NORMALES].mean()
for m in FALTANTES:
    E.loc[m, AIRE] = r_prom * xm_mes.loc[m, "regulado_kWh"]
# Gecelca facturó en dic el consumo de ene: se reparte (ene+dic)/2
media = (E.loc[1, GEC] + E.loc[12, GEC]) / 2
E.loc[[1, 12], GEC] = media

# ---- potencia horaria (kW) por empresa
f_reg = xm.regulado_kWh / xm.mes.map(xm_mes.regulado_kWh)
f_nor = xm.no_regulado_kWh / xm.mes.map(xm_mes.no_regulado_kWh)
P = pd.DataFrame(index=xm.index)
for emp in E.columns:
    if E[emp].sum() == 0:
        continue
    P[emp] = xm.mes.map(E[emp]) * (f_reg if emp == AIRE else f_nor)
keep = ~((xm.fecha.dt.month == 2) & (xm.fecha.dt.day == 29))          # SAM: años de 8760 h
P = P[keep].reset_index(drop=True); X = xm[keep].reset_index(drop=True)
assert len(P) == 8760

orden = P.sum().sort_values(ascending=False).index.tolist()
CORTO = {AIRE: "Air-e", GEC: "Gecelca (comercializadora)",
         "VATIA S.A.S. E.S.P.": "Vatia", "CELSIA COLOMBIA S.A. E.S.P.": "Celsia",
         "QI ENERGY SAS ESP": "QI Energy", "ENEL COLOMBIA S.A. E.S.P.": "Enel Colombia",
         "NEU ENERGY SAS ESP": "Neu Energy", "RUITOQUE S.A. E.S.P.": "Ruitoque",
         "CARIBEMAR DE LA COSTA S.A.S. E.S.P.": "Caribemar de la Costa",
         "EMPRESAS PÚBLICAS DE MEDELLIN E.S.P.": "EPM", "ENERTOTAL S.A. E.S.P.": "Enertotal",
         "BIA ENERGY S.A.S. E.S.P.": "Bia Energy", "Enel X Colombia S.A.S. ESP": "Enel X Colombia"}
for e in orden:
    if e.startswith("Transacciones"):
        CORTO[e] = "Transacciones Energéticas"
tipo = {e: ("Regulado" if e == AIRE else "No regulado") for e in orden}
nombres = [CORTO.get(e, e) for e in orden]

# ---- verificación contra el perfil oficial del proyecto
of = pd.read_csv(AQUI / "perfil_horario_la_guajira_8760.csv", encoding="utf-8-sig")
dif = np.abs(P[orden].sum(axis=1).values - of.P_demanda_kW.values).max()
print(f"empresas: {len(orden)} | max |suma - perfil oficial| = {dif:.4f} kW | total {P.values.sum()/1e6:,.1f} GWh")

# ================= Excel =================
wb = Workbook(); ws = wb.active; ws.title = "Demanda por empresa"
NAVY, CLARO, AMAR = "1F3A5F", "E8EEF6", "FFF4D6"
borde = Side(style="thin", color="C9D1DC")
n = len(orden); c0 = 4; cT = c0 + n                           # A hora, B fecha_hora, C mes, D.. empresas, luego total
r_h = 12; r0 = r_h + 1; r1 = r0 + 8759                         # encabezado fila 12, datos 13..8772

ws["A1"] = "Demanda eléctrica de La Guajira 2024 · empresa por empresa · 8760 horas"
ws["A1"].font = Font(name="Calibri", size=16, bold=True, color=NAVY)
ws["A2"] = "Potencia media horaria (kW) de cada comercializador que atiende usuarios en La Guajira. 1 kW durante una hora = 1 kWh."
ws["A2"].font = Font(size=10, color="555555")
notas = [
    "Energía mensual por empresa: SUI, «Consolidado de energía por empresa y departamento» 2024 (residencial + comercial + industrial + oficial + otros).",
    "Forma horaria: XM, demanda comercial del mercado CARIBE SOL 2024. Air-e usa la curva regulada; las demás empresas, la no regulada (mes a mes). No es medición por empresa: es su energía mensual repartida con la forma horaria de su tipo de usuario.",
    "Ajustes: Air-e no reportó sep/oct en el SUI (estimado = relación media Air-e/XM regulado × XM del mes); Gecelca facturó en dic el consumo de ene (se repartió ene+dic por igual). Los meses sin reporte de una empresa quedan en 0.",
    "Sin 29 de febrero (año de 8760 h, formato SAM). Diceler reportó 0 kWh y no aparece. La suma de las columnas = perfil total del proyecto (perfil_horario_la_guajira_8760.csv).",
]
for i, t in enumerate(notas):
    c = ws.cell(row=3 + i, column=1, value=t); c.font = Font(size=9, italic=True, color="555555")

# resumen por empresa (fórmulas sobre la tabla)
etiq = [(7, "Tipo"), (8, "Energía anual (GWh)"), (9, "Participación (%)"), (10, "Potencia media (MW)"), (11, "Pico (MW)")]
for r_, t in etiq:
    c = ws.cell(row=r_, column=3, value=t); c.font = Font(bold=True, size=10, color=NAVY); c.alignment = Alignment(horizontal="right")
tc = L(cT)
for j, e in enumerate(orden):
    col = L(c0 + j); rng = f"{col}{r0}:{col}{r1}"
    ws.cell(row=7, column=c0 + j, value=tipo[e])
    ws.cell(row=8, column=c0 + j, value=f"=SUM({rng})/1000000").number_format = "#,##0.000"
    ws.cell(row=9, column=c0 + j, value=f"={col}8/{tc}8").number_format = "0.00%"
    ws.cell(row=10, column=c0 + j, value=f"=AVERAGE({rng})/1000").number_format = "#,##0.000"
    ws.cell(row=11, column=c0 + j, value=f"=MAX({rng})/1000").number_format = "#,##0.000"
rngT = f"{tc}{r0}:{tc}{r1}"
ws.cell(row=7, column=cT, value="Total")
ws.cell(row=8, column=cT, value=f"=SUM({rngT})/1000000").number_format = "#,##0.000"
ws.cell(row=9, column=cT, value=f"=SUM({L(c0)}9:{L(cT-1)}9)").number_format = "0.00%"
ws.cell(row=10, column=cT, value=f"=AVERAGE({rngT})/1000").number_format = "#,##0.000"
ws.cell(row=11, column=cT, value=f"=MAX({rngT})/1000").number_format = "#,##0.000"
for r_ in range(7, 12):
    for cc in range(3, cT + 1):
        c = ws.cell(row=r_, column=cc); c.fill = PatternFill("solid", fgColor=CLARO if cc < cT else AMAR)
        c.font = Font(size=10, bold=(cc == cT or r_ == 8)); c.border = Border(bottom=borde)
        if cc > 3:
            c.alignment = Alignment(horizontal="center")

# encabezado de la tabla
head = ["Hora del año", "Fecha y hora", "Mes"] + [f"{x} (kW)" for x in nombres] + ["TOTAL La Guajira (kW)"]
for j, t in enumerate(head, 1):
    c = ws.cell(row=r_h, column=j, value=t)
    c.font = Font(bold=True, color="FFFFFF", size=10)
    c.fill = PatternFill("solid", fgColor=NAVY if j < len(head) else "B8860B")
    c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
ws.row_dimensions[r_h].height = 42

# datos
fh = (X.fecha + pd.to_timedelta(X.hora_inicio, unit="h")).dt.to_pydatetime()
vals = P[orden].round(3).values
for i in range(8760):
    r_ = r0 + i
    ws.cell(row=r_, column=1, value=i + 1)
    c = ws.cell(row=r_, column=2, value=fh[i]); c.number_format = "yyyy-mm-dd hh:mm"
    ws.cell(row=r_, column=3, value=int(X.mes[i]))
    for j in range(n):
        c = ws.cell(row=r_, column=c0 + j, value=float(vals[i, j])); c.number_format = "#,##0.000"
    c = ws.cell(row=r_, column=cT, value=f"=SUM({L(c0)}{r_}:{L(cT-1)}{r_})")
    c.number_format = "#,##0.000"; c.font = Font(bold=True); c.fill = PatternFill("solid", fgColor=AMAR)

ws.column_dimensions["A"].width = 12; ws.column_dimensions["B"].width = 18; ws.column_dimensions["C"].width = 22
for j in range(n):
    ws.column_dimensions[L(c0 + j)].width = 17
ws.column_dimensions[tc].width = 20
ws.freeze_panes = ws.cell(row=r0, column=c0)
ws.auto_filter.ref = f"A{r_h}:{tc}{r1}"
ws.sheet_view.zoomScale = 90
ws.sheet_properties.tabColor = NAVY
# ================= Hoja 2: aclaración del método =================
wm = wb.create_sheet("Método y aclaración")
wm.sheet_properties.tabColor = "B8860B"; wm.sheet_view.showGridLines = False
wm.column_dimensions["A"].width = 3
for col, w in zip("BCDE", (34, 44, 20, 62)):
    wm.column_dimensions[col].width = w
wrap = Alignment(wrap_text=True, vertical="top")

def titulo(r_, t):
    c = wm.cell(row=r_, column=2, value=t); c.font = Font(size=12, bold=True, color=NAVY)
    for cc in range(2, 6):
        wm.cell(row=r_, column=cc).border = Border(bottom=Side(style="medium", color=NAVY))

def parrafo(r_, t, alto):
    wm.merge_cells(start_row=r_, start_column=2, end_row=r_, end_column=5)
    c = wm.cell(row=r_, column=2, value=t); c.alignment = wrap; c.font = Font(size=10)
    wm.row_dimensions[r_].height = alto

wm["B1"] = "Aclaración del método · perfil horario por empresa"
wm["B1"].font = Font(size=16, bold=True, color=NAVY)
wm["B2"] = "Estos datos NO son mediciones hora por hora de cada empresa: son un perfil sintético (estimado)."
wm["B2"].font = Font(size=11, bold=True, color="A33A2A")

titulo(4, "1. Qué es dato real y qué es estimación")
for j, t in enumerate(["Dato", "Fuente", "¿Medido o estimado?", "Comentario"]):
    c = wm.cell(row=5, column=2 + j, value=t)
    c.font = Font(bold=True, color="FFFFFF", size=10); c.fill = PatternFill("solid", fgColor=NAVY)
    c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
tabla = [
    ("Energía mensual de cada empresa", "SUI, «Consolidado de energía por empresa y departamento», 2024", "Dato real (facturado)",
     "Es energía facturada por mes, no medida por hora; puede traer desfases de facturación (p. ej. Gecelca facturó en diciembre el consumo de enero)."),
    ("Forma horaria de la demanda", "XM, demanda comercial horaria, mercado CARIBE SOL 2024 (regulado y no regulado)", "Dato real (medido)",
     "Es medición hora a hora, pero de todo el mercado CARIBE SOL (zona de Air-e), no solo de La Guajira ni de cada empresa."),
    ("Potencia horaria de cada empresa", "Cálculo propio", "ESTIMADO",
     "Energía mensual de la empresa × fracción horaria de XM. La curva de cada empresa tiene la forma de la demanda regional, no la suya."),
    ("Air-e en septiembre y octubre", "Cálculo propio", "ESTIMADO",
     f"Air-e no reportó esos meses en el SUI. Se estimó con r × demanda regulada XM del mes, con r = {r_prom:.4f} (relación media Air-e/XM regulado en los meses normales)."),
    ("Gecelca en enero y diciembre", "Cálculo propio", "AJUSTADO",
     "Se repartió (enero + diciembre) por partes iguales, porque diciembre incluye el consumo de enero."),
    ("Meses sin reporte de una empresa", "SUI", "Sin dato",
     "Vatia, Celsia, QI Energy, Enel Colombia, Enertotal, Transacciones y otras no reportaron todos los meses; esos meses quedan en 0 (no se estimaron: son <1 % del total)."),
]
for i, fila in enumerate(tabla):
    r_ = 6 + i
    for j, t in enumerate(fila):
        c = wm.cell(row=r_, column=2 + j, value=t); c.alignment = wrap; c.font = Font(size=10, bold=(j == 2))
        c.border = Border(bottom=borde)
        if j == 2:
            c.fill = PatternFill("solid", fgColor="FBE3DE" if t in ("ESTIMADO", "Sin dato") else ("FFF4D6" if t == "AJUSTADO" else "E3F1E4"))
    wm.row_dimensions[r_].height = 58

titulo(13, "2. Cómo se construyó (paso a paso)")
pasos = [
    "1) Energía mensual de cada comercializador = residencial + comercial + industrial + oficial + otros (SUI, kWh/mes).",
    "2) Se completan Air-e (sep/oct) y Gecelca (ene/dic) como se indica arriba.",
    "3) Para cada hora: P_empresa (kW) = E_empresa,mes × (E_XM,hora / E_XM,mes). Air-e usa la curva regulada de XM; las demás empresas, la curva no regulada. Como 1 kWh en 1 h = 1 kW medio, la energía horaria es la potencia.",
    "4) Se elimina el 29 de febrero para tener 8760 h (formato de SAM). Se conserva la energía de cada mes salvo ese día.",
    "5) TOTAL La Guajira = suma de las columnas de empresas; coincide con el perfil horario del proyecto (diferencia máxima 0,0005 kW).",
]
for i, t in enumerate(pasos):
    parrafo(14 + i, t, 32 if len(t) > 120 else 20)

titulo(20, "3. Limitaciones")
lim = [
    "• Las energías mensuales y anuales por empresa son confiables (vienen del SUI). La forma del día y la hora del pico son aproximaciones.",
    "• Un usuario industrial grande (p. ej. Gecelca) probablemente tiene una curva más plana que la de XM; aquí se le asigna la curva no regulada de la región.",
    "• No sirve para afirmar cuánto consumió una empresa en una hora concreta. Esos datos solo los tienen las propias comercializadoras (p. ej. Air-e).",
    "• Sí sirve para dimensionar el sistema en SAM: el total mensual es consistente y la forma diaria es típica de la región.",
]
for i, t in enumerate(lim):
    parrafo(21 + i, t, 32 if len(t) > 120 else 20)

titulo(26, "4. Cómo citarlo")
parrafo(27, "«Perfil horario sintético de la demanda de La Guajira 2024, construido con la energía mensual por empresa del SUI y la curva horaria de XM "
            "del mercado CARIBE SOL (regulado para Air-e, no regulado para las demás empresas); sin medición horaria por empresa.»", 44)

out = AQUI / "Demanda_La_Guajira_2024_por_empresa_8760h.xlsx"
wb.save(out); print("OK", out)
