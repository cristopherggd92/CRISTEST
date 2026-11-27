"""Vistas de gestión: secciones con carpetas, CRUD de casos/planes/ciclos/reportes y ejecución."""

from dataclasses import dataclass

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    FormsetPasos,
    FormularioAgregarCasos,
    FormularioCarpeta,
    FormularioCaso,
    FormularioCiclo,
    FormularioEjecucion,
    FormularioPlan,
    FormularioReporte,
)
from .models import (
    Ambito,
    Carpeta,
    CasoDePrueba,
    CicloDePrueba,
    Ejecucion,
    Estatus,
    PlanDePrueba,
    Reporte,
    Seccion,
    resumen_ejecuciones,
)


@dataclass(frozen=True)
class DefSeccion:
    clave: str
    modelo: type
    formulario: type
    titulo: str
    singular: str
    nuevo: str
    ambito: str | None
    busqueda: tuple


SECCIONES = {
    "casos": DefSeccion(
        "casos", CasoDePrueba, FormularioCaso, "Casos de Prueba", "caso de prueba",
        "Nuevo caso", Ambito.CASO, ("titulo", "objetivo"),
    ),
    "planes": DefSeccion(
        "planes", PlanDePrueba, FormularioPlan, "Planes de Prueba", "plan de prueba",
        "Nuevo plan", Ambito.PLAN, ("nombre", "descripcion"),
    ),
    "ciclos": DefSeccion(
        "ciclos", CicloDePrueba, FormularioCiclo, "Ciclos de Prueba", "ciclo de prueba",
        "Nuevo ciclo", Ambito.CICLO, ("nombre", "descripcion", "version"),
    ),
    "reportes": DefSeccion(
        "reportes", Reporte, FormularioReporte, "Reportes", "reporte",
        "Nuevo reporte", None, ("nombre", "descripcion"),
    ),
}


def _seccion(clave):
    try:
        return SECCIONES[clave]
    except KeyError as exc:
        raise Http404("Sección no encontrada") from exc


def _arbol(seccion):
    """Carpetas de una sección como árbol anidado, con su conteo de elementos."""
    modelo = SECCIONES[seccion].modelo
    conteo = dict(
        modelo.objects.filter(carpeta__isnull=False)
        .values_list("carpeta")
        .annotate(n=Count("id"))
    )
    por_path, raices = {}, []
    for c in Carpeta.objects.filter(seccion=seccion).order_by("path"):
        c.hijos, c.total = [], conteo.get(c.pk, 0)
        por_path[c.path] = c
        padre = por_path.get(c.path[: -Carpeta.steplen])
        (padre.hijos if padre else raices).append(c)
    # Sumar los elementos de las subcarpetas al total de cada carpeta
    def acumular(nodo):
        nodo.total_con_hijos = nodo.total + sum(acumular(h) for h in nodo.hijos)
        return nodo.total_con_hijos

    for r in raices:
        acumular(r)
    return raices


# ---------------------------------------------------------------------------
# Inicio
# ---------------------------------------------------------------------------


@login_required
def inicio(request):
    ejecuciones = Ejecucion.objects.all()
    exito = ejecuciones.filter(estatus__categoria=Estatus.Categoria.EXITO).count()
    ejecutadas = ejecuciones.exclude(
        Q(estatus__isnull=True) | Q(estatus__categoria=Estatus.Categoria.PENDIENTE)
    ).count()
    contexto = {
        "total_casos": CasoDePrueba.objects.count(),
        "total_planes": PlanDePrueba.objects.count(),
        "total_ciclos": CicloDePrueba.objects.count(),
        "porcentaje_exito": round(exito * 100 / ejecutadas) if ejecutadas else None,
        "ciclos_recientes": CicloDePrueba.objects.select_related("plan", "estatus", "entorno")[:5],
        "resumen": resumen_ejecuciones(ejecuciones),
        "total_ejecuciones": ejecuciones.count(),
        "mis_pendientes": Ejecucion.objects.filter(
            asignado=request.user, estatus__categoria=Estatus.Categoria.PENDIENTE
        ).select_related("caso", "ciclo")[:8],
    }
    return render(request, "pruebas/inicio.html", contexto)


