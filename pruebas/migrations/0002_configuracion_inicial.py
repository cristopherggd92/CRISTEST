"""Valores iniciales de configuración (editables desde la sección «Configuración»)."""

from django.db import migrations

ESTATUS = {
    "caso": [
        ("Borrador", "gris", "pendiente", True),
        ("En revisión", "amarillo", "en_progreso", False),
        ("Aprobado", "verde", "exito", False),
        ("Obsoleto", "rojo", "otro", False),
    ],
    "plan": [
        ("Nuevo", "gris", "pendiente", True),
        ("En progreso", "azul", "en_progreso", False),
        ("Terminado", "verde", "exito", False),
    ],
    "ciclo": [
        ("Planificado", "gris", "pendiente", True),
        ("En progreso", "azul", "en_progreso", False),
        ("Terminado", "verde", "exito", False),
    ],
    "ejecucion": [
        ("No ejecutado", "gris", "pendiente", True),
        ("En progreso", "azul", "en_progreso", False),
        ("Pasó", "verde", "exito", False),
        ("Falló", "rojo", "fallo", False),
        ("Bloqueado", "naranja", "bloqueado", False),
        ("Omitido", "morado", "otro", False),
    ],
}

PRIORIDADES = [("Baja", "gris"), ("Media", "azul"), ("Alta", "naranja"), ("Crítica", "rojo")]
ENTORNOS = [
    ("Dev", "Entorno de desarrollo"),
    ("QA", "Entorno de pruebas"),
    ("UAT", "Pruebas de aceptación de usuario"),
    ("Producción", "Entorno productivo"),
]
ETIQUETAS = [("Smoke", "verde"), ("Regresión", "azul"), ("Crítico", "rojo")]


def crear(apps, schema_editor):
    Estatus = apps.get_model("pruebas", "Estatus")
    Prioridad = apps.get_model("pruebas", "Prioridad")
    Entorno = apps.get_model("pruebas", "Entorno")
    Etiqueta = apps.get_model("pruebas", "Etiqueta")
    for ambito, filas in ESTATUS.items():
        for i, (nombre, color, categoria, defecto) in enumerate(filas):
            Estatus.objects.create(
                nombre=nombre, ambito=ambito, color=color, categoria=categoria,
                por_defecto=defecto, orden=i,
            )
    for i, (nombre, color) in enumerate(PRIORIDADES):
        Prioridad.objects.create(nombre=nombre, color=color, orden=i)
    for i, (nombre, desc) in enumerate(ENTORNOS):
        Entorno.objects.create(nombre=nombre, descripcion=desc, orden=i)
    for i, (nombre, color) in enumerate(ETIQUETAS):
        Etiqueta.objects.create(nombre=nombre, color=color, orden=i)


class Migration(migrations.Migration):
    dependencies = [("pruebas", "0001_initial")]
    operations = [migrations.RunPython(crear, migrations.RunPython.noop)]
