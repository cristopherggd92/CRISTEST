"""Vistas del paso 1: panel de inicio y estructura de cada sección.

La gestión completa (crear/editar/eliminar desde la interfaz) llega en el paso 2;
por ahora los datos se administran desde /admin/.
"""

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render

from .models import Carpeta, CasoDePrueba, CicloDePrueba, Ejecucion, PlanDePrueba, Seccion


def _arbol(seccion, relacion):
    """Devuelve las carpetas de una sección como árbol anidado, con su conteo de elementos."""
    carpetas = list(
        Carpeta.objects.filter(seccion=seccion).annotate(total=Count(relacion)).order_by("path")
    )
    por_path = {}
    raices = []
    for c in carpetas:
        c.hijos = []
        por_path[c.path] = c
        padre = por_path.get(c.path[: -Carpeta.steplen])
        (padre.hijos if padre else raices).append(c)
    return raices


@login_required
def inicio(request):
    ejecuciones = Ejecucion.objects.values("estado").annotate(total=Count("id"))
    conteo = {fila["estado"]: fila["total"] for fila in ejecuciones}
    total_ejec = sum(conteo.values())
    ejecutadas = total_ejec - conteo.get(Ejecucion.Estado.NO_EJECUTADO, 0)
    contexto = {
        "total_casos": CasoDePrueba.objects.count(),
        "total_planes": PlanDePrueba.objects.count(),
        "total_ciclos": CicloDePrueba.objects.count(),
        "porcentaje_paso": round(conteo.get(Ejecucion.Estado.PASO, 0) * 100 / ejecutadas)
        if ejecutadas
        else None,
        "ciclos_recientes": CicloDePrueba.objects.select_related("plan")[:5],
    }
    return render(request, "pruebas/inicio.html", contexto)


@login_required
def casos(request):
    contexto = {
        "seccion": Seccion.CASOS,
        "arbol": _arbol(Seccion.CASOS, "casos"),
        "elementos": CasoDePrueba.objects.select_related("carpeta")[:50],
    }
    return render(request, "pruebas/casos.html", contexto)


@login_required
def ciclos(request):
    contexto = {
        "seccion": Seccion.CICLOS,
        "arbol": _arbol(Seccion.CICLOS, "ciclos"),
        "elementos": CicloDePrueba.objects.select_related("carpeta", "plan")[:50],
    }
    return render(request, "pruebas/ciclos.html", contexto)


@login_required
def planes(request):
    contexto = {
        "seccion": Seccion.PLANES,
        "arbol": _arbol(Seccion.PLANES, "planes"),
        "elementos": PlanDePrueba.objects.select_related("carpeta").annotate(
            total_casos=Count("casos")
        )[:50],
    }
    return render(request, "pruebas/planes.html", contexto)


@login_required
def reportes(request):
    return render(request, "pruebas/reportes.html")