# ---------------------------------------------------------------------------
# Listado, detalle, alta, edición y baja
# ---------------------------------------------------------------------------


@login_required
def lista(request, seccion):
    s = _seccion(seccion)
    qs = s.modelo.objects.all()
    carpeta = None
    if request.GET.get("carpeta"):
        carpeta = get_object_or_404(Carpeta, pk=request.GET["carpeta"], seccion=seccion)
        qs = qs.filter(carpeta_id__in=carpeta.ids_subarbol())
    elif request.GET.get("carpeta") == "":
        pass
    if request.GET.get("sin_carpeta"):
        qs = qs.filter(carpeta__isnull=True)

    q = request.GET.get("q", "").strip()
    if q:
        filtro = Q()
        for campo in s.busqueda:
            filtro |= Q(**{f"{campo}__icontains": q})
        if q.upper().startswith(("TC-", "TP-", "CY-")) and q[3:].isdigit():
            filtro |= Q(pk=int(q[3:]))
        qs = qs.filter(filtro)

    filtros = {}
    if s.ambito:
        filtros["estatus"] = Estatus.objects.filter(ambito=s.ambito)
        filtros["usuarios"] = get_user_model().objects.filter(is_active=True).order_by("username")
        if request.GET.get("estatus"):
            qs = qs.filter(estatus_id=request.GET["estatus"])
        if request.GET.get("asignado"):
            qs = qs.filter(asignado_id=request.GET["asignado"])

    if seccion == "casos":
        qs = qs.select_related("carpeta", "estatus", "prioridad", "componente", "asignado")
    elif seccion == "planes":
        qs = qs.select_related("carpeta", "estatus", "asignado").annotate(total_casos=Count("casos"))
    elif seccion == "ciclos":
        qs = qs.select_related("carpeta", "estatus", "plan", "entorno", "asignado")
    else:
        qs = qs.select_related("carpeta", "plan", "ciclo")

    contexto = {
        "s": s,
        "seccion": seccion,
        "arbol": _arbol(seccion),
        "carpeta_actual": carpeta,
        "sin_carpeta": bool(request.GET.get("sin_carpeta")),
        "elementos": qs[:200],
        "total": qs.count(),
        "q": q,
        "filtros": filtros,
        "estatus_sel": request.GET.get("estatus", ""),
        "asignado_sel": request.GET.get("asignado", ""),
    }
    return render(request, f"pruebas/{seccion}/lista.html", contexto)


@login_required
def detalle(request, seccion, pk):
    s = _seccion(seccion)
    obj = get_object_or_404(s.modelo, pk=pk)
    contexto = {"s": s, "seccion": seccion, "obj": obj}
    if seccion == "ciclos":
        contexto["ejecuciones"] = obj.ejecuciones.select_related(
            "caso", "caso__prioridad", "estatus", "asignado"
        )
        contexto["estatus_ejecucion"] = Estatus.objects.filter(ambito=Ambito.EJECUCION, activo=True)
        contexto["resumen"] = obj.resumen()
    elif seccion == "planes":
        contexto["casos"] = obj.casos.select_related("prioridad", "estatus", "carpeta")
        contexto["ciclos"] = obj.ciclos.select_related("estatus", "entorno")
    elif seccion == "reportes":
        contexto["resultados"] = obj.resultados()
        contexto["total"] = sum(f["total"] for f in contexto["resultados"])
    return render(request, f"pruebas/{seccion}/detalle.html", contexto)


def _carpeta_inicial(request, seccion):
    pk = request.GET.get("carpeta")
    if pk and Carpeta.objects.filter(pk=pk, seccion=seccion).exists():
        return int(pk)
    return None


