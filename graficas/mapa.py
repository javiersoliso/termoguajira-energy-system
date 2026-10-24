"""Mapa de la Infografía 1: Colombia, La Guajira (demanda), subárea GCM y Termoguajira 2.

Fuentes: límites departamentales — Colombia.geo.json (gist público john-guerra, basado en DANE);
coordenadas de Termoguajira — Global Energy Monitor (11.262213, -73.415568, WGS 84);
punto del clima — NSRDB TMY Location ID 1254249 (11.17, -73.70).
"""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle, ConnectionPatch

AQUI = Path(__file__).parent
C = dict(guajira="#2a78d6", gcm="#b7d3f6", resto="#e8e7e1", borde="#ffffff", tinta="#0b0b0b", tinta2="#52514e",
         muted="#898781", central="#0b0b0b", clima="#eda100")
plt.rcParams.update({"font.family": "Segoe UI", "font.size": 8, "svg.fonttype": "none", "savefig.dpi": 300})

TGJ2 = (-73.415568, 11.262213)          # (lon, lat)
TMY = (-73.70, 11.17)
CIUDADES = {"Riohacha": (-72.907, 11.544), "Maicao": (-72.240, 11.378), "Uribia": (-72.266, 11.714),
            "Santa Marta": (-74.199, 11.241), "Valledupar": (-73.253, 10.463)}


