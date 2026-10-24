"""Gráficas del SEI (FC + PV + BESS) para las infografías, a partir de la exportación horaria de SAM.

Uso:  python graficas.py [ruta_csv_SAM]      (por defecto: resultados de referencia)
Salida: PNG (300 dpi) + SVG en esta carpeta.
Paleta: SOFC azul, FV amarillo, batería violeta, déficit rojo.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path as MPath

AQUI = Path(__file__).parent
RAIZ = AQUI.parent
CSV = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "sam" / "resultados_referencia" / "serie_horaria_referencia.csv"

# ---------------------------------------------------------------- estilo
C = dict(fc="#2a78d6", pv="#eda100", bat="#4a3aa7", defi="#e34948", calor="#eb6834", cub="#1baf7a",
         exp="#898781", perd="#c3c2b7", tinta="#0b0b0b", tinta2="#52514e", muted="#898781",
         grid="#e1e0d9", eje="#c3c2b7", fondo="#fcfcfb")
plt.rcParams.update({
    "font.family": "Segoe UI", "font.size": 9, "axes.edgecolor": C["eje"], "axes.linewidth": 0.8,
    "axes.labelcolor": C["tinta2"], "xtick.color": C["muted"], "ytick.color": C["muted"],
    "xtick.labelsize": 8, "ytick.labelsize": 8, "axes.titlesize": 11, "axes.titleweight": "semibold",
    "axes.titlecolor": C["tinta"], "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": C["grid"], "grid.linewidth": 0.6, "axes.axisbelow": True,
    "legend.frameon": False, "legend.fontsize": 8, "figure.facecolor": "white", "axes.facecolor": "white",
    "svg.fonttype": "none", "savefig.dpi": 300,
})
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]


def fecha_es(f):
    """28-ago (abreviatura del mes en español)."""
    return f"{f.day:02d}-{MESES[f.month - 1][:3]}"


def guardar(fig, nombre):
    for ext in ("png", "svg"):
        fig.savefig(AQUI / f"{nombre}.{ext}", bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print("  ", nombre)


# ---------------------------------------------------------------- datos
def cargar(csv=CSV):
    d = pd.read_csv(csv)
    col = lambda patron: next(c for c in d.columns if c.startswith(patron))
    opc = lambda patron: d[col(patron)] if any(c.startswith(patron) for c in d.columns) else 0.0
    f = pd.date_range("2024-01-01", periods=8784, freq="h")
    f = f[~((f.month == 2) & (f.day == 29))]
    kw = 1 / 1000.0                                    # kW -> MW
    df = pd.DataFrame(index=f)
    if any(c.startswith("Electricity load (year 1)") for c in d.columns):
        df["dem"] = d[col("Electricity load (year 1)")].values * kw
    else:   # la carga es la suma de lo que llega a ella: FV + SOFC + batería + red
        df["dem"] = (d[col("Electricity to load from system AC")] + d[col("Electricity to load from fuel cell")]
                     + d[col("Electricity to load from battery AC")] + d[col("Electricity to load from grid AC")]).values * kw
    df["pv"] = d[col("AC inverter output power")].values / 1e6
    df["fc"] = d[col("Electricity from fuel cell")].values * kw
    df["gen"] = d[col("Power produced without the battery")].values * kw
    df["carga"] = (d[col("Electricity to battery from system AC")] + opc("Electricity to battery from fuel cell AC")
                   + opc("Electricity to battery from grid AC")).values * kw
    df["desc"] = (d[col("Electricity to load from battery AC")] + opc("Electricity to grid from battery AC")).values * kw
    df["soc"] = d[col("Battery state of charge")].values
    df["pv2d"] = d[col("Electricity to load from system AC")].values * kw
    df["fc2d"] = d[col("Electricity to load from fuel cell")].values * kw
    df["b2d"] = d[col("Electricity to load from battery AC")].values * kw
    df["defi"] = np.maximum(0, df.dem - df.gen - df.desc)
    df["exc"] = np.maximum(0, df.gen - df.dem - df.carga)
    df["ghi"] = d[col("Weather file global horizontal irradiance")].values
    return df


# ---------------------------------------------------------------- series de tiempo (mes / semana)
CAJA = dict(boxstyle="round,pad=0.25", fc="white", ec="none", alpha=0.9)
FLECHA = dict(arrowstyle="-", color=C["tinta2"], lw=0.6, shrinkA=0, shrinkB=2)


def _panel_potencia(ax, s, x):
    capas = [(s.fc2d, C["fc"], "SOFC (H₂)"), (s.pv2d, C["pv"], "FV"), (s.b2d, C["bat"], "Batería"),
             (s.defi, C["defi"], "Déficit (SIN)")]
    base = np.zeros(len(s))
    for v, color, lab in capas:
        ax.fill_between(x, base, base + v.values, color=color, alpha=0.82, lw=0, label=lab)
        base = base + v.values
    arriba = s.dem.values
    ax.fill_between(x, arriba, arriba + s.carga.values + s.exc.values, color=C["exp"], alpha=0.22, lw=0,
                    label="Excedente (carga batería + exportación)")
    ax.plot(x, s.dem.values, color=C["tinta"], lw=1.1, label="Demanda")
    ax.axhline(130, color=C["tinta2"], lw=0.7, alpha=0.6)
    ax.text(x[0] + 0.1, 131.5, "130 MW firmes (SOFC 110 + batería 20)", ha="left", va="bottom", fontsize=7,
            color=C["tinta2"], bbox=CAJA)
    ax.set_ylabel("Potencia (MW)")
    ax.set_ylim(0, max(270, float((s.dem + s.carga + s.exc).max()) * 1.08))


def _elegir(v, desde=0.08, hasta=0.92, modo="max"):
    """Índice del máximo/mínimo lejos de los bordes (para que la anotación no se salga)."""
    n = len(v); a, b = int(n * desde), int(n * hasta)
    sub = v[a:b]
    return a + int(np.argmax(sub) if modo == "max" else np.argmin(sub))


def _anotaciones(ax, s, x):
    span = x[-1] - x[0]
    exc = (s.carga + s.exc).values
    i_e = _elegir(exc, 0.62, 0.95)
    ax.annotate("Excedente al mediodía: FV + mínimo SOFC > demanda\n→ carga la batería y exporta al SIN",
                (x[i_e], s.dem.values[i_e] + exc[i_e] * 0.5), xytext=(x[i_e] - span * 0.03, 250),
                fontsize=7.5, color=C["tinta"], ha="right", va="center", bbox=CAJA, arrowprops=FLECHA)
    d = s.defi.values
    if d.max() > 0:
        i_d = _elegir(d, 0.30, 0.60)
        ax.annotate("Déficit nocturno: batería vacía y\ndemanda > 110 MW de la SOFC",
                    (x[i_d], s.dem.values[i_d] - d[i_d] / 2), xytext=(x[i_d], 205), fontsize=7.5,
                    color=C["tinta"], ha="center", va="center", bbox=CAJA, arrowprops=FLECHA)
    b = s.b2d.values
    i_b = _elegir(b, 0.05, 0.28)
    ax.annotate("La batería cubre la subida\nde la demanda al atardecer",
                (x[i_b], s.fc2d.values[i_b] + s.pv2d.values[i_b] + b[i_b] / 2), xytext=(x[i_b] + span * 0.02, 175),
                fontsize=7.5, color=C["tinta"], ha="left", va="center", bbox=CAJA, arrowprops=FLECHA)


def _panel_soc(ax, s, x):
    span = x[-1] - x[0]
    ax.plot(x, s.soc.values, color=C["bat"], lw=1.3)
    tr = ax.get_yaxis_transform()
    for y, t in ((95, "máx. 95 %"), (15, "mín. 15 %")):
        ax.axhline(y, color=C["eje"], lw=0.8)
        ax.text(1.005, y, t, transform=tr, fontsize=7, color=C["muted"], va="center", ha="left")
    ax.set_ylim(0, 108); ax.set_yticks([0, 50, 100])
    ax.set_ylabel("SoC (%)")
    v = s.soc.values
    i_max = _elegir(v, 0.10, 0.45, "max"); i_min = _elegir(v, 0.55, 0.90, "min")
    if v.max() >= 94:
        i_max = int(np.argmax(v >= 94)) if v[i_max] < 94 else i_max
        t_max = "carga completa (95 %)"
    else:
        i_max = int(np.argmax(v)); t_max = f"máximo del periodo: {v.max():.0f} % (no llega a llenarse)"
    ax.annotate(t_max, (x[i_max], v[i_max]), xytext=(x[i_max] + span * 0.03, 72 if v[i_max] < 60 else 60),
                fontsize=7, color=C["tinta2"], ha="left", va="center", bbox=CAJA, arrowprops=FLECHA)
    if v.min() <= 16:
        ax.annotate("descarga profunda (15 %)", (x[i_min], v[i_min]), xytext=(x[i_min] + span * 0.03, 45),
                    fontsize=7, color=C["tinta2"], ha="left", va="center", bbox=CAJA, arrowprops=FLECHA)


def grafico_periodo(df, ini, fin, titulo, nombre, ghi_diaria=True):
    s = df.loc[ini:fin]
    x = (s.index - pd.Timestamp(ini)).total_seconds().values / 86400 + 1      # día (fraccional) desde 1
    alturas = [1, 3.6, 1.4] if ghi_diaria else [3.6, 1.4]
    fig, axs = plt.subplots(len(alturas), 1, figsize=(10, 6.6), sharex=True,
                            gridspec_kw=dict(height_ratios=alturas, hspace=0.14))
    k = 0
    if ghi_diaria:
        ax = axs[0]
        g = s.ghi.groupby(s.index.date).sum() / 1000
        xd = np.arange(1, len(g) + 1) + 0.5
        ax.bar(xd, g.values, width=0.5 if len(g) > 10 else 0.22, color=C["pv"], lw=0)
        ax.set_ylabel("GHI\n(kWh/m²·d)"); ax.set_ylim(0, 8); ax.set_yticks([0, 4, 8])
        ax.text(1.005, 0.5, f"media\n{g.mean():.2f}".replace(".", ","), transform=ax.transAxes, ha="left",
                va="center", fontsize=7, color=C["tinta2"])
        k = 1
    _panel_potencia(axs[k], s, x)
    _anotaciones(axs[k], s, x)
    _panel_soc(axs[k + 1], s, x)
    dias = len(s) // 24
    axs[-1].set_xlim(1, 1 + dias)
    if dias <= 8:
        fechas = pd.date_range(ini, periods=dias, freq="D")
        axs[-1].set_xticks(np.arange(1, dias + 1) + 0.5)
        axs[-1].set_xticklabels([fecha_es(f) for f in fechas])
        axs[-1].set_xlabel("")
    else:
        axs[-1].set_xticks(range(1, dias + 1, 5))
        axs[-1].set_xlabel("Día del mes")
    fig.suptitle(titulo, x=0.075, y=0.995, ha="left", fontsize=12, fontweight="semibold", color=C["tinta"])
    h, l = axs[k].get_legend_handles_labels()
    fig.legend(h, l, loc="upper left", bbox_to_anchor=(0.068, 0.962), ncol=6, handlelength=1.3, columnspacing=1.2,
               fontsize=8)
    fig.subplots_adjust(top=0.90)
    guardar(fig, nombre)


def indicadores_periodo(df, ini, fin, cap_kwh=160000):
    s = df.loc[ini:fin]
    return dict(dem_MWh=s.dem.sum(), pv_MWh=s.pv.sum(), deficit_MWh=s.defi.sum(), horas_deficit=int((s.defi > 0.001).sum()),
                deficit_max_MW=s.defi.max(), excedente_MWh=s.exc.sum(), ciclos=s.desc.sum() * 1000 / cap_kwh,
                cobertura=1 - s.defi.sum() / s.dem.sum(), ghi_dia=s.ghi.sum() / 1000 / (len(s) / 24))


# ---------------------------------------------------------------- sankey
def sankey(nodos, flujos, nombre, titulo, unidad="GWh", arriba=(), extra=None):
    """nodos: {id: (columna, orden, etiqueta, color)}; flujos: [(origen, destino, valor)] en MWh.
    arriba: columnas cuyos nodos se alinean arriba (en vez de centrados)."""
    extra = extra or {}
    ent = {n: 0.0 for n in nodos}; sal = {n: 0.0 for n in nodos}
    for o, dd, v in flujos:
        sal[o] += v; ent[dd] += v
    tam = {n: max(ent[n], sal[n]) for n in nodos}
    cols = sorted({c for c, *_ in nodos.values()})
    hueco = 0.03
    total = max(sum(tam[n] for n in nodos if nodos[n][0] == c) for c in cols)
    nmax = max(sum(1 for n in nodos if nodos[n][0] == c) for c in cols)
    esc = (0.90 - hueco * (nmax - 1)) / total
    pos = {}
    for c in cols:
        lista = sorted([n for n in nodos if nodos[n][0] == c], key=lambda n: nodos[n][1])
        alto = sum(tam[n] for n in lista) * esc + hueco * (len(lista) - 1)
        y = 0.95 if c in arriba else 0.5 + alto / 2
        for n in lista:
            h = max(tam[n] * esc, 0.004)
            pos[n] = (c, y - h, y)
            y -= h + hueco
    fig, ax = plt.subplots(figsize=(12, 6.6))
    ax.set_xlim(-0.03, len(cols) - 1 + 0.75); ax.set_ylim(0, 1); ax.axis("off")
    ancho = 0.03
    xcol = {c: i for i, c in enumerate(cols)}
    # orden de apilado: en cada nodo, los flujos se ordenan por la altura del nodo del otro extremo
    # (el de arriba primero), así las cintas no se cruzan innecesariamente
    yc = {n: (pos[n][1] + pos[n][2]) / 2 for n in nodos}
    y_sal, y_ent = {}, {}
    for n in nodos:
        acc = pos[n][2]
        for o, dd, v in sorted([f for f in flujos if f[0] == n], key=lambda f: -yc[f[1]]):
            y_sal[(o, dd)] = acc; acc -= v * esc
        acc = pos[n][2]
        for o, dd, v in sorted([f for f in flujos if f[1] == n], key=lambda f: -yc[f[0]]):
            y_ent[(o, dd)] = acc; acc -= v * esc
    for o, dd, v in flujos:
        h = v * esc
        y0a = y_sal[(o, dd)]; y0b = y0a - h
        y1a = y_ent[(o, dd)]; y1b = y1a - h
        x0 = xcol[nodos[o][0]] + ancho; x1 = xcol[nodos[dd][0]]
        xm = (x0 + x1) / 2
        verts = [(x0, y0a), (xm, y0a), (xm, y1a), (x1, y1a), (x1, y1b), (xm, y1b), (xm, y0b), (x0, y0b), (x0, y0a)]
        codes = [MPath.MOVETO, MPath.CURVE4, MPath.CURVE4, MPath.CURVE4, MPath.LINETO, MPath.CURVE4, MPath.CURVE4,
                 MPath.CURVE4, MPath.CLOSEPOLY]
        ax.add_patch(PathPatch(MPath(verts, codes), fc=nodos[o][3], ec="none", alpha=0.30))
    for n, (c, b, t) in pos.items():
        x = xcol[c]
        ax.add_patch(Rectangle((x, b), ancho, t - b, fc=nodos[n][3], ec="none"))
        txt = f"{nodos[n][2]}\n{tam[n] / 1000:,.0f} {unidad}".replace(",", ".") + extra.get(n, "")
        ax.text(x + ancho + 0.012, (b + t) / 2, txt, va="center", ha="left", fontsize=8, color=C["tinta"],
                linespacing=1.15)
    ax.set_title(titulo, loc="left", fontsize=12)
    guardar(fig, nombre)


# ---------------------------------------------------------------- sparklines
def sparkline(serie, color, nombre, etiqueta, unidad, fmt="{:.0f}"):
    fig, ax = plt.subplots(figsize=(3.2, 0.8))
    x = np.arange(len(serie))
    ax.plot(x, serie.values, color=color, lw=1.1, zorder=2)
    ax.fill_between(x, serie.min() * 0.98, serie.values, color=color, alpha=0.10, lw=0, zorder=1)
    for i in (int(np.argmax(serie.values)), int(np.argmin(serie.values))):
        ax.plot(x[i], serie.values[i], "o", ms=5, color=color, mec="white", mew=1.4, zorder=3)
    ax.axis("off")
    ax.set_title(f"{etiqueta}  ·  mín {fmt.format(serie.min())} – máx {fmt.format(serie.max())} {unidad}",
                 loc="left", fontsize=7.5, color=C["tinta2"], fontweight="normal", pad=2)
    guardar(fig, nombre)


# ---------------------------------------------------------------- principal
def main():
    df = cargar()
    print("Datos:", CSV.name, f"| demanda {df.dem.sum():,.0f} MWh | cobertura {1 - df.defi.sum() / df.dem.sum():.2%}")

    # Infografía 2: mes bueno (marzo) y mes malo (noviembre)
    grafico_periodo(df, "2024-03-01", "2024-03-31 23:00", "Marzo (mes de buena generación): demanda vs. suministro y estado de carga",
                    "Info2_Mes_Bueno_Marzo")
    grafico_periodo(df, "2024-11-01", "2024-11-30 23:00", "Noviembre (mes de mala generación): demanda vs. suministro y estado de carga",
                    "Info2_Mes_Malo_Noviembre")

    # Infografía 4: semanas representativas (versión propia; la guía pide también las exportadas de SAM)
    for tag, ini in (("Buena", "2024-08-28"), ("Mala", "2024-12-11")):
        fin = str((pd.Timestamp(ini) + pd.Timedelta(days=6, hours=23)))
        grafico_periodo(df, ini, fin, f"Semana de {'buena' if tag == 'Buena' else 'mala'} generación "
                        f"({fecha_es(pd.Timestamp(ini))} a {fecha_es(pd.Timestamp(fin))}): demanda vs. suministro y estado de carga",
                        f"Info4_Semana_{tag}", ghi_diaria=True)
        print("     ", tag, {k: round(v, 3) for k, v in indicadores_periodo(df, ini, fin).items()})

    # Infografía 3: Sankey anual (MWh) y sparklines (promedios diarios)
    area = 300000 / 0.19
    e = lambda v: float(v)
    ghi = pd.read_csv(CSV)
    poa = ghi[[c for c in ghi.columns if c.startswith("Plane of array irradiance")][0]].sum() * area / 1e6
    fc = df.fc.sum()
    eff = pd.read_csv(CSV)[[c for c in ghi.columns if c.startswith("Fuel cell electrical efficiency")][0]].values
    h2 = np.nansum(np.where(eff > 0, df.fc.values / (eff / 100), 0))
    calor = pd.read_csv(CSV)[[c for c in ghi.columns if c.startswith("Heat from fuel cell")][0]].sum() / 1000
    pv2x = df.pv.sum() - df.pv2d.sum() - df.carga.sum()
    fc2x = fc - df.fc2d.sum()
    nodos = {
        "sol": (0, 0, "Radiación solar\nsobre módulos", C["pv"]), "h2": (0, 1, "Hidrógeno (PCI)", C["fc"]),
        "fv": (1, 0, "Generación FV", C["pv"]), "pfv": (1, 1, "Pérdidas FV", C["perd"]),
        "sofc": (1, 2, "Electricidad SOFC", C["fc"]), "calor": (1, 3, "Calor recuperable", C["calor"]),
        "psofc": (1, 4, "Pérdidas SOFC", C["perd"]),
        "bat": (2, 0, "Batería", C["bat"]),
        "pbat": (3, 0, "Pérdidas batería", C["perd"]), "cub": (3, 1, "Demanda cubierta", C["cub"]),
        "exp": (3, 2, "Excedente exportado", C["exp"]), "sin": (3, 3, "Déficit (SIN)", C["defi"]),
        "dem": (4, 0, "Demanda\nLa Guajira", C["tinta2"]),
    }
    flujos = [("sol", "fv", df.pv.sum()), ("sol", "pfv", poa - df.pv.sum()),
              ("h2", "sofc", fc), ("h2", "calor", calor), ("h2", "psofc", h2 - fc - calor),
              ("fv", "cub", df.pv2d.sum()), ("fv", "bat", df.carga.sum()), ("fv", "exp", pv2x),
              ("sofc", "cub", df.fc2d.sum()), ("sofc", "exp", fc2x),
              ("bat", "cub", df.b2d.sum()), ("bat", "pbat", df.carga.sum() - df.b2d.sum()),
              ("cub", "dem", df.pv2d.sum() + df.fc2d.sum() + df.b2d.sum()), ("sin", "dem", df.defi.sum())]
    dem = df.dem.sum()
    pct = lambda v: f" ({v / dem * 100:.1f} %)".replace(".", ",")
    sankey(nodos, flujos, "Info3_Sankey_anual", "Balance energético anual del SEI (GWh/año)", arriba=(2,),
           extra={"cub": pct(dem - df.defi.sum()), "sin": pct(df.defi.sum())})
    dia = df.groupby(df.index.date).mean()
    sparkline(dia.dem, C["tinta2"], "Info3_sparkline_demanda", "Demanda (media diaria)", "MW")
    sparkline(dia.gen, C["fc"], "Info3_sparkline_generacion", "Generación FV + SOFC (media diaria)", "MW")
    sparkline(dia.soc, C["bat"], "Info3_sparkline_soc", "SoC de la batería (media diaria)", "%")


if __name__ == "__main__":
    main()
