import pytest
from django.urls import reverse

from pruebas.models import (
    Ambito, CampoPersonalizado, Carpeta, CasoDePrueba, CicloDePrueba, Ejecucion, Entorno,
    Estatus, PlanDePrueba, Prioridad, Reporte, Seccion,
)

pytestmark = pytest.mark.django_db

SECCIONES = ["casos", "planes", "ciclos", "reportes"]


def test_paginas_requieren_iniciar_sesion(client):
    for url in [reverse("pruebas:inicio"), reverse("pruebas:lista", args=["casos"]), reverse("pruebas:config")]:
        respuesta = client.get(url)
        assert respuesta.status_code == 302
        assert reverse("login") in respuesta.url


@pytest.mark.parametrize("seccion", SECCIONES)
def test_lista_y_formulario_nuevo_cargan(cliente, seccion):
    html = cliente.get(reverse("pruebas:lista", args=[seccion])).content.decode()
    assert "data-alternar-menu" in html  # menú hamburguesa
    assert "data-alternar-tema" in html
    assert "Configuración" in html
    assert cliente.get(reverse("pruebas:nuevo", args=[seccion])).status_code == 200


def test_login_en_espanol(client, usuario):
    assert "Contraseña" in client.get(reverse("login")).content.decode()
    r = client.post(reverse("login"), {"username": "qa", "password": "clave-segura-123"})
    assert r.url == reverse("pruebas:inicio")


# --- Carpetas ----------------------------------------------------------------

def test_crear_renombrar_mover_y_eliminar_carpeta(cliente):
    url = reverse("pruebas:carpeta_nueva", args=["casos"])
    cliente.post(url, {"nombre": "Login", "padre": ""})
    login = Carpeta.objects.get(nombre="Login")
    cliente.post(url, {"nombre": "Carrito", "padre": ""})
    carrito = Carpeta.objects.get(nombre="Carrito")
    cliente.post(url, {"nombre": "Recuperar", "padre": login.pk})
    sub = Carpeta.objects.get(nombre="Recuperar")
    assert Carpeta.objects.get_parent(sub) == login

    # Renombrar y mover a otra carpeta
    cliente.post(reverse("pruebas:carpeta_editar", args=[sub.pk]), {"nombre": "Recuperar contraseña", "padre": carrito.pk})
    sub = Carpeta.objects.get(pk=sub.pk)
    assert sub.nombre == "Recuperar contraseña"
    assert Carpeta.objects.get_parent(sub).pk == carrito.pk

    # Mover a la raíz
    cliente.post(reverse("pruebas:carpeta_editar", args=[sub.pk]), {"nombre": "Recuperar contraseña", "padre": ""})
    assert Carpeta.objects.get(pk=sub.pk).depth == 1

    # Eliminar: los casos quedan sin carpeta
    caso = CasoDePrueba.objects.create(titulo="X", carpeta=login)
    hija = Carpeta.objects.add_child(Carpeta.objects.get(pk=login.pk), {"nombre": "Hija", "seccion": "casos"})
    cliente.post(reverse("pruebas:carpeta_eliminar", args=[login.pk]))
    assert not Carpeta.objects.filter(pk__in=[login.pk, hija.pk]).exists()
    caso.refresh_from_db()
    assert caso.carpeta is None


def test_no_se_puede_mover_carpeta_dentro_de_si_misma(cliente):
    raiz = Carpeta.objects.add_root({"nombre": "A", "seccion": "casos"})
    hija = Carpeta.objects.add_child(raiz, {"nombre": "B", "seccion": "casos"})
    r = cliente.post(reverse("pruebas:carpeta_editar", args=[raiz.pk]), {"nombre": "A", "padre": hija.pk})
    assert r.status_code == 200  # el formulario rechaza la opción
    assert Carpeta.objects.get(pk=raiz.pk).depth == 1