@login_required
def formulario(request, seccion, pk=None):
    s = _seccion(seccion)
    obj = get_object_or_404(s.modelo, pk=pk) if pk else None
    form = s.formulario(
        request.POST or None, instance=obj, carpeta_inicial=_carpeta_inicial(request, seccion)
    )
    pasos = None
    if seccion == "casos":
        pasos = FormsetPasos(request.POST or None, instance=obj or CasoDePrueba(), prefix="pasos")

    if request.method == "POST" and form.is_valid() and (pasos is None or pasos.is_valid()):
        with transaction.atomic():
            nuevo = form.save(commit=False)
            if not nuevo.pk and hasattr(nuevo, "autor_id"):
                nuevo.autor = request.user
            nuevo.save()
            form.save_m2m()
            if pasos is not None:
                pasos.instance = nuevo
                instancias = pasos.save(commit=False)
                for eliminado in pasos.deleted_objects:
                    eliminado.delete()
                for paso in instancias:
                    paso.save()
        messages.success(request, f"Se guardó «{nuevo}».")
        if "guardar_y_nuevo" in request.POST:
            url = reverse("pruebas:nuevo", args=[seccion])
            return redirect(f"{url}?carpeta={nuevo.carpeta_id}" if nuevo.carpeta_id else url)
        return redirect("pruebas:detalle", seccion, nuevo.pk)

    return render(
        request,
        "pruebas/formulario.html",
        {"s": s, "seccion": seccion, "obj": obj, "form": form, "pasos": pasos},
    )


@login_required
def eliminar(request, seccion, pk):
    s = _seccion(seccion)
    obj = get_object_or_404(s.modelo, pk=pk)
    if request.method == "POST":
        nombre = str(obj)
        obj.delete()
        messages.success(request, f"Se eliminó «{nombre}».")
        return redirect("pruebas:lista", seccion)
    return render(
        request,
        "pruebas/confirmar_eliminar.html",
        {"s": s, "seccion": seccion, "obj": obj, "cancelar": reverse("pruebas:detalle", args=[seccion, pk])},
    )


@login_required
@require_POST
def duplicar_caso(request, pk):
    original = get_object_or_404(CasoDePrueba, pk=pk)
    with transaction.atomic():
        etiquetas = list(original.etiquetas.all())
        pasos = list(original.pasos.all())
        copia = original
        copia.pk = None
        copia.id = None
        copia._state.adding = True
        copia.titulo = f"{original.titulo} (copia)"[:200]
        copia.autor = request.user
        copia.save()
        copia.etiquetas.set(etiquetas)
        for p in pasos:
            p.pk = None
            p.caso = copia
            p.save()
    messages.success(request, f"Se creó la copia «{copia}».")
    return redirect("pruebas:editar", "casos", copia.pk)


# ---------------------------------------------------------------------------
# Carpetas
# ---------------------------------------------------------------------------


@login_required
def carpeta_nueva(request, seccion):
    _seccion(seccion)
    padre_inicial = _carpeta_inicial(request, seccion)
    form = FormularioCarpeta(request.POST or None, seccion=seccion, initial={"padre": padre_inicial})
    if request.method == "POST" and form.is_valid():
        datos = {"nombre": form.cleaned_data["nombre"], "seccion": seccion}
        padre_pk = form.cleaned_data["padre"]
        if padre_pk:
            padre = get_object_or_404(Carpeta, pk=padre_pk, seccion=seccion)
            carpeta = Carpeta.objects.add_child(padre, datos)
        else:
            carpeta = Carpeta.objects.add_root(datos)
        messages.success(request, f"Se creó la carpeta «{carpeta.nombre}».")
        return redirect(f"{reverse('pruebas:lista', args=[seccion])}?carpeta={carpeta.pk}")
    return render(
        request,
        "pruebas/carpeta_form.html",
        {"s": SECCIONES[seccion], "seccion": seccion, "form": form, "carpeta": None},
    )


