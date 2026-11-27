from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

admin.site.site_header = "CRISTEST · Administración"
admin.site.site_title = "CRISTEST"
admin.site.index_title = "Gestión de pruebas"

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "ingresar/",
        auth_views.LoginView.as_view(redirect_authenticated_user=True),
        name="login",
    ),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("pruebas.urls")),
]
