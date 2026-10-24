"""Puente mínimo (ctypes) al motor SSC de SAM 2026.7.3.

La carpeta de instalación de SAM se lee de la variable de entorno SAM_DIR
(por defecto C:\\SAM\\2026.7.3, la ruta que propone el instalador de Windows).

Permite correr la configuración "Fuel Cell - Commercial" con los mismos módulos que la interfaz:
pvwattsv8 -> fuelcell -> battery -> grid (-> utilityrate5 -> thermalrate -> cashloan).
"""
import ctypes as C
import json, os
from pathlib import Path

SAM_DIR = Path(os.environ.get("SAM_DIR", r"C:\SAM\2026.7.3"))
os.add_dll_directory(str(SAM_DIR / "x64"))
_dll = C.CDLL(str(SAM_DIR / "x64" / "ssc.dll"))

_vp, _cp, _d, _i = C.c_void_p, C.c_char_p, C.c_double, C.c_int
for name, res, args in [
    ("ssc_version", _i, []), ("ssc_build_info", _cp, []),
    ("json_to_ssc_data", _vp, [_cp]), ("ssc_data_to_json", _cp, [_vp]),
    ("ssc_data_free", None, [_vp]), ("ssc_data_query", _i, [_vp, _cp]),
    ("ssc_data_first", _cp, [_vp]), ("ssc_data_next", _cp, [_vp]),
    ("ssc_data_set_number", None, [_vp, _cp, _d]),
    ("ssc_data_set_array", None, [_vp, _cp, C.POINTER(_d), _i]),
    ("ssc_data_get_number", _i, [_vp, _cp, C.POINTER(_d)]),
    ("ssc_data_get_array", C.POINTER(_d), [_vp, _cp, C.POINTER(_i)]),
    ("ssc_data_get_matrix", C.POINTER(_d), [_vp, _cp, C.POINTER(_i), C.POINTER(_i)]),
    ("ssc_data_get_string", _cp, [_vp, _cp]),
    ("ssc_module_create", _vp, [_cp]), ("ssc_module_free", None, [_vp]),
    ("ssc_module_exec", _i, [_vp, _vp]),
    ("ssc_module_log", _cp, [_vp, _i, C.POINTER(_i), C.POINTER(C.c_float)]),
    ("ssc_module_var_info", _vp, [_vp, _i]),
    ("ssc_info_var_type", _i, [_vp]), ("ssc_info_data_type", _i, [_vp]),
    ("ssc_info_name", _cp, [_vp]), ("ssc_info_label", _cp, [_vp]), ("ssc_info_units", _cp, [_vp]),
    ("ssc_info_meta", _cp, [_vp]), ("ssc_info_required", _cp, [_vp]), ("ssc_info_group", _cp, [_vp]),
    ("ssc_module_exec_set_print", None, [_i]),
]:
    f = getattr(_dll, name); f.restype = res; f.argtypes = args
_dll.ssc_module_exec_set_print(0)   # sin mensajes de progreso en consola

SSC_INPUT, SSC_OUTPUT, SSC_INOUT = 1, 2, 3
SSC_STRING, SSC_NUMBER, SSC_ARRAY, SSC_MATRIX, SSC_TABLE = 1, 2, 3, 4, 5
FUELCELL_COMMERCIAL = ["pvwattsv8", "fuelcell", "battery", "grid", "utilityrate5", "thermalrate", "cashloan"]
PERFORMANCE = FUELCELL_COMMERCIAL[:4]


def version():
    return _dll.ssc_version(), _dll.ssc_build_info().decode()


def defaults(config="Fuel Cell_Commercial"):
    """Entradas por defecto de SAM para la configuración (mismo archivo que usa la interfaz)."""
    with open(SAM_DIR / "runtime" / "defaults" / f"{config}.json", encoding="utf-8") as f:
        return json.load(f)


def module_vars(module):
    """Lista (tipo, nombre, etiqueta, unidades, meta) de las variables de un módulo SSC."""
    m = _dll.ssc_module_create(module.encode())
    out, i = [], 0
    while True:
        inf = _dll.ssc_module_var_info(m, i)
        if not inf:
            break
        g = lambda fn: (fn(inf) or b"").decode(errors="replace")
        out.append(dict(vt=_dll.ssc_info_var_type(inf), dt=_dll.ssc_info_data_type(inf),
                        name=g(_dll.ssc_info_name), label=g(_dll.ssc_info_label),
                        units=g(_dll.ssc_info_units), meta=g(_dll.ssc_info_meta),
                        required=g(_dll.ssc_info_required), group=g(_dll.ssc_info_group)))
        i += 1
    _dll.ssc_module_free(m)
    return out


class Result(dict):
    """Diccionario de salidas; las series se devuelven como listas de floats."""


def run(inputs, modules=PERFORMANCE, outputs=None, verbose=False):
    """Ejecuta los módulos en secuencia sobre un mismo contenedor de datos (como SAM).

    inputs  : dict con las entradas (p. ej. defaults() modificado)
    outputs : nombres de salidas a recuperar; None = todas las salidas numéricas/arrays de los módulos
    """
    data = _dll.json_to_ssc_data(json.dumps(inputs).encode())
    if not data:
        raise RuntimeError("json_to_ssc_data falló")
    logs, names = [], set()
    try:
        for mod in modules:
            m = _dll.ssc_module_create(mod.encode())
            if not m:
                raise RuntimeError(f"no existe el módulo {mod}")
            ok = _dll.ssc_module_exec(m, data)
            k = 0
            while True:
                t, tm = C.c_int(), C.c_float()
                msg = _dll.ssc_module_log(m, k, C.byref(t), C.byref(tm))
                if not msg:
                    break
                logs.append((mod, t.value, msg.decode(errors="replace")))
                k += 1
            if outputs is None:
                for v in module_vars(mod):
                    if v["vt"] in (SSC_OUTPUT, SSC_INOUT):
                        names.add(v["name"])
            _dll.ssc_module_free(m)
            if not ok:
                errs = [l for l in logs if l[0] == mod]
                raise RuntimeError(f"{mod} falló: {errs}")
        res = Result()
        for n in (outputs or sorted(names)):
            typ = _dll.ssc_data_query(data, n.encode())
            if typ == SSC_NUMBER:
                v = C.c_double(); _dll.ssc_data_get_number(data, n.encode(), C.byref(v)); res[n] = v.value
            elif typ == SSC_ARRAY:
                ln = C.c_int(); p = _dll.ssc_data_get_array(data, n.encode(), C.byref(ln))
                res[n] = [p[i] for i in range(ln.value)]
            elif typ == SSC_MATRIX:
                r_, c_ = C.c_int(), C.c_int(); p = _dll.ssc_data_get_matrix(data, n.encode(), C.byref(r_), C.byref(c_))
                res[n] = [[p[i * c_.value + j] for j in range(c_.value)] for i in range(r_.value)]
            elif typ == SSC_STRING:
                res[n] = (_dll.ssc_data_get_string(data, n.encode()) or b"").decode()
        res.logs = logs
        if verbose:
            for l in logs:
                print(l)
        return res
    finally:
        _dll.ssc_data_free(data)
