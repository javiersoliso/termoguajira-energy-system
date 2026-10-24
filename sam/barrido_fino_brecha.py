"""Barrido fino con el motor de SAM (SSC 2026.7.3) alrededor de las opciones B y D para cerrar el déficit.

Factorial completo: FV 300/350/400 MWdc × SOFC 110/115/120 MW × rampa 20/30/40 %/h ×
batería 40–90 MW × 320–800 MWh × carga desde la SOFC (0/1), más los casos ya validados
en validar_brecha.py (para comprobar que dan lo mismo). Lo demás es igual al diseño entregado.

Salida: barrido_fino_brecha_SAM.csv (una fila por caso). Corre en paralelo (1 proceso por núcleo).
"""
import csv, itertools, os, time
from concurrent.futures import ProcessPoolExecutor
import numpy as np

PV = [300, 350, 400]                       # MWdc
SOFC = [110, 115, 120]                     # MW
RAMPA = [20, 30, 40]                       # %/h de la potencia de la SOFC
BAT_MW = [40, 50, 60, 70, 80, 90]
BAT_MWH = [320, 400, 480, 560, 640, 720, 800]
CARGA_FC = [0, 1]
# casos de validar_brecha.py fuera de la malla (pv, sofc, rampa, bat_MW, bat_MWh, carga_fc)
EXTRA = [(300, 110, 20, 20, 160, 0), (300, 130, 20, 20, 160, 0), (300, 110, 40, 20, 160, 0)]


def terreno_ha(pv_mw, sofc_mw, bat_mwh):
    # mismas hipótesis que validar_brecha.py: módulos 19 % y GCR 0,3; SOFC 107 m²/MW; BESS 12,14 m²/MWh
    return pv_mw * 1000 / 0.19 / 0.3 / 1e4 + sofc_mw * 107 / 1e4 + bat_mwh * 12.14 / 1e4


def correr(caso):
    import diseno, ssc
    from correr_diseno_final import DISENO
    pv, fc, rampa, bmw, bmwh, cfc = caso
    p = {**DISENO, "pv_kwdc": pv * 1000, "fc_kw": fc * 1000, "fc_rampa_pct_h": rampa,
         "batt_kw": bmw * 1000, "batt_kwh": bmwh * 1000, "batt_carga_desde_fc": cfc}
    r = ssc.run(diseno.entradas(**p), outputs=diseno.SALIDAS)
    s = {k: np.asarray(v[:8760], float) for k, v in r.items() if isinstance(v, list)}
    L = s["load"]
    dfc = s["grid_to_load"]                                            # lo que la red tendría que poner
    exc = s["system_to_grid"] + s["fuelcell_to_grid"] + s["batt_to_grid"]
    carga = s["system_to_batt"] + s["fuelcell_to_batt"] + s["grid_to_batt"]
    dis = s["batt_to_load"] + s["batt_to_grid"]
    eff = np.where(s["fuelcell_electrical_efficiency"] > 0, s["fuelcell_electrical_efficiency"] / 100, np.nan)
    h2 = np.nansum(s["fuelcell_power"] / eff) / 33.33 / 1000           # t/año (PCI 33,33 kWh/kg)
    hora = np.arange(8760) % 24
    noche = (hora >= 18) | (hora < 6)
    mes = np.repeat(np.arange(12), [d * 24 for d in (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)])
    def_mes = np.bincount(mes, dfc, 12) / 1e6
    con = dfc > 1.0                                                    # umbral 1 kW (residuos numéricos)
    # racha más larga de horas seguidas con déficit
    racha = max((len(list(g)) for k, g in itertools.groupby(con) if k), default=0)
    return dict(
        pv_MWdc=pv, sofc_MW=fc, rampa_pct_h=rampa, bat_MW=bmw, bat_MWh=bmwh, bat_h=round(bmwh / bmw, 1),
        carga_desde_sofc=cfc, firme_MW=fc + bmw,
        cobertura_pct=round((1 - dfc.sum() / L.sum()) * 100, 3), deficit_GWh=round(dfc.sum() / 1e6, 3),
        horas_deficit=int(con.sum()), pct_horas_deficit=round(con.mean() * 100, 2),
        deficit_max_MW=round(dfc.max() / 1000, 1), racha_max_h=racha,
        dias_con_deficit=int(np.unique(np.arange(8760)[con] // 24).size),
        deficit_noche_pct=round(dfc[noche].sum() / max(dfc.sum(), 1) * 100, 1),
        peor_mes=int(def_mes.argmax()) + 1, deficit_peor_mes_GWh=round(def_mes.max(), 3),
        excedente_GWh=round(exc.sum() / 1e6, 2), horas_excedente=int((exc > 1.0).sum()),
        E_pv_GWh=round(s["ac"].sum() / 1e9, 2), E_sofc_GWh=round(s["fuelcell_power"].sum() / 1e6, 2),
        sofc_a_bat_GWh=round(s["fuelcell_to_batt"].sum() / 1e6, 2), fv_a_bat_GWh=round(s["system_to_batt"].sum() / 1e6, 2),
        desc_bat_GWh=round(dis.sum() / 1e6, 2), ciclos_bat=round(dis.sum() / (bmwh * 1000), 1),
        eta_rt_pct=round(dis.sum() / max(carga.sum(), 1) * 100, 1),
        H2_t=round(h2), terreno_ha=round(terreno_ha(pv, fc, bmwh), 1),
    )


def main():
    casos = list(itertools.product(PV, SOFC, RAMPA, BAT_MW, BAT_MWH, CARGA_FC)) + EXTRA
    print(f"{len(casos)} casos en {os.cpu_count()} procesos")
    t0 = time.time(); filas = []
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as ex:
        for i, fila in enumerate(ex.map(correr, casos, chunksize=8), 1):
            filas.append(fila)
            if i % 200 == 0:
                print(f"  {i}/{len(casos)}  {time.time() - t0:.0f} s", flush=True)
    with open("barrido_fino_brecha_SAM.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0])); w.writeheader(); w.writerows(filas)
    print(f"listo: {len(filas)} casos en {time.time() - t0:.0f} s -> barrido_fino_brecha_SAM.csv")


if __name__ == "__main__":
    main()