def poligonos(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    return geom["coordinates"]


def dibujar(ax, feats, destacar=True, lw=0.4):
    for f in feats:
        nom = f["properties"]["NOMBRE_DPT"]
        if nom.startswith("ARCHIPIELAGO"):
            continue
        color = C["resto"]
        if destacar and nom == "LA GUAJIRA":
            color = C["guajira"]
        elif destacar and nom in ("CESAR", "MAGDALENA"):
            color = C["gcm"]
        for poly in poligonos(f["geometry"]):
            ext = np.array(poly[0])
            ax.add_patch(Polygon(ext, closed=True, fc=color, ec=C["borde"], lw=lw))


def centroide(f):
    pts = np.vstack([np.array(p[0]) for p in poligonos(f["geometry"])])
    return pts[:, 0].mean(), pts[:, 1].mean()


def main():
    g = json.loads((AQUI / "mapa" / "Colombia.geo.json").read_text(encoding="utf-8"))
    feats = g["features"]
    fig = plt.figure(figsize=(9.0, 6.0))
    # --- izquierda: Colombia
    ax = fig.add_axes([0.0, 0.0, 0.46, 1.0])
    dibujar(ax, feats)
    ax.set_xlim(-79.3, -66.6); ax.set_ylim(-4.4, 12.7)
    ax.set_aspect(1 / np.cos(np.radians(4)))
    ax.axis("off")
    ax.plot(*TGJ2, "o", ms=6, color=C["central"], mec="white", mew=1.4, zorder=5)
    ax.text(-74.0, 9.85, "Magdalena", fontsize=6.5, color=C["tinta2"], ha="right")
    ax.text(-73.35, 8.75, "Cesar", fontsize=6.5, color=C["tinta2"], ha="left")
    ax.text(-72.2, 3.2, "Colombia", fontsize=10, color=C["muted"], ha="center", fontweight="semibold")
    x0, x1, y0_, y1 = -74.45, -71.05, 10.25, 12.55
    ax.add_patch(Rectangle((x0, y0_), x1 - x0, y1 - y0_, fc="none", ec=C["tinta2"], lw=0.7))
    km = 200; grados = km / 111.32
    ax.plot([-78.8, -78.8 + grados], [-3.6, -3.6], color=C["tinta2"], lw=1.4)
    ax.text(-78.8 + grados / 2, -3.3, f"{km} km", ha="center", fontsize=7, color=C["tinta2"])
    ax.annotate("", xy=(-67.6, -2.3), xytext=(-67.6, -3.6), arrowprops=dict(arrowstyle="-|>", color=C["tinta2"], lw=1))
    ax.text(-67.6, -2.1, "N", ha="center", fontsize=8, color=C["tinta2"], fontweight="semibold")

    # --- derecha arriba: ampliación de La Guajira
    axi = fig.add_axes([0.49, 0.30, 0.51, 0.68])
    dibujar(axi, feats, lw=0.8)
    axi.set_xlim(x0, x1); axi.set_ylim(y0_, y1); axi.set_aspect(1 / np.cos(np.radians(11.3)))
    axi.set_xticks([]); axi.set_yticks([])
    for sp in axi.spines.values():
        sp.set_color(C["tinta2"]); sp.set_linewidth(0.7)
    axi.set_facecolor("#f4f8fd")
    for nom, (x, y) in CIUDADES.items():
        axi.plot(x, y, "o", ms=2.5, color=C["tinta2"], zorder=4)
        izq = nom in ("Maicao",)
        axi.text(x + (-0.05 if izq else 0.05), y + 0.05, nom, fontsize=7, zorder=4, ha="right" if izq else "left",
                 color="white" if nom in ("Riohacha", "Uribia", "Maicao") else C["tinta2"])
    axi.plot(*TMY, "P", ms=6, color=C["clima"], mec="white", mew=0.8, zorder=5)
    axi.annotate("punto del clima TMY (NSRDB)\n11,17 N · 73,70 O", TMY, xytext=(TMY[0] - 0.55, TMY[1] - 0.45),
                 fontsize=6.5, color=C["tinta2"], ha="center", va="top",
                 arrowprops=dict(arrowstyle="-", color=C["tinta2"], lw=0.6))
    axi.plot(*TGJ2, "o", ms=8, color=C["central"], mec="white", mew=1.5, zorder=6)
    axi.annotate("Termoguajira 2 · 130 MW\nMingueo, Dibulla · S/E 220 kV\n11,26 N · 73,42 O", TGJ2,
                 xytext=(TGJ2[0] - 0.35, TGJ2[1] + 0.85), fontsize=7, color=C["tinta"], va="bottom", ha="center",
                 arrowprops=dict(arrowstyle="-", color=C["tinta2"], lw=0.6),
                 bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none", alpha=0.92))
    axi.text(-71.62, 12.02, "LA GUAJIRA", fontsize=8.5, color="white", ha="center", fontweight="semibold")
    axi.text(-72.6, 12.45, "Mar Caribe", fontsize=7, color=C["muted"], ha="left", va="top", style="italic")
    for (xa, ya), (xb, yb) in (((x1, y1), (0, 1)), ((x1, y0_), (0, 0))):
        fig.add_artist(ConnectionPatch((xa, ya), (xb, yb), coordsA="data", coordsB="axes fraction", axesA=ax,
                                       axesB=axi, color=C["muted"], lw=0.5))

    # --- derecha abajo: leyenda
    axl = fig.add_axes([0.50, 0.02, 0.50, 0.24]); axl.axis("off"); axl.set_xlim(0, 1); axl.set_ylim(0, 1)
    filas = [("rect", C["guajira"], "La Guajira: área de demanda del SEI (1.028 GWh/año, 2024)"),
             ("rect", C["gcm"], "Subárea eléctrica Guajira–Cesar–Magdalena (XM)"),
             ("punto", C["central"], "Termoguajira 2: central a reemplazar y sitio del SEI"),
             ("cruz", C["clima"], "Recurso solar: año meteorológico típico NSRDB")]
    for i, (tipo, col, txt) in enumerate(filas):
        y = 0.86 - i * 0.24
        if tipo == "rect":
            axl.add_patch(Rectangle((0.02, y - 0.07), 0.045, 0.14, fc=col, ec="none"))
        elif tipo == "punto":
            axl.plot(0.0425, y, "o", ms=7, color=col, mec="white", mew=1.4)
        else:
            axl.plot(0.0425, y, "P", ms=7, color=col, mec="white", mew=0.8)
        axl.text(0.09, y, txt, fontsize=8, va="center", color=C["tinta"])
    fig.text(0.50, -0.01, "Límites: DANE (GeoJSON público). Coordenadas de la central: Global Energy Monitor.",
             fontsize=6, color=C["muted"])
    for ext in ("png", "svg"):
        fig.savefig(AQUI / f"Info1_Mapa_Colombia.{ext}", bbox_inches="tight", pad_inches=0.05, transparent=True)
    print("Info1_Mapa_Colombia")


if __name__ == "__main__":
    main()
