"""Baterías pequeñas (escala Colombia) con el motor de SAM (SSC 2026.7.3).

Pregunta: ¿cuál es la batería más pequeña con la que el SEI iguala a una TGJ2 de 130 MW
disponible el 100 % del tiempo (1.287 h con déficit en 2024) o a la TGJ2 real (5.863 h)?
Malla: SOFC 110/115/120 MW × batería 20–60 MW × 40–320 MWh × carga desde la SOFC (0/1).
FV 300 MWdc y lo demás igual al diseño entregado. Reusa correr() de barrido_fino_brecha.py.

Salida: barrido_bateria_pequena_SAM.csv
"""
import csv, itertools, os, time
from concurrent.futures import ProcessPoolExecutor
from barrido_fino_brecha import correr

SOFC = [110, 115, 120]
BAT_MW = [20, 30, 40, 50, 60]
BAT_MWH = [40, 80, 120, 160, 200, 240, 320]
CARGA_FC = [0, 1]

if __name__ == "__main__":
    casos = [(300, fc, 20, mw, mwh, c) for fc, mw, mwh, c in itertools.product(SOFC, BAT_MW, BAT_MWH, CARGA_FC)
             if mwh / mw >= 1]                                   # duración mínima 1 h
    t = time.time()
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as ex:
        filas = list(ex.map(correr, casos, chunksize=4))
    with open("barrido_bateria_pequena_SAM.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0])); w.writeheader(); w.writerows(filas)
    print(f"{len(filas)} casos en {time.time() - t:.0f} s")