def test_lista_filtra_por_carpeta_incluyendo_subcarpetas(cliente):
    raiz = Carpeta.objects.add_root({"nombre": "Login", "seccion": "casos"})
    hija = Carpeta.objects.add_child(raiz, {"nombre": "Sub", "seccion": "casos"})
    Carpeta.objects.add_root({"nombre": "Solo de planes", "seccion": "planes"})
    CasoDePrueba.objects.create(titulo="En la hija", carpeta=hija)
    CasoDePrueba.objects.create(titulo="Fuera", carpeta=None)
    html = cliente.get(reverse("pruebas:lista", args=["casos"]) + f"?carpeta={raiz.pk}").content.decode()
    assert "En la hija" in html and "Fuera" not in html
    assert "Solo de planes" not in html
    assert "<details" in html


# --- Casos -------------------------------------------------------------------

def _datos_caso(**extra):
    datos = {
        "titulo": "Iniciar sesión", "carpeta": "", "objetivo": "", "precondiciones": "",
        "estatus": "", "prioridad": Prioridad.objects.get(nombre="Alta").pk, "componente": "",
        "tipo": "manual", "asignado": "",
        "pasos-TOTAL_FORMS": "2", "pasos-INITIAL_FORMS": "0",
        "pasos-0-orden": "1", "pasos-0-accion": "Abrir login", "pasos-0-datos": "", "pasos-0-resultado_esperado": "Se ve el formulario",
        "pasos-1-orden": "2", "pasos-1-accion": "Ingresar credenciales", "pasos-1-datos": "qa/123", "pasos-1-resultado_esperado": "Entra al inicio",
    }
    datos.update(extra)
    return datos


def test_crear_caso_con_pasos_y_campo_personalizado(cliente, usuario):
    campo = CampoPersonalizado.objects.create(nombre="Navegador", ambito=Ambito.CASO, tipo="lista", opciones="Chrome\nFirefox")
    r = cliente.post(reverse("pruebas:nuevo", args=["casos"]), _datos_caso(**{campo.clave: "Firefox"}))
    caso = CasoDePrueba.objects.get()
    assert r.url == reverse("pruebas:detalle", args=["casos", caso.pk])
    assert caso.autor == usuario
    assert caso.estatus.nombre == "Borrador"
    assert [p.accion for p in caso.pasos.all()] == ["Abrir login", "Ingresar credenciales"]
    assert caso.campos_extra == {campo.clave: "Firefox"}
    html = cliente.get(r.url).content.decode()
    assert "Navegador" in html and "Firefox" in html and "Ingresar credenciales" in html


def test_campo_personalizado_obligatorio_se_valida(cliente):
    CampoPersonalizado.objects.create(nombre="Historia", ambito=Ambito.CASO, tipo="texto", obligatorio=True)
    r = cliente.post(reverse("pruebas:nuevo", args=["casos"]), _datos_caso())
    assert r.status_code == 200
    assert not CasoDePrueba.objects.exists()


def test_editar_caso_reordena_y_elimina_pasos(cliente):
    cliente.post(reverse("pruebas:nuevo", args=["casos"]), _datos_caso())
    caso = CasoDePrueba.objects.get()
    p1, p2 = caso.pasos.all()
    datos = _datos_caso(titulo="Iniciar sesión (editado)", **{
        "pasos-TOTAL_FORMS": "2", "pasos-INITIAL_FORMS": "2",
        "pasos-0-id": p1.pk, "pasos-0-orden": "2",
        "pasos-1-id": p2.pk, "pasos-1-orden": "1",
    })
    cliente.post(reverse("pruebas:editar", args=["casos", caso.pk]), datos)
    caso.refresh_from_db()
    assert caso.titulo == "Iniciar sesión (editado)"
    assert [p.accion for p in caso.pasos.all()] == ["Ingresar credenciales", "Abrir login"]

    datos["pasos-0-DELETE"] = "on"
    cliente.post(reverse("pruebas:editar", args=["casos", caso.pk]), datos)
    assert [p.accion for p in caso.pasos.all()] == ["Ingresar credenciales"]


