from django.contrib import admin
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from .models import (
    CampoPersonalizado,
    Carpeta,
    CasoDePrueba,
    CicloDePrueba,
    Componente,
    Ejecucion,
    Entorno,
    Estatus,
    Etiqueta,
    PasoDePrueba,
    PlanDePrueba,
    Prioridad,
    Reporte,
)

# La gestión diaria se hace desde la interfaz de CRISTEST; el admin queda como respaldo.


@admin.register(Carpeta)
class CarpetaAdmin(TreeAdmin):
    form = movenodeform_factory(Carpeta, fields=["nombre", "seccion"])
    list_display = ["nombre", "seccion"]
    list_filter = ["seccion"]


class PasoInline(admin.TabularInline):
    model = PasoDePrueba
    extra = 0


@admin.register(CasoDePrueba)
class CasoDePruebaAdmin(admin.ModelAdmin):
    list_display = ["codigo", "titulo", "carpeta", "prioridad", "estatus", "tipo", "asignado"]
    list_filter = ["estatus", "prioridad", "tipo", "componente"]
    search_fields = ["titulo", "objetivo"]
    inlines = [PasoInline]


@admin.register(PlanDePrueba)
class PlanDePruebaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "carpeta", "estatus", "fecha_inicio", "fecha_fin"]
    list_filter = ["estatus"]
    filter_horizontal = ["casos"]


@admin.register(CicloDePrueba)
class CicloDePruebaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "plan", "version", "entorno", "estatus"]
    list_filter = ["estatus", "entorno"]


@admin.register(Ejecucion)
class EjecucionAdmin(admin.ModelAdmin):
    list_display = ["caso", "ciclo", "estatus", "asignado", "fecha_ejecucion"]
    list_filter = ["estatus", "ciclo"]


@admin.register(Estatus)
class EstatusAdmin(admin.ModelAdmin):
    list_display = ["nombre", "ambito", "categoria", "por_defecto", "orden", "activo"]
    list_filter = ["ambito"]


@admin.register(CampoPersonalizado)
class CampoPersonalizadoAdmin(admin.ModelAdmin):
    list_display = ["nombre", "ambito", "tipo", "obligatorio", "activo"]
    list_filter = ["ambito"]


admin.site.register([Entorno, Componente, Etiqueta, Prioridad, Reporte])
