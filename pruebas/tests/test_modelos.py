import datetime as dt

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from pruebas.models import (
    Ambito, CampoPersonalizado, Carpeta, CasoDePrueba, CicloDePrueba, Ejecucion, Estatus,
    PlanDePrueba, Prioridad, Reporte, Seccion,
)

pytestmark = pytest.mark.django_db


def test_configuracion_inicial_creada_por_migracion():
    assert Estatus.objects.filter(ambito=Ambito.EJECUCION).count() == 6
    assert set(Prioridad.objects.values_list("nombre", flat=True)) == {"Baja", "Media", "Alta", "Crítica"}
    for ambito in Ambito.values:
        assert Estatus.objects.filter(ambito=ambito, por_defecto=True).count() == 1


def test_codigos_de_elementos():
    caso = CasoDePrueba.objects.create(titulo="Login válido")
    plan = PlanDePrueba.objects.create(nombre="Regresión")
    ciclo = CicloDePrueba.objects.create(nombre="Ciclo 1")
    assert caso.codigo == f"TC-{caso.pk:04d}"
    assert plan.codigo == f"TP-{plan.pk:04d}"
    assert ciclo.codigo == f"CY-{ciclo.pk:04d}"


def test_estatus_por_defecto_se_asigna_al_crear():
    caso = CasoDePrueba.objects.create(titulo="X")
    assert caso.estatus.nombre == "Borrador"


def test_solo_un_estatus_por_defecto_por_ambito():
    nuevo = Estatus.objects.create(nombre="Nuevo", ambito=Ambito.CASO, por_defecto=True)
    assert list(Estatus.objects.filter(ambito=Ambito.CASO, por_defecto=True)) == [nuevo]
    assert Estatus.objects.filter(ambito=Ambito.PLAN, por_defecto=True).count() == 1


def test_carpetas_anidadas_ruta_y_subarbol():
    raiz = Carpeta.objects.add_root({"nombre": "Login", "seccion": Seccion.CASOS})
    hija = Carpeta.objects.add_child(raiz, {"nombre": "Recuperar contraseña", "seccion": Seccion.CASOS})
    nieta = Carpeta.objects.add_child(hija, {"nombre": "Correo", "seccion": Seccion.CASOS})
    assert nieta.ruta == "Login / Recuperar contraseña / Correo"
    assert set(raiz.ids_subarbol()) == {raiz.pk, hija.pk, nieta.pk}


def test_caso_no_acepta_carpeta_ni_estatus_de_otra_seccion():
    carpeta_planes = Carpeta.objects.add_root({"nombre": "Sprint 1", "seccion": Seccion.PLANES})
    estatus_plan = Estatus.objects.filter(ambito=Ambito.PLAN).first()
    caso = CasoDePrueba(titulo="X", carpeta=carpeta_planes, estatus=estatus_plan)
    with pytest.raises(ValidationError) as error:
        caso.full_clean()
    assert {"carpeta", "estatus"} <= set(error.value.message_dict)


def test_plan_valida_rango_de_fechas():
    plan = PlanDePrueba(nombre="R", fecha_inicio=dt.date(2026, 12, 10), fecha_fin=dt.date(2026, 12, 1))
    with pytest.raises(ValidationError) as error:
        plan.full_clean()
    assert "fecha_fin" in error.value.message_dict


def test_campo_lista_requiere_opciones():
    campo = CampoPersonalizado(nombre="Navegador", ambito=Ambito.CASO, tipo="lista")
    with pytest.raises(ValidationError):
        campo.full_clean()
    campo.opciones = "Chrome\nFirefox\n\n"
    campo.full_clean()
    assert campo.lista_opciones == ["Chrome", "Firefox"]


def test_ciclo_agrega_casos_sin_duplicar_y_calcula_progreso(estatus_ejec):
    ciclo = CicloDePrueba.objects.create(nombre="Ciclo 1")
    casos = [CasoDePrueba.objects.create(titulo=f"Caso {i}") for i in range(4)]
    assert ciclo.agregar_casos(casos[:3]) == 3
    assert ciclo.agregar_casos(casos) == 1
    assert ciclo.progreso == 0
    ejecuciones = list(ciclo.ejecuciones.order_by("caso_id"))
    for e, nombre in zip(ejecuciones, ["Pasó", "Pasó", "Falló"]):
        e.estatus = estatus_ejec[nombre]
        e.save()
    assert ciclo.progreso == 75
    resumen = {f["estatus"].nombre: f["total"] for f in ciclo.resumen()}
    assert resumen["Pasó"] == 2 and resumen["Falló"] == 1 and resumen["No ejecutado"] == 1


def test_un_caso_solo_se_agrega_una_vez_por_ciclo():
    ciclo = CicloDePrueba.objects.create(nombre="Ciclo 1")
    caso = CasoDePrueba.objects.create(titulo="Caso")
    Ejecucion.objects.create(ciclo=ciclo, caso=caso)
    with pytest.raises(IntegrityError):
        Ejecucion.objects.create(ciclo=ciclo, caso=caso)


def test_reporte_de_ejecucion_por_estatus(estatus_ejec):
    plan = PlanDePrueba.objects.create(nombre="P")
    ciclo = CicloDePrueba.objects.create(nombre="C", plan=plan)
    casos = [CasoDePrueba.objects.create(titulo=f"Caso {i}") for i in range(4)]
    ciclo.agregar_casos(casos)
    for e in ciclo.ejecuciones.all()[:3]:
        e.estatus = estatus_ejec["Pasó"]
        e.save()
    otro = CicloDePrueba.objects.create(nombre="Otro")
    otro.agregar_casos(casos)

    filas = Reporte(nombre="R", tipo="ejecucion", agrupar_por="estatus", plan=plan).resultados()
    datos = {f["etiqueta"]: (f["total"], f["porcentaje"]) for f in filas}
    assert datos == {"Pasó": (3, 75), "No ejecutado": (1, 25)}


def test_reporte_de_casos_por_prioridad():
    alta = Prioridad.objects.get(nombre="Alta")
    CasoDePrueba.objects.create(titulo="A", prioridad=alta)
    CasoDePrueba.objects.create(titulo="B", prioridad=alta)
    CasoDePrueba.objects.create(titulo="C")
    filas = Reporte(nombre="R", tipo="casos", agrupar_por="prioridad").resultados()
    assert [(f["etiqueta"], f["total"]) for f in filas] == [("Alta", 2), ("Sin asignar", 1)]


def test_reporte_de_casos_no_se_agrupa_por_ciclo():
    with pytest.raises(ValidationError):
        Reporte(nombre="R", tipo="casos", agrupar_por="ciclo").full_clean()