def test_duplicar_y_eliminar_caso(cliente):
    cliente.post(reverse("pruebas:nuevo", args=["casos"]), _datos_caso())
    original = CasoDePrueba.objects.get()
    cliente.post(reverse("pruebas:duplicar_caso", args=[original.pk]))
    copia = CasoDePrueba.objects.exclude(pk=original.pk).get()
    assert copia.titulo.endswith("(copia)") and copia.pasos.count() == 2
    assert original.pasos.count() == 2

    cliente.post(reverse("pruebas:eliminar", args=["casos", original.pk]))
    assert not CasoDePrueba.objects.filter(pk=original.pk).exists()


def test_buscar_y_filtrar_casos(cliente, usuario):
    aprobado = Estatus.objects.get(ambito=Ambito.CASO, nombre="Aprobado")
    CasoDePrueba.objects.create(titulo="Pagar con tarjeta", estatus=aprobado, asignado=usuario)
    CasoDePrueba.objects.create(titulo="Pagar en efectivo")
    url = reverse("pruebas:lista", args=["casos"])
    html = cliente.get(url, {"q": "tarjeta"}).content.decode()
    assert "Pagar con tarjeta" in html and "efectivo" not in html
    html = cliente.get(url, {"estatus": aprobado.pk}).content.decode()
    assert "tarjeta" in html and "efectivo" not in html
    html = cliente.get(url, {"asignado": usuario.pk}).content.decode()
    assert "tarjeta" in html and "efectivo" not in html


# --- Planes y ciclos ---------------------------------------------------------

def test_flujo_plan_ciclo_y_ejecucion(cliente, usuario, estatus_ejec):
    casos = [CasoDePrueba.objects.create(titulo=f"Caso {i}") for i in range(3)]
    cliente.post(reverse("pruebas:nuevo", args=["planes"]), {"nombre": "Regresión v1", "carpeta": "", "estatus": "", "asignado": ""})
    plan = PlanDePrueba.objects.get()
    cliente.post(reverse("pruebas:agregar_casos", args=["planes", plan.pk]), {"casos": [c.pk for c in casos]})
    assert plan.casos.count() == 3

    entorno = Entorno.objects.get(nombre="QA")
    cliente.post(reverse("pruebas:nuevo", args=["ciclos"]), {
        "nombre": "Ciclo 1", "carpeta": "", "plan": plan.pk, "version": "1.0.0",
        "entorno": entorno.pk, "estatus": "", "asignado": "",
    })
    ciclo = CicloDePrueba.objects.get()
    cliente.post(reverse("pruebas:cargar_plan", args=[ciclo.pk]))
    assert ciclo.ejecuciones.count() == 3

    # Cambio rápido de estatus (HTMX) y pantalla de ejecución
    e1, e2, _ = ciclo.ejecuciones.order_by("caso_id")
    r = cliente.post(reverse("pruebas:estatus_ejecucion", args=[e1.pk]), {"estatus": estatus_ejec["Pasó"].pk}, HTTP_HX_REQUEST="true")
    assert r.status_code == 200 and "resumen-ciclo" in r.content.decode()
    e1.refresh_from_db()
    assert e1.ejecutado_por == usuario and e1.fecha_ejecucion is not None

    r = cliente.post(reverse("pruebas:ejecutar", args=[e2.pk]), {"estatus": estatus_ejec["Falló"].pk, "asignado": "", "comentario": "Error 500", "siguiente": "1"})
    assert r.url == reverse("pruebas:ejecutar", args=[ciclo.ejecuciones.order_by("caso_id").last().pk])
    e2.refresh_from_db()
    assert e2.comentario == "Error 500"
    assert ciclo.progreso == 67

    # Volver a «No ejecutado» limpia quién lo ejecutó
    cliente.post(reverse("pruebas:estatus_ejecucion", args=[e1.pk]), {"estatus": estatus_ejec["No ejecutado"].pk})
    e1.refresh_from_db()
    assert e1.ejecutado_por is None

    # Quitar caso del ciclo
    cliente.post(reverse("pruebas:quitar_caso", args=["ciclos", ciclo.pk, e1.caso_id]))
    assert ciclo.ejecuciones.count() == 2

    html = cliente.get(reverse("pruebas:detalle", args=["ciclos", ciclo.pk])).content.decode()
    assert "Ejecutar" in html and "hx-post" in html


