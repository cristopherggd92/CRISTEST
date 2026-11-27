from django import forms
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory

from .models import (
    Ambito,
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
    Seccion,
)


class SelectorUsuario(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.get_full_name() or obj.get_username()


def _usuarios():
    return get_user_model().objects.filter(is_active=True).order_by("username")


def _opciones_carpeta(seccion):
    """Carpetas de la sección con sangría según su nivel."""
    return [("", "— Sin carpeta —")] + [
        (c.pk, " " * (c.depth - 1) + c.nombre)
        for c in Carpeta.objects.filter(seccion=seccion).order_by("path")
    ]


class CampoCarpeta(forms.TypedChoiceField):
    def __init__(self, seccion, **kwargs):
        super().__init__(
            choices=_opciones_carpeta(seccion), coerce=int, empty_value=None, required=False,
            label="Carpeta", **kwargs,
        )


class CamposPersonalizadosMixin:
    """Agrega al formulario los campos personalizados activos del ámbito y los guarda en `campos_extra`."""

    ambito = None

    def _agregar_campos_personalizados(self):
        self.campos_personalizados = list(
            CampoPersonalizado.objects.filter(ambito=self.ambito, activo=True)
        )
        extra = getattr(self.instance, "campos_extra", None) or {}
        T = CampoPersonalizado.Tipo
        for campo in self.campos_personalizados:
            comunes = {"label": campo.nombre, "required": campo.obligatorio}
            if campo.tipo == T.TEXTO:
                f = forms.CharField(max_length=255, **comunes)
            elif campo.tipo == T.TEXTO_LARGO:
                f = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), **comunes)
            elif campo.tipo == T.NUMERO:
                f = forms.DecimalField(**comunes)
            elif campo.tipo == T.FECHA:
                f = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), **comunes)
            elif campo.tipo == T.LISTA:
                f = forms.ChoiceField(
                    choices=[("", "—")] + [(o, o) for o in campo.lista_opciones], **comunes
                )
            else:
                f = forms.BooleanField(label=campo.nombre, required=False)
            f.initial = extra.get(campo.clave)
            f.personalizado = True
            self.fields[campo.clave] = f

    def _guardar_campos_personalizados(self, instancia):
        extra = dict(instancia.campos_extra or {})
        for campo in self.campos_personalizados:
            valor = self.cleaned_data.get(campo.clave)
            if valor in (None, ""):
                extra.pop(campo.clave, None)
            else:
                extra[campo.clave] = str(valor) if not isinstance(valor, bool) else valor
        instancia.campos_extra = extra

    def campos_base(self):
        return [c for c in self if not getattr(c.field, "personalizado", False)]

    def campos_extra_visibles(self):
        return [c for c in self if getattr(c.field, "personalizado", False)]


class FormularioElemento(CamposPersonalizadosMixin, forms.ModelForm):
    """Base de los formularios de casos, planes y ciclos."""

    seccion = None

    def __init__(self, *args, carpeta_inicial=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["carpeta"] = CampoCarpeta(self.seccion)
        if not self.instance.pk and carpeta_inicial:
            self.initial["carpeta"] = carpeta_inicial
        if "estatus" in self.fields:
            self.fields["estatus"].queryset = Estatus.objects.filter(ambito=self.ambito, activo=True)
            self.fields["estatus"].empty_label = "— Por defecto —"
        if "asignado" in self.fields:
            self.fields["asignado"] = SelectorUsuario(
                _usuarios(), required=False, label="Asignado a", empty_label="— Sin asignar —",
                initial=self.instance.asignado_id,
            )
        if "etiquetas" in self.fields:
            self.fields["etiquetas"].queryset = Etiqueta.objects.filter(activo=True)
            self.fields["etiquetas"].widget = forms.CheckboxSelectMultiple()
            self.fields["etiquetas"].widget.choices = self.fields["etiquetas"].choices
        self._agregar_campos_personalizados()

    def clean_carpeta(self):
        pk = self.cleaned_data.get("carpeta")
        return Carpeta.objects.get(pk=pk) if pk else None

    def save(self, commit=True):
        instancia = super().save(commit=False)
        self._guardar_campos_personalizados(instancia)
        if commit:
            instancia.save()
            self.save_m2m()
        return instancia


_fecha = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class FormularioCaso(FormularioElemento):
    ambito = Ambito.CASO
    seccion = Seccion.CASOS

    class Meta:
        model = CasoDePrueba
        fields = [
            "titulo", "carpeta", "objetivo", "precondiciones", "estatus", "prioridad",
            "componente", "tipo", "asignado", "etiquetas",
        ]
        widgets = {
            "objetivo": forms.Textarea(attrs={"rows": 3}),
            "precondiciones": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["prioridad"].queryset = Prioridad.objects.filter(activo=True)
        self.fields["componente"].queryset = Componente.objects.filter(activo=True)
        self.fields["prioridad"].empty_label = "— Sin prioridad —"
        self.fields["componente"].empty_label = "— Sin componente —"


FormsetPasos = inlineformset_factory(
    CasoDePrueba,
    PasoDePrueba,
    fields=["orden", "accion", "datos", "resultado_esperado"],
    extra=0,
    can_delete=True,
    widgets={
        "orden": forms.HiddenInput(attrs={"data-orden": ""}),
        "accion": forms.Textarea(attrs={"rows": 2}),
        "datos": forms.Textarea(attrs={"rows": 2}),
        "resultado_esperado": forms.Textarea(attrs={"rows": 2}),
    },
)


class FormularioPlan(FormularioElemento):
    ambito = Ambito.PLAN
    seccion = Seccion.PLANES

    class Meta:
        model = PlanDePrueba
        fields = [
            "nombre", "carpeta", "descripcion", "estatus", "asignado", "fecha_inicio",
            "fecha_fin", "etiquetas",
        ]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 3}),
            "fecha_inicio": _fecha,
            "fecha_fin": _fecha,
        }


