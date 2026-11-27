import pytest
from django.urls import reverse

from pruebas.models import Carpeta, CasoDePrueba, Seccion

pytestmark = pytest.mark.django_db

SECCIONES = ["pruebas:inicio", "pruebas:casos", "pruebas:ciclos", "pruebas:planes", "pruebas:reportes"]


@pytest.fixture
def usuario(django_user_model):
    return django_user_model.objects.create_user(username="qa", password="clave-segura-123")


@pytest.mark.parametrize("nombre", SECCIONES)
def test_secciones_requieren_iniciar_sesion(client, nombre):
    respuesta = client.get(reverse(nombre))
    assert respuesta.status_code == 302
    assert reverse("login") in respuesta.url


@pytest.mark.parametrize("nombre", SECCIONES)
def test_secciones_cargan_para_usuario_autenticado(client, usuario, nombre):
    client.force_login(usuario)
    respuesta = client.get(reverse(nombre))
    assert respuesta.status_code == 200
    html = respuesta.content.decode()
    # Menú lateral con las cuatro secciones y botón de tema en todas las páginas
    for texto in ["Casos de Prueba", "Ciclos de Prueba", "Planes de Prueba", "Reportes"]:
        assert texto in html
    assert "data-alternar-tema" in html


def test_login_en_espanol_e_inicio_de_sesion(client, usuario):
    respuesta = client.get(reverse("login"))
    assert respuesta.status_code == 200
    assert "Contraseña" in respuesta.content.decode()

    respuesta = client.post(
        reverse("login"), {"username": "qa", "password": "clave-segura-123"}
    )
    assert respuesta.status_code == 302
    assert respuesta.url == reverse("pruebas:inicio")


def test_login_con_credenciales_incorrectas(client, usuario):
    respuesta = client.post(reverse("login"), {"username": "qa", "password": "mala"})
    assert respuesta.status_code == 200
    assert "Usuario o contraseña incorrectos" in respuesta.content.decode()


def test_arbol_de_carpetas_muestra_subcarpetas_y_casos(client, usuario):
    raiz = Carpeta.objects.add_root({"nombre": "Módulo Login", "seccion": Seccion.CASOS})
    hija = Carpeta.objects.add_child(raiz, {"nombre": "Recuperar contraseña", "seccion": Seccion.CASOS})
    Carpeta.objects.add_root({"nombre": "Solo de planes", "seccion": Seccion.PLANES})
    CasoDePrueba.objects.create(titulo="Enviar correo de recuperación", carpeta=hija)

    client.force_login(usuario)
    html = client.get(reverse("pruebas:casos")).content.decode()
    assert "Módulo Login" in html
    assert "Recuperar contraseña" in html
    assert "Enviar correo de recuperación" in html
    assert "<details" in html  # carpetas desplegables
    assert "Solo de planes" not in html  # cada sección tiene su propio árbol
