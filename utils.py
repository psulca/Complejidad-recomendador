import pandas as pd
import math
from typing import Any


def limpiar_valor_nan(valor: Any, valor_default: Any) -> Any:
    if valor is None:
        return valor_default
    
    try:
        if pd.isna(valor):
            return valor_default
    except:
        pass
    
    if isinstance(valor, float) and math.isnan(valor):
        return valor_default
    
    if isinstance(valor, str):
        valor_str = valor.strip().lower()
        if valor_str in ["nan", "none", "null", ""]:
            return valor_default
    
    return valor


def limpiar_curso_data(curso: dict) -> dict:
    curso_limpio = {}
    for key, value in curso.items():
        if value is None:
            curso_limpio[key] = None if key == "requisitos" else (0.0 if key == "creditos" else (0 if key == "nivel" else ""))
        elif isinstance(value, float) and math.isnan(value):
            curso_limpio[key] = 0.0 if key == "creditos" else 0
        elif isinstance(value, str) and value.lower() in ["nan", "none", "null"]:
            curso_limpio[key] = None if key == "requisitos" else ""
        else:
            curso_limpio[key] = value
    return curso_limpio


def eliminar_duplicados_lote(lote: list) -> list:
    lote_unicos = {}
    for curso in lote:
        clave = (curso["codigo"], curso["carrera"])
        lote_unicos[clave] = curso
    return list(lote_unicos.values())