class FormularioCiclo(FormularioElemento):
    ambito = Ambito.CICLO
    seccion = Seccion.CICLOS

    class Meta:
        model = CicloDePrueba
        fields = [
            "nombre", "carpeta", "descripcion", "plan", "version", "entorno", "estatus",
            "asignado", "fecha_inicio", "fecha_fin",
        ]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 3}),
            "fecha_inicio": _fecha,
            "fecha_fin": _fecha,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["entorno"].queryset = Entorno.objects.filter(activo=True)
        self.fields["entorno"].empty_label = "— Sin entorno —"
        self.fields["plan"].empty_label = "— Sin plan —"


class FormularioEjecucion(CamposPersonalizadosMixin, forms.ModelForm):
    ambito = Ambito.EJECUCION

    class Meta:
        model = Ejecucion
        fields = ["estatus", "asignado", "comentario"]
        widgets = {"comentario": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estatus"].queryset = Estatus.objects.filter(ambito=Ambito.EJECUCION, activo=True)
        self.fields["estatus"].required = True
        self.fields["asignado"] = SelectorUsuario(
            _usuarios(), required=False, label="Asignado a", empty_label="— Sin asignar —",
            initial=self.instance.asignado_id,
        )
        self._agregar_campos_personalizados()

    def save(self, commit=True):
        instancia = super().save(commit=False)
        self._guardar_campos_personalizados(instancia)
        if commit:
            instancia.save()
        return instancia


class FormularioReporte(forms.ModelForm):
    class Meta:
        model = Reporte
        fields = [
            "nombre", "carpeta", "descripcion", "tipo", "agrupar_por", "plan", "ciclo",
            "entorno", "componente",
        ]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, carpeta_inicial=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["carpeta"] = CampoCarpeta(Seccion.REPORTES)
        if not self.instance.pk and carpeta_inicial:
            self.initial["carpeta"] = carpeta_inicial
        for nombre in ["plan", "ciclo", "entorno", "componente"]:
            self.fields[nombre].empty_label = "— Todos —"

    def clean_carpeta(self):
        pk = self.cleaned_data.get("carpeta")
        return Carpeta.objects.get(pk=pk) if pk else None

    def campos_base(self):
        return list(self)

    def campos_extra_visibles(self):
        return []


class FormularioCarpeta(forms.Form):
    nombre = forms.CharField(label="Nombre", max_length=120)
    padre = forms.TypedChoiceField(label="Dentro de", coerce=int, empty_value=None, required=False)

    def __init__(self, *args, seccion, carpeta=None, **kwargs):
        super().__init__(*args, **kwargs)
        excluir = set(carpeta.ids_subarbol()) if carpeta else set()
        self.fields["padre"].choices = [("", "— Raíz —")] + [
            (c.pk, " " * (c.depth - 1) + c.nombre)
            for c in Carpeta.objects.filter(seccion=seccion).order_by("path")
            if c.pk not in excluir
        ]


class FormularioAgregarCasos(forms.Form):
    casos = forms.ModelMultipleChoiceField(
        queryset=CasoDePrueba.objects.all(), widget=forms.CheckboxSelectMultiple, required=False,
        label="Casos",
    )


# --- Configuración -----------------------------------------------------------

def formulario_config(modelo, campos):
    widgets = {}
    if "opciones" in campos:
        widgets["opciones"] = forms.Textarea(attrs={"rows": 3})
    return forms.modelform_factory(modelo, fields=campos, widgets=widgets)