def _mover_carpeta(carpeta, padre_pk):
    """Coloca la carpeta bajo `padre_pk` (o en la raíz) manteniendo el orden alfabético."""
    carpeta.refresh_from_db()
    if padre_pk:
        destino = Carpeta.objects.get(pk=padre_pk, seccion=carpeta.seccion)
        Carpeta.objects.move(carpeta, destino, "sorted-child")
        return
    otra_raiz = Carpeta.objects.get_root_nodes().exclude(pk=carpeta.pk).first()
    if otra_raiz:
        Carpeta.objects.move(carpeta, otra_raiz, "sorted-sibling")


@login_required
def carpeta_editar(request, pk):
    carpeta = get_object_or_404(Carpeta, pk=pk)
    seccion = carpeta.seccion
    padre = Carpeta.objects.get_parent(carpeta)
    form = FormularioCarpeta(
        request.POST or None, seccion=seccion, carpeta=carpeta,
        initial={"nombre": carpeta.nombre, "padre": padre.pk if padre else None},
    )
    if request.method == "POST" and form.is_valid():
        carpeta.nombre = form.cleaned_data["nombre"]
        carpeta.save()
        _mover_carpeta(carpeta, form.cleaned_data["padre"])
        messages.success(request, f"Se actualizó la carpeta «{carpeta.nombre}».")
        return redirect(f"{reverse('pruebas:lista', args=[seccion])}?carpeta={carpeta.pk}")
    return render(
        request,
        "pruebas/carpeta_form.html",
        {"s": SECCIONES[seccion], "seccion": seccion, "form": form, "carpeta": carpeta},
    )


@login_required
def carpeta_eliminar(request, pk):
    carpeta = get_object_or_404(Carpeta, pk=pk)
    seccion = carpeta.seccion
    s = SECCIONES[seccion]
    ids = carpeta.ids_subarbol()
    afectados = s.modelo.objects.filter(carpeta_id__in=ids).count()
    if request.method == "POST":
        nombre = carpeta.nombre
        s.modelo.objects.filter(carpeta_id__in=ids).update(carpeta=None)
        Carpeta.objects.filter(path__startswith=carpeta.path).delete()
        messages.success(
            request,
            f"Se eliminó la carpeta «{nombre}»."
            + (f" {afectados} elemento(s) quedaron sin carpeta." if afectados else ""),
        )
        return redirect("pruebas:lista", seccion)
    return render(
        request,
        "pruebas/confirmar_eliminar.html",
        {
            "s": s,
            "seccion": seccion,
            "obj": carpeta,
            "es_carpeta": True,
            "subcarpetas": len(ids) - 1,
            "afectados": afectados,
            "cancelar": f"{reverse('pruebas:lista', args=[seccion])}?carpeta={carpeta.pk}",
        },
    )


# ---------------------------------------------------------------------------
# Casos dentro de planes y ciclos
# ---------------------------------------------------------------------------


@login_required
def seleccionar_casos(request, seccion, pk):
    """Agrega casos a un plan o a un ciclo."""
    if seccion not in ("planes", "ciclos"):
        raise Http404
    obj = get_object_or_404(SECCIONES[seccion].modelo, pk=pk)
    ya = set(obj.casos.values_list("pk", flat=True))
    form = FormularioAgregarCasos(request.POST or None)
    if request.method == "POST" and form.is_valid():
        casos = [c for c in form.cleaned_data["casos"] if c.pk not in ya]
        if seccion == "planes":
            obj.casos.add(*casos)
            agregados = len(casos)
        else:
            agregados = obj.agregar_casos(casos)
        messages.success(request, f"Se agregaron {agregados} caso(s).")
        return redirect("pruebas:detalle", seccion, pk)

    casos = CasoDePrueba.objects.exclude(pk__in=ya).select_related("carpeta", "prioridad", "estatus")
    q = request.GET.get("q", "").strip()
    if q:
        casos = casos.filter(Q(titulo__icontains=q) | Q(carpeta__nombre__icontains=q))
    return render(
        request,
        "pruebas/seleccionar_casos.html",
        {"s": SECCIONES[seccion], "seccion": seccion, "obj": obj, "casos": casos, "q": q},
    )


