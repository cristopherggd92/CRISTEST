"""Módulo de Configuración: catálogos, estatus y campos personalizados (estilo Zephyr)."""

from dataclasses import dataclass

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from .forms import formulario_config
from .models import Ambito, CampoPersonalizado, Componente, Entorno, Estatus, Etiqueta, Prioridad


@dataclass(frozen=True)
class DefConfig:
    clave: str
    grupo: str
    titulo: str
    modelo: type
    campos: tuple
    columnas: tuple
    ambito: str | None = None
    ayuda: str = ""


_ESTATUS = ("nombre", "descripcion", "color", "categoria", "por_defecto", "orden", "activo")
_CAMPOS = ("nombre", "tipo", "opciones", "obligatorio", "orden", "activo")

CONFIGURACIONES = [
    DefConfig("entornos", "General", "Entornos", Entorno,
              ("nombre", "descripcion", "orden", "activo"), ("nombre", "descripcion", "activo"),
              ayuda="Ambientes donde se ejecutan los ciclos (Dev, QA, UAT, Producción…)."),
    DefConfig("componentes", "General", "Componentes", Componente,
              ("nombre", "descripcion", "orden", "activo"), ("nombre", "descripcion", "activo"),
              ayuda="Módulos o áreas funcionales del sistema bajo prueba."),
    DefConfig("etiquetas", "General", "Etiquetas", Etiqueta,
              ("nombre", "descripcion", "color", "orden", "activo"), ("nombre", "color", "descripcion", "activo")),
    DefConfig("prioridades", "General", "Prioridades", Prioridad,
              ("nombre", "descripcion", "color", "orden", "activo"), ("nombre", "color", "descripcion", "activo")),
    DefConfig("estatus-casos", "Estatus", "Casos de prueba", Estatus, _ESTATUS,
              ("nombre", "color", "categoria", "por_defecto", "activo"), Ambito.CASO),
    DefConfig("estatus-planes", "Estatus", "Planes de prueba", Estatus, _ESTATUS,
              ("nombre", "color", "categoria", "por_defecto", "activo"), Ambito.PLAN),
    DefConfig("estatus-ciclos", "Estatus", "Ciclos de prueba", Estatus, _ESTATUS,
              ("nombre", "color", "categoria", "por_defecto", "activo"), Ambito.CICLO),
    DefConfig("estatus-ejecuciones", "Estatus", "Ejecuciones", Estatus, _ESTATUS,
              ("nombre", "color", "categoria", "por_defecto", "activo"), Ambito.EJECUCION,
              ayuda="La categoría define cómo cuenta cada estatus en las métricas (éxito, fallo, pendiente…)."),
    DefConfig("campos-casos", "Campos personalizados", "Casos de prueba", CampoPersonalizado, _CAMPOS,
              ("nombre", "tipo", "obligatorio", "activo"), Ambito.CASO),
    DefConfig("campos-planes", "Campos personalizados", "Planes de prueba", CampoPersonalizado, _CAMPOS,
              ("nombre", "tipo", "obligatorio", "activo"), Ambito.PLAN),
    DefConfig("campos-ciclos", "Campos personalizados", "Ciclos de prueba", CampoPersonalizado, _CAMPOS,
              ("nombre", "tipo", "obligatorio", "activo"), Ambito.CICLO),
    DefConfig("campos-ejecuciones", "Campos personalizados", "Ejecuciones", CampoPersonalizado, _CAMPOS,
              ("nombre", "tipo", "obligatorio", "activo"), Ambito.EJECUCION),
]
_POR_CLAVE = {c.clave: c for c in CONFIGURACIONES}


def _menu():
    grupos = {}
    for c in CONFIGURACIONES:
        grupos.setdefault(c.grupo, []).append(c)
    return grupos.items()


def _def(clave):
    try:
        return _POR_CLAVE[clave]
    except KeyError as exc:
        raise Http404 from exc


def _qs(d):
    qs = d.modelo.objects.all()
    return qs.filter(ambito=d.ambito) if d.ambito else qs


def _titulo(d):
    return d.titulo if d.grupo == "General" else f"{d.grupo}: {d.titulo}"


@login_required
def inicio(request):
    return redirect("pruebas:config_lista", CONFIGURACIONES[0].clave)


@login_required
def lista(request, clave):
    d = _def(clave)
    elementos = _qs(d)
    filas = []
    for e in elementos:
        celdas = []
        for col in d.columnas:
            valor = getattr(e, col)
            if col in ("color",):
                celdas.append({"tipo": "color", "valor": valor, "texto": e.get_color_display()})
            elif isinstance(valor, bool):
                celdas.append({"tipo": "bool", "valor": valor})
            elif hasattr(e, f"get_{col}_display"):
                celdas.append({"tipo": "texto", "valor": getattr(e, f"get_{col}_display")()})
            else:
                celdas.append({"tipo": "texto", "valor": valor})
        filas.append({"obj": e, "celdas": celdas})
    encabezados = [d.modelo._meta.get_field(c).verbose_name for c in d.columnas]
    return render(request, "pruebas/config/lista.html", {
        "d": d, "menu": _menu(), "titulo": _titulo(d), "filas": filas, "encabezados": encabezados,
    })


@login_required
def formulario(request, clave, pk=None):
    d = _def(clave)
    obj = get_object_or_404(_qs(d), pk=pk) if pk else None
    Form = formulario_config(d.modelo, list(d.campos))
    form = Form(request.POST or None, instance=obj)
    if request.method == "POST":
        if d.ambito:
            form.instance.ambito = d.ambito
        if form.is_valid():
            guardado = form.save()
            messages.success(request, f"Se guardó «{guardado}».")
            return redirect("pruebas:config_lista", clave)
    return render(request, "pruebas/config/formulario.html", {
        "d": d, "menu": _menu(), "titulo": _titulo(d), "form": form, "obj": obj,
    })


@login_required
def eliminar(request, clave, pk):
    d = _def(clave)
    obj = get_object_or_404(_qs(d), pk=pk)
    if request.method == "POST":
        try:
            obj.delete()
            messages.success(request, f"Se eliminó «{obj}».")
        except ProtectedError:
            messages.error(
                request,
                f"No se puede eliminar «{obj}» porque está en uso. Puedes desactivarlo para que ya no aparezca en los formularios.",
            )
        return redirect("pruebas:config_lista", clave)
    return render(request, "pruebas/config/eliminar.html", {
        "d": d, "menu": _menu(), "titulo": _titulo(d), "obj": obj,
    })
