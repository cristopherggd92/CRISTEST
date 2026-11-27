import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from pruebas.models import Carpeta, CasoDePrueba, CicloDePrueba, Ejecucion, PlanDePrueba, Seccion

pytestmark = pytest.mark.django_db


def test_codigo_de_caso_se_genera_a_partir_del_id():
    caso = CasoDePrueba.objects.create(titulo="Iniciar sesión con credenciales válidas")
    assert caso.codigo == f"TC-{caso.pk:04d}"
    assert CasoDePrueba(titulo="sin guardar").codigo == "TC-nuevo"


def test_carpetas_anidadas_y_ruta():
    raiz = Carpeta.objects.add_root({"nombre": "Login", "seccion": Seccion.CASOS})
    hija = Carpeta.objects.add_child(raiz, {"nombre": "Recuperar contraseña", "seccion": Seccion.CASOS})
    assert Carpeta.objects.get_parent(hija) == raiz
    assert hija.ruta == "Login / Recuperar contraseña"


def test_subcarpeta_no_puede_cambiar_de_seccion():
    raiz = Carpeta.objects.add_root({"nombre": "Login", "seccion": Seccion.CASOS})
    hija = Carpeta.objects.add_child(raiz, {"nombre": "Otra", "seccion": Seccion.CASOS})
    hija.seccion = Seccion.PLANES
    with pytest.raises(ValidationError):
        hija.full_clean()


def test_caso_no_acepta_carpeta_de_otra_seccion():
    carpeta_planes = Carpeta.objects.add_root({"nombre": "Sprint 1", "seccion": Seccion.PLANES})
    caso = CasoDePrueba(titulo="X", carpeta=carpeta_planes)
    with pytest.raises(ValidationError) as error:
        caso.full_clean()
    assert "carpeta" in error.value.message_dict


def test_plan_valida_rango_de_fechas():
    import datetime as dt

    plan = PlanDePrueba(
        nombre="Regresión", fecha_inicio=dt.date(2026, 12, 10), fecha_fin=dt.date(2026, 12, 1)
    )
    with pytest.raises(ValidationError) as error:
        plan.full_clean()
    assert "fecha_fin" in error.value.message_dict


def test_etiquetas_se_separan_por_comas():
    caso = CasoDePrueba(titulo="X", etiquetas="smoke, login ,, regresión")
    assert caso.lista_etiquetas == ["smoke", "login", "regresión"]


def test_resumen_y_progreso_del_ciclo():
    ciclo = CicloDePrueba.objects.create(nombre="Ciclo 1")
    casos = [CasoDePrueba.objects.create(titulo=f"Caso {i}") for i in range(4)]
    estados = [
        Ejecucion.Estado.PASO,
        Ejecucion.Estado.PASO,
        Ejecucion.Estado.FALLO,
        Ejecucion.Estado.NO_EJECUTADO,
    ]
    for caso, estado in zip(casos, estados):
        Ejecucion.objects.create(ciclo=ciclo, caso=caso, estado=estado)

    resumen = ciclo.resumen()
    assert resumen["paso"] == 2
    assert resumen["fallo"] == 1
    assert resumen["bloqueado"] == 0
    assert ciclo.progreso == 75


def test_progreso_de_ciclo_vacio_es_cero():
    assert CicloDePrueba.objects.create(nombre="Vacío").progreso == 0


def test_un_caso_solo_se_agrega_una_vez_por_ciclo():
    ciclo = CicloDePrueba.objects.create(nombre="Ciclo 1")
    caso = CasoDePrueba.objects.create(titulo="Caso")
    Ejecucion.objects.create(ciclo=ciclo, caso=caso)
    with pytest.raises(IntegrityError):
        Ejecucion.objects.create(ciclo=ciclo, caso=caso)
