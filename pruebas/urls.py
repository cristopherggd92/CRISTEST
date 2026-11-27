from django.urls import path

from . import views

app_name = "pruebas"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("casos/", views.casos, name="casos"),
    path("ciclos/", views.ciclos, name="ciclos"),
    path("planes/", views.planes, name="planes"),
    path("reportes/", views.reportes, name="reportes"),
]
