"""SOFC y batería con FV fija (300 MWdc) y batería cargada SOLO con el sol (motor de SAM, SSC 2026.7.3).

Criterios del grupo (04-oct): cobertura ≥ 95 % (déficit ≤ 5 % de la demanda anual), menos H₂ que el
diseño entregado y batería de menos de USD 100 M. La casilla "Battery can charge from fuel cell" queda
desmarcada en todos los casos. Malla: SOFC 60–110 MW × batería 20–80 MW × 80–800 MWh.
Reusa correr() de barrido_fino_brecha.py.

Salida: barrido_sofc_bateria_solar_SAM.csv
"""
import csv, itertools, os, time
from concurrent.futures import ProcessPoolExecutor
from barrido_fino_brecha import correr

SOFC = [60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110]
BAT_MW = [20, 30, 40, 50, 60, 80]
BAT_MWH = [80, 160, 240, 320, 400, 480, 640, 800]

if __name__ == "__main__":
    casos = [(300, fc, 20, mw, mwh, 0) for fc, mw, mwh in itertools.product(SOFC, BAT_MW, BAT_MWH) if mwh / mw >= 1]
    t = time.time()
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as ex:
        filas = list(ex.map(correr, casos, chunksize=4))
    with open("barrido_sofc_bateria_solar_SAM.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0])); w.writeheader(); w.writerows(filas)
    print(f"{len(filas)} casos en {time.time() - t:.0f} s")
