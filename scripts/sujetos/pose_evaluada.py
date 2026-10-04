"""Vina top-1 de una corrida MolDesign, nunca el ligando cocristalizado."""
from __future__ import annotations

import hashlib

import bl_ext.blender_org.molecularnodes as mn

from nucleo import arte
from variables.sujeto import Montado, SujetoNoDisponible

ID = "pose_evaluada"
DESCRIPCION = "Primera pose 3D persistida por una corrida concreta de Vina."


def disponible(paq):
    d = paq.dock
    if d is None:
        return False, "la corrida no conserva docking.json con caja y poses"
    pose = d["poses"][0]
    ruta = paq.ruta_dock(pose.get("pdb_visual", ""))
    if ruta is None:
        return False, "falta la geometría PDB de la pose top-1"
    if hashlib.sha256(ruta.read_bytes()).hexdigest() != pose.get("pdb_visual_sha256"):
        return False, "el hash de la geometría visual no coincide"
    return True, "Vina top-1 con coordenadas y hash verificados"


def cargar(paq, _ctx=None):
    ok, razon = disponible(paq)
    if not ok:
        raise SujetoNoDisponible(razon)
    pose = paq.dock["poses"][0]
    lig = mn.Molecule.load(str(paq.ruta_dock(pose["pdb_visual"])),
                           name=f"{paq.pdb_id}_vina_top1")
    lig.add_style("ball_and_stick", name="vina_top1")
    mat = arte.material_del_estilo(lig, "Ball and Stick", f"{paq.pdb_id}_VinaTop1")
    arte.realzar_protagonista(mat)
    m = Montado()
    m.objetos.append(lig.object)
    if mat:
        m.materiales.append(mat)
    centro = arte.centro_evaluado(lig.object)
    m.anclas.append(("vina_top1", "Vina top-1", centro))
    puntos = arte.puntos_evaluados(lig.object)
    m.dianas += puntos[::max(1, len(puntos) // 120)]
    m.medido["pose_rank"] = 1
    m.medido["afinidad_kcal_mol"] = pose.get("afinidad_kcal_mol")
    m.notas.append("Pose Vina top-1 de la corrida declarada; no es ligando cristalográfico.")
    m.notas.append("No se dibujan contactos ni trayectoria de búsqueda no medidos.")
    return m