def test_estatus_de_otro_ambito_se_rechaza(cliente):
    ciclo = CicloDePrueba.objects.create(nombre="C")
    caso = CasoDePrueba.objects.create(titulo="X")
    e = Ejecucion.objects.create(ciclo=ciclo, caso=caso)
    estatus_caso = Estatus.objects.filter(ambito=Ambito.CASO).first()
    r = cliente.post(reverse("pruebas:estatus_ejecucion", args=[e.pk]), {"estatus": estatus_caso.pk})
    assert r.status_code == 400


# --- Reportes ----------------------------------------------------------------

def test_crear_y_consultar_reporte(cliente):
    alta = Prioridad.objects.get(nombre="Alta")
    CasoDePrueba.objects.create(titulo="A", prioridad=alta)
    cliente.post(reverse("pruebas:nuevo", args=["reportes"]), {
        "nombre": "Casos por prioridad", "carpeta": "", "descripcion": "", "tipo": "casos",
        "agrupar_por": "prioridad", "plan": "", "ciclo": "", "entorno": "", "componente": "",
    })
    reporte = Reporte.objects.get()
    html = cliente.get(reverse("pruebas:detalle", args=["reportes", reporte.pk])).content.decode()
    assert "Alta" in html and "100 %" in html


# --- Configuración -----------------------------------------------------------

def test_configuracion_crud_y_proteccion(cliente):
    assert cliente.get(reverse("pruebas:config")).status_code == 302
    for c in ["entornos", "componentes", "etiquetas", "prioridades", "estatus-casos", "estatus-ejecuciones", "campos-casos", "campos-ciclos"]:
        assert cliente.get(reverse("pruebas:config_lista", args=[c])).status_code == 200
        assert cliente.get(reverse("pruebas:config_nuevo", args=[c])).status_code == 200

    cliente.post(reverse("pruebas:config_nuevo", args=["estatus-casos"]), {
        "nombre": "Bloqueado", "descripcion": "", "color": "naranja", "categoria": "bloqueado", "orden": 9, "activo": "on",
    })
    nuevo = Estatus.objects.get(nombre="Bloqueado", ambito=Ambito.CASO)
    assert nuevo.color == "naranja"

    cliente.post(reverse("pruebas:config_editar", args=["estatus-casos", nuevo.pk]), {
        "nombre": "Bloqueado por defecto", "descripcion": "", "color": "rojo", "categoria": "bloqueado", "orden": 9, "activo": "on",
    })
    nuevo.refresh_from_db()
    assert nuevo.nombre == "Bloqueado por defecto"

    # Un estatus en uso no se elimina
    CasoDePrueba.objects.create(titulo="X", estatus=nuevo)
    r = cliente.post(reverse("pruebas:config_eliminar", args=["estatus-casos", nuevo.pk]), follow=True)
    assert Estatus.objects.filter(pk=nuevo.pk).exists()
    assert "está en uso" in r.content.decode()

    # Un entorno sin uso sí
    entorno = Entorno.objects.create(nombre="Temporal")
    cliente.post(reverse("pruebas:config_eliminar", args=["entornos", entorno.pk]))
    assert not Entorno.objects.filter(pk=entorno.pk).exists()


def test_config_no_permite_editar_elemento_de_otro_ambito(cliente):
    estatus_plan = Estatus.objects.filter(ambito=Ambito.PLAN).first()
    r = cliente.get(reverse("pruebas:config_editar", args=["estatus-casos", estatus_plan.pk]))
    assert r.status_code == 404


def test_campo_personalizado_aparece_en_formulario(cliente):
    cliente.post(reverse("pruebas:config_nuevo", args=["campos-ciclos"]), {
        "nombre": "Sprint", "tipo": "numero", "opciones": "", "orden": 0, "activo": "on",
    })
    html = cliente.get(reverse("pruebas:nuevo", args=["ciclos"])).content.decode()
    assert "Sprint" in html and "Campos personalizados" in html
