from django.urls import path, register_converter

from . import views, views_config


class SeccionConverter:
    regex = "casos|planes|ciclos|reportes"

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value


register_converter(SeccionConverter, "seccion")

app_name = "pruebas"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    # Secciones
    path("<seccion:seccion>/", views.lista, name="lista"),
    path("<seccion:seccion>/nuevo/", views.formulario, name="nuevo"),
    path("<seccion:seccion>/<int:pk>/", views.detalle, name="detalle"),
    path("<seccion:seccion>/<int:pk>/editar/", views.formulario, name="editar"),
    path("<seccion:seccion>/<int:pk>/eliminar/", views.eliminar, name="eliminar"),
    path("<seccion:seccion>/<int:pk>/agregar-casos/", views.seleccionar_casos, name="agregar_casos"),
    path("<seccion:seccion>/<int:pk>/quitar-caso/<int:caso_pk>/", views.quitar_caso, name="quitar_caso"),
    path("casos/<int:pk>/duplicar/", views.duplicar_caso, name="duplicar_caso"),
    path("ciclos/<int:pk>/cargar-plan/", views.cargar_casos_del_plan, name="cargar_plan"),
    path("ejecuciones/<int:pk>/", views.ejecutar, name="ejecutar"),
    path("ejecuciones/<int:pk>/estatus/", views.cambiar_estatus_ejecucion, name="estatus_ejecucion"),
    # Carpetas
    path("<seccion:seccion>/carpetas/nueva/", views.carpeta_nueva, name="carpeta_nueva"),
    path("carpetas/<int:pk>/editar/", views.carpeta_editar, name="carpeta_editar"),
    path("carpetas/<int:pk>/eliminar/", views.carpeta_eliminar, name="carpeta_eliminar"),
    # Configuración
    path("configuracion/", views_config.inicio, name="config"),
    path("configuracion/<slug:clave>/", views_config.lista, name="config_lista"),
    path("configuracion/<slug:clave>/nuevo/", views_config.formulario, name="config_nuevo"),
    path("configuracion/<slug:clave>/<int:pk>/", views_config.formulario, name="config_editar"),
    path("configuracion/<slug:clave>/<int:pk>/eliminar/", views_config.eliminar, name="config_eliminar"),
]
