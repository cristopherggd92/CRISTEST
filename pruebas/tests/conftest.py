import pytest

from pruebas.models import Ambito, Estatus


@pytest.fixture
def usuario(django_user_model):
    return django_user_model.objects.create_user(username="qa", password="clave-segura-123")


@pytest.fixture
def cliente(client, usuario):
    client.force_login(usuario)
    return client


@pytest.fixture
def estatus_ejec():
    """Estatus de ejecución creados por la migración inicial, por nombre."""
    return {e.nombre: e for e in Estatus.objects.filter(ambito=Ambito.EJECUCION)}
