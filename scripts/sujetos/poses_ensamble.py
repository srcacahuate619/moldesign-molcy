"""SUJETO: el ensamble de poses de acoplamiento.

NO DISPONIBLE todavia, y esta aqui a proposito: declarar el hueco es mas util
que no tenerlo. El maestro lo lista, dice por que no se puede, y senala donde
esta el arreglo.
"""
from __future__ import annotations

from variables.sujeto import Montado, SujetoNoDisponible

ID = "poses_ensamble"
DESCRIPCION = "Las N poses del ensamble de acoplamiento sobre el receptor."

FALTA = (
    "el paquete de escena no trae poses de Vina. Su propio exportador lo dice: "
    "hay que pasar por `services/docking/pose_recovery.py`, que tiene seis "
    "puertas y puede abstenerse, y no vale leer el SDF de la corrida. "
    "El arreglo va en moldesign-build, no aqui."
)


def disponible(paq) -> tuple[bool, str]:
    return False, FALTA


def cargar(paq) -> Montado:
    raise SujetoNoDisponible(FALTA)