@login_required
@require_POST
def quitar_caso(request, seccion, pk, caso_pk):
    if seccion == "planes":
        get_object_or_404(PlanDePrueba, pk=pk).casos.remove(caso_pk)
    elif seccion == "ciclos":
        Ejecucion.objects.filter(ciclo_id=pk, caso_id=caso_pk).delete()
    else:
        raise Http404
    messages.success(request, "Se quitó el caso.")
    return redirect("pruebas:detalle", seccion, pk)


@login_required
@require_POST
def cargar_casos_del_plan(request, pk):
    ciclo = get_object_or_404(CicloDePrueba, pk=pk)
    if not ciclo.plan:
        messages.error(request, "Este ciclo no tiene un plan asociado.")
    else:
        n = ciclo.agregar_casos(ciclo.plan.casos.all())
        messages.success(request, f"Se cargaron {n} caso(s) del plan «{ciclo.plan}».")
    return redirect("pruebas:detalle", "ciclos", pk)


# ---------------------------------------------------------------------------
# Ejecución
# ---------------------------------------------------------------------------


def _registrar_ejecucion(ejecucion, usuario):
    if ejecucion.estatus and ejecucion.estatus.categoria != Estatus.Categoria.PENDIENTE:
        ejecucion.ejecutado_por = usuario
        ejecucion.fecha_ejecucion = timezone.now()
    else:
        ejecucion.ejecutado_por = None
        ejecucion.fecha_ejecucion = None


@login_required
@require_POST
def cambiar_estatus_ejecucion(request, pk):
    """Cambio rápido de estatus desde la tabla del ciclo (HTMX)."""
    ejecucion = get_object_or_404(Ejecucion.objects.select_related("ciclo"), pk=pk)
    estatus = Estatus.objects.filter(
        pk=request.POST.get("estatus"), ambito=Ambito.EJECUCION
    ).first()
    if not estatus:
        return HttpResponseBadRequest("Estatus inválido")
    ejecucion.estatus = estatus
    _registrar_ejecucion(ejecucion, request.user)
    ejecucion.save()
    if request.headers.get("HX-Request"):
        ciclo = ejecucion.ciclo
        return render(
            request,
            "pruebas/ciclos/_resumen.html",
            {"obj": ciclo, "resumen": ciclo.resumen(), "oob": True},
        )
    return redirect("pruebas:detalle", "ciclos", ejecucion.ciclo_id)


@login_required
def ejecutar(request, pk):
    """Pantalla para ejecutar un caso paso a paso dentro de un ciclo."""
    ejecucion = get_object_or_404(
        Ejecucion.objects.select_related("ciclo", "caso", "caso__prioridad"), pk=pk
    )
    form = FormularioEjecucion(request.POST or None, instance=ejecucion)
    if request.method == "POST" and form.is_valid():
        e = form.save(commit=False)
        _registrar_ejecucion(e, request.user)
        e.save()
        messages.success(request, f"Se registró el resultado de {e.caso.codigo}.")
        if "siguiente" in request.POST:
            siguiente = (
                ejecucion.ciclo.ejecuciones.filter(
                    estatus__categoria=Estatus.Categoria.PENDIENTE
                )
                .exclude(pk=e.pk)
                .order_by("caso_id")
                .first()
            )
            if siguiente:
                return redirect("pruebas:ejecutar", siguiente.pk)
        return redirect("pruebas:detalle", "ciclos", ejecucion.ciclo_id)
    return render(
        request,
        "pruebas/ciclos/ejecutar.html",
        {"s": SECCIONES["ciclos"], "seccion": "ciclos", "ejecucion": ejecucion, "form": form},
    )
