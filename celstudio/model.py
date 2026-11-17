"""Utilidades compartidas del motor v2: errores de contrato, rutas de recurso e identificadores."""
from pathlib import Path
import math
import re


class ContractError(ValueError):
    pass


def number(value, label, low=-100000, high=100000):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ContractError(f'{label}: número entre {low} y {high} requerido')
    return value


def asset_path(root, relative):
    if not isinstance(relative, str) or not relative:
        raise ContractError('Ruta de recurso vacía')
    if Path(relative).is_absolute() or Path(relative).drive:
        raise ContractError('La ruta de recurso debe ser relativa al proyecto')
    path = (Path(root) / relative).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ContractError('El recurso debe estar dentro del proyecto')
    return path


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', value):
        raise ContractError('ID inválido: usa letras, números, guion o guion bajo')
    return value
