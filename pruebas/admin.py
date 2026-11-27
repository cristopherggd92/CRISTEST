from django.contrib import admin
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from .models import (
    Carpeta,
    CasoDePrueba,
    CicloDePrueba,
    Ejecucion,
    PasoDePrueba,
    PlanDePrueba,
)


@admin.register(Carpeta)
class CarpetaAdmin(TreeAdmin):
    form = movenodeform_factory(Carpeta, fields=["nombre", "seccion"])
    list_display = ["nombre", "seccion"]
    list_filter = ["seccion"]


class PasoInline(admin.TabularInline):
    model = PasoDePrueba
    extra = 1


@admin.register(CasoDePrueba)
class CasoDePruebaAdmin(admin.ModelAdmin):
    list_display = ["codigo", "titulo", "carpeta", "prioridad", "tipo", "estado", "actualizado"]
    list_filter = ["prioridad", "tipo", "estado"]
    search_fields = ["titulo", "descripcion", "etiquetas"]
    inlines = [PasoInline]
    readonly_fields = ["creado", "actualizado"]

    @admin.display(description="código", ordering="id")
    def codigo(self, obj):
        return obj.codigo

    def save_model(self, request, obj, form, change):
        if not obj.autor_id:
            obj.autor = request.user
        super().save_model(request, obj, form, change)


@admin.register(PlanDePrueba)
class PlanDePruebaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "carpeta", "estado", "fecha_inicio", "fecha_fin"]
    list_filter = ["estado"]
    search_fields = ["nombre"]
    filter_horizontal = ["casos"]

    def save_model(self, request, obj, form, change):
        if not obj.autor_id:
            obj.autor = request.user
        super().save_model(request, obj, form, change)


class EjecucionInline(admin.TabularInline):
    model = Ejecucion
    extra = 0
    autocomplete_fields = ["caso"]


@admin.register(CicloDePrueba)
class CicloDePruebaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "plan", "version", "entorno", "estado", "progreso_pct"]
    list_filter = ["estado", "entorno"]
    search_fields = ["nombre", "version"]
    inlines = [EjecucionInline]

    @admin.display(description="progreso")
    def progreso_pct(self, obj):
        return f"{obj.progreso} %"


@admin.register(Ejecucion)
class EjecucionAdmin(admin.ModelAdmin):
    list_display = ["caso", "ciclo", "estado", "ejecutado_por", "fecha_ejecucion"]
    list_filter = ["estado", "ciclo"]
