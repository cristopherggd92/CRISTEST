"""Modelo de datos de CRISTEST.

Configuración (administrable desde la sección «Configuración»):
    Entorno, Componente, Etiqueta, Prioridad, Estatus (por ámbito) y CampoPersonalizado

Gestión:
    Carpeta (árbol por sección) ─┬─ CasoDePrueba ── PasoDePrueba
                                 ├─ PlanDePrueba (agrupa casos)
                                 ├─ CicloDePrueba ── Ejecucion (un caso dentro de un ciclo)
                                 └─ Reporte (consulta de métricas guardada)
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from treebeard.mp_tree import MP_Node

# ---------------------------------------------------------------------------
# Catálogos compartidos
# ---------------------------------------------------------------------------


class Ambito(models.TextChoices):
    """Elemento al que aplica un estatus o un campo personalizado."""

    CASO = "caso", "Casos de prueba"
    PLAN = "plan", "Planes de prueba"
    CICLO = "ciclo", "Ciclos de prueba"
    EJECUCION = "ejecucion", "Ejecuciones"


class Seccion(models.TextChoices):
    """Sección que tiene su propio árbol de carpetas."""

    CASOS = "casos", "Casos de Prueba"
    CICLOS = "ciclos", "Ciclos de Prueba"
    PLANES = "planes", "Planes de Prueba"
    REPORTES = "reportes", "Reportes"


class Color(models.TextChoices):
    GRIS = "gris", "Gris"
    AZUL = "azul", "Azul"
    VERDE = "verde", "Verde"
    AMARILLO = "amarillo", "Amarillo"
    NARANJA = "naranja", "Naranja"
    ROJO = "rojo", "Rojo"
    MORADO = "morado", "Morado"


class Auditoria(models.Model):
    creado = models.DateTimeField("creado", auto_now_add=True)
    actualizado = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------


class ElementoConfig(models.Model):
    """Base para los catálogos simples de configuración."""

    nombre = models.CharField("nombre", max_length=80)
    descripcion = models.CharField("descripción", max_length=200, blank=True)
    orden = models.PositiveIntegerField("orden", default=0)
    activo = models.BooleanField("activo", default=True)

    class Meta:
        abstract = True
        ordering = ["orden", "nombre"]

    def __str__(self):
        return self.nombre


class Entorno(ElementoConfig):
    class Meta(ElementoConfig.Meta):
        verbose_name = "entorno"
        verbose_name_plural = "entornos"


class Componente(ElementoConfig):
    class Meta(ElementoConfig.Meta):
        verbose_name = "componente"
        verbose_name_plural = "componentes"


class Etiqueta(ElementoConfig):
    color = models.CharField("color", max_length=10, choices=Color.choices, default=Color.AZUL)

    class Meta(ElementoConfig.Meta):
        verbose_name = "etiqueta"
        verbose_name_plural = "etiquetas"


class Prioridad(ElementoConfig):
    color = models.CharField("color", max_length=10, choices=Color.choices, default=Color.GRIS)

    class Meta(ElementoConfig.Meta):
        verbose_name = "prioridad"
        verbose_name_plural = "prioridades"


class Estatus(ElementoConfig):
    """Estatus configurable para casos, planes, ciclos o ejecuciones."""

    class Categoria(models.TextChoices):
        """Significado del estatus para las métricas."""

        PENDIENTE = "pendiente", "Pendiente / sin ejecutar"
        EN_PROGRESO = "en_progreso", "En progreso"
        EXITO = "exito", "Éxito / terminado"
        FALLO = "fallo", "Fallo"
        BLOQUEADO = "bloqueado", "Bloqueado"
        OTRO = "otro", "Otro"

    ambito = models.CharField("aplica a", max_length=10, choices=Ambito.choices)
    color = models.CharField("color", max_length=10, choices=Color.choices, default=Color.GRIS)
    categoria = models.CharField(
        "categoría", max_length=12, choices=Categoria.choices, default=Categoria.OTRO
    )
    por_defecto = models.BooleanField(
        "por defecto", default=False, help_text="Se asigna automáticamente a los nuevos registros."
    )

    class Meta(ElementoConfig.Meta):
        verbose_name = "estatus"
        verbose_name_plural = "estatus"
        ordering = ["ambito", "orden", "nombre"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.por_defecto:
            Estatus.objects.filter(ambito=self.ambito, por_defecto=True).exclude(pk=self.pk).update(
                por_defecto=False
            )

    @classmethod
    def predeterminado(cls, ambito):
        activos = cls.objects.filter(ambito=ambito, activo=True)
        return activos.filter(por_defecto=True).first() or activos.first()


class CampoPersonalizado(models.Model):
    """Campo adicional que aparece en el formulario de casos, planes, ciclos o ejecuciones."""

    class Tipo(models.TextChoices):
        TEXTO = "texto", "Texto corto"
        TEXTO_LARGO = "texto_largo", "Texto largo"
        NUMERO = "numero", "Número"
        FECHA = "fecha", "Fecha"
        LISTA = "lista", "Lista de opciones"
        CASILLA = "casilla", "Casilla (sí/no)"

    nombre = models.CharField("nombre", max_length=80)
    ambito = models.CharField("aplica a", max_length=10, choices=Ambito.choices)
    tipo = models.CharField("tipo", max_length=12, choices=Tipo.choices, default=Tipo.TEXTO)
    opciones = models.TextField(
        "opciones", blank=True, help_text="Solo para «Lista de opciones». Una opción por línea."
    )
    obligatorio = models.BooleanField("obligatorio", default=False)
    orden = models.PositiveIntegerField("orden", default=0)
    activo = models.BooleanField("activo", default=True)

    class Meta:
        verbose_name = "campo personalizado"
        verbose_name_plural = "campos personalizados"
        ordering = ["ambito", "orden", "nombre"]

    def __str__(self):
        return self.nombre

    @property
    def clave(self):
        return f"campo_{self.pk}"

    @property
    def lista_opciones(self):
        return [o.strip() for o in self.opciones.splitlines() if o.strip()]

    def clean(self):
        if self.tipo == self.Tipo.LISTA and not self.lista_opciones:
            raise ValidationError({"opciones": "Agrega al menos una opción para la lista."})


# ---------------------------------------------------------------------------
# Carpetas
# ---------------------------------------------------------------------------


class Carpeta(MP_Node):
    """Carpeta anidable. Cada sección tiene su propio árbol de carpetas."""

    nombre = models.CharField("nombre", max_length=120)
    seccion = models.CharField("sección", max_length=10, choices=Seccion.choices)
    creado = models.DateTimeField("creado", auto_now_add=True)
    actualizado = models.DateTimeField("actualizado", auto_now=True)

    node_order_by = ["nombre"]

    class Meta:
        verbose_name = "carpeta"
        verbose_name_plural = "carpetas"

    def __str__(self):
        return self.ruta

    @property
    def ruta(self):
        """Ruta legible, p. ej. «Login / Recuperar contraseña»."""
        nombres = [c.nombre for c in Carpeta.objects.get_ancestors(self)] + [self.nombre]
        return " / ".join(nombres)

    def ids_subarbol(self):
        """Ids de esta carpeta y todas sus subcarpetas."""
        return list(
            Carpeta.objects.filter(path__startswith=self.path, seccion=self.seccion).values_list(
                "id", flat=True
            )
        )


def _validar_carpeta(carpeta, seccion, errores):
    if carpeta is not None and carpeta.seccion != seccion:
        errores["carpeta"] = f"La carpeta debe pertenecer a la sección «{Seccion(seccion).label}»."


def _validar_estatus(estatus, ambito, errores):
    if estatus is not None and estatus.ambito != ambito:
        errores["estatus"] = f"El estatus debe ser de «{Ambito(ambito).label}»."


def _validar_fechas(obj, errores):
    if obj.fecha_inicio and obj.fecha_fin and obj.fecha_fin < obj.fecha_inicio:
        errores["fecha_fin"] = "La fecha de fin no puede ser anterior a la de inicio."


# ---------------------------------------------------------------------------
# Elementos de prueba
# ---------------------------------------------------------------------------


class ElementoDePrueba(Auditoria):
    """Campos comunes de casos, planes y ciclos."""

    AMBITO = None
    SECCION = None

    carpeta = models.ForeignKey(
        Carpeta, verbose_name="carpeta", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )
    estatus = models.ForeignKey(
        Estatus, verbose_name="estatus", on_delete=models.PROTECT, null=True, blank=True,
        related_name="+",
    )
    asignado = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="asignado a", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="autor", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )
    campos_extra = models.JSONField("campos personalizados", default=dict, blank=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.estatus_id is None:
            self.estatus = Estatus.predeterminado(self.AMBITO)
        super().save(*args, **kwargs)

    def clean(self):
        errores = {}
        _validar_carpeta(self.carpeta, self.SECCION, errores)
        _validar_estatus(self.estatus, self.AMBITO, errores)
        if hasattr(self, "fecha_inicio"):
            _validar_fechas(self, errores)
        if errores:
            raise ValidationError(errores)

    def valores_personalizados(self):
        """Lista de (campo, valor) para mostrar en el detalle."""
        campos = CampoPersonalizado.objects.filter(ambito=self.AMBITO, activo=True)
        return [(c, self.campos_extra.get(c.clave)) for c in campos]


class CasoDePrueba(ElementoDePrueba):
    AMBITO = Ambito.CASO
    SECCION = Seccion.CASOS

    class Tipo(models.TextChoices):
        MANUAL = "manual", "Manual"
        AUTOMATIZADO = "automatizado", "Automatizado"

    titulo = models.CharField("título", max_length=200)
    objetivo = models.TextField("objetivo", blank=True)
    precondiciones = models.TextField("precondiciones", blank=True)
    prioridad = models.ForeignKey(
        Prioridad, verbose_name="prioridad", on_delete=models.PROTECT, null=True, blank=True,
        related_name="casos",
    )
    componente = models.ForeignKey(
        Componente, verbose_name="componente", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="casos",
    )
    etiquetas = models.ManyToManyField(Etiqueta, verbose_name="etiquetas", blank=True, related_name="casos")
    tipo = models.CharField("tipo", max_length=15, choices=Tipo.choices, default=Tipo.MANUAL)

    class Meta:
        verbose_name = "caso de prueba"
        verbose_name_plural = "casos de prueba"
        ordering = ["id"]

    def __str__(self):
        return f"{self.codigo} · {self.titulo}"

    @property
    def codigo(self):
        return f"TC-{self.pk:04d}" if self.pk else "TC-nuevo"


class PasoDePrueba(models.Model):
    caso = models.ForeignKey(CasoDePrueba, verbose_name="caso", on_delete=models.CASCADE, related_name="pasos")
    orden = models.PositiveIntegerField("orden", default=1)
    accion = models.TextField("acción")
    datos = models.TextField("datos de prueba", blank=True)
    resultado_esperado = models.TextField("resultado esperado")

    class Meta:
        verbose_name = "paso"
        verbose_name_plural = "pasos"
        ordering = ["orden", "id"]

    def __str__(self):
        return f"Paso {self.orden}"


class PlanDePrueba(ElementoDePrueba):
    AMBITO = Ambito.PLAN
    SECCION = Seccion.PLANES

    nombre = models.CharField("nombre", max_length=200)
    descripcion = models.TextField("descripción / alcance", blank=True)
    casos = models.ManyToManyField(CasoDePrueba, verbose_name="casos", blank=True, related_name="planes")
    etiquetas = models.ManyToManyField(Etiqueta, verbose_name="etiquetas", blank=True, related_name="planes")
    fecha_inicio = models.DateField("fecha de inicio", null=True, blank=True)
    fecha_fin = models.DateField("fecha de fin", null=True, blank=True)

    class Meta:
        verbose_name = "plan de prueba"
        verbose_name_plural = "planes de prueba"
        ordering = ["-creado"]

    def __str__(self):
        return self.nombre

    @property
    def codigo(self):
        return f"TP-{self.pk:04d}" if self.pk else "TP-nuevo"


class CicloDePrueba(ElementoDePrueba):
    AMBITO = Ambito.CICLO
    SECCION = Seccion.CICLOS

    nombre = models.CharField("nombre", max_length=200)
    descripcion = models.TextField("descripción", blank=True)
    plan = models.ForeignKey(
        PlanDePrueba, verbose_name="plan", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ciclos",
    )
    version = models.CharField("versión / build", max_length=60, blank=True)
    entorno = models.ForeignKey(
        Entorno, verbose_name="entorno", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ciclos",
    )
    fecha_inicio = models.DateField("fecha de inicio", null=True, blank=True)
    fecha_fin = models.DateField("fecha de fin", null=True, blank=True)
    casos = models.ManyToManyField(
        CasoDePrueba, through="Ejecucion", verbose_name="casos", blank=True, related_name="ciclos"
    )

    class Meta:
        verbose_name = "ciclo de prueba"
        verbose_name_plural = "ciclos de prueba"
        ordering = ["-creado"]

    def __str__(self):
        return self.nombre

    @property
    def codigo(self):
        return f"CY-{self.pk:04d}" if self.pk else "CY-nuevo"

    def resumen(self):
        """Ejecuciones agrupadas por estatus: [{'estatus': Estatus|None, 'total': n}, ...]."""
        return resumen_ejecuciones(self.ejecuciones.all())

    @property
    def progreso(self):
        """Porcentaje de casos ejecutados (estatus cuya categoría no es «pendiente»)."""
        total = self.ejecuciones.count()
        if not total:
            return 0
        pendientes = self.ejecuciones.filter(
            models.Q(estatus__isnull=True) | models.Q(estatus__categoria=Estatus.Categoria.PENDIENTE)
        ).count()
        return round((total - pendientes) * 100 / total)

    def agregar_casos(self, casos):
        """Agrega casos al ciclo sin duplicar. Devuelve cuántos se agregaron."""
        existentes = set(self.ejecuciones.values_list("caso_id", flat=True))
        estatus = Estatus.predeterminado(Ambito.EJECUCION)
        nuevas = [
            Ejecucion(ciclo=self, caso=c, estatus=estatus) for c in casos if c.pk not in existentes
        ]
        Ejecucion.objects.bulk_create(nuevas)
        return len(nuevas)


class Ejecucion(models.Model):
    """Resultado de un caso de prueba dentro de un ciclo."""

    ciclo = models.ForeignKey(CicloDePrueba, verbose_name="ciclo", on_delete=models.CASCADE, related_name="ejecuciones")
    caso = models.ForeignKey(CasoDePrueba, verbose_name="caso", on_delete=models.CASCADE, related_name="ejecuciones")
    estatus = models.ForeignKey(
        Estatus, verbose_name="estatus", on_delete=models.PROTECT, null=True, blank=True,
        related_name="+", limit_choices_to={"ambito": Ambito.EJECUCION},
    )
    asignado = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="asignado a", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )
    comentario = models.TextField("comentario", blank=True)
    ejecutado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="ejecutado por", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )
    fecha_ejecucion = models.DateTimeField("fecha de ejecución", null=True, blank=True)
    campos_extra = models.JSONField("campos personalizados", default=dict, blank=True)

    class Meta:
        verbose_name = "ejecución"
        verbose_name_plural = "ejecuciones"
        ordering = ["ciclo", "caso"]
        constraints = [
            models.UniqueConstraint(fields=["ciclo", "caso"], name="ejecucion_unica_por_ciclo"),
        ]

    def __str__(self):
        return f"{self.caso.codigo} en {self.ciclo}"

    def save(self, *args, **kwargs):
        if self.estatus_id is None:
            self.estatus = Estatus.predeterminado(Ambito.EJECUCION)
        super().save(*args, **kwargs)


def resumen_ejecuciones(ejecuciones):
    """Agrupa un queryset de ejecuciones por estatus, en el orden configurado."""
    filas = ejecuciones.values("estatus").annotate(total=models.Count("id"))
    totales = {f["estatus"]: f["total"] for f in filas}
    resultado = [
        {"estatus": e, "total": totales.pop(e.pk, 0)}
        for e in Estatus.objects.filter(ambito=Ambito.EJECUCION)
    ]
    if totales.get(None):
        resultado.append({"estatus": None, "total": totales[None]})
    return resultado


# ---------------------------------------------------------------------------
# Reportes
# ---------------------------------------------------------------------------


class Reporte(Auditoria):
    """Consulta de métricas guardada, con sus filtros."""

    class Tipo(models.TextChoices):
        EJECUCION = "ejecucion", "Resultados de ejecución"
        CASOS = "casos", "Distribución de casos de prueba"

    class AgruparPor(models.TextChoices):
        ESTATUS = "estatus", "Estatus"
        PRIORIDAD = "prioridad", "Prioridad"
        COMPONENTE = "componente", "Componente"
        ASIGNADO = "asignado", "Asignado a"
        TIPO = "tipo", "Tipo (manual/automatizado)"
        CICLO = "ciclo", "Ciclo (solo ejecución)"

    nombre = models.CharField("nombre", max_length=200)
    descripcion = models.TextField("descripción", blank=True)
    carpeta = models.ForeignKey(
        Carpeta, verbose_name="carpeta", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )
    tipo = models.CharField("tipo de reporte", max_length=10, choices=Tipo.choices, default=Tipo.EJECUCION)
    agrupar_por = models.CharField("agrupar por", max_length=12, choices=AgruparPor.choices, default=AgruparPor.ESTATUS)
    plan = models.ForeignKey(PlanDePrueba, verbose_name="plan", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    ciclo = models.ForeignKey(CicloDePrueba, verbose_name="ciclo", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    entorno = models.ForeignKey(Entorno, verbose_name="entorno", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    componente = models.ForeignKey(Componente, verbose_name="componente", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="autor", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )

    class Meta:
        verbose_name = "reporte"
        verbose_name_plural = "reportes"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def clean(self):
        errores = {}
        _validar_carpeta(self.carpeta, Seccion.REPORTES, errores)
        if self.tipo == self.Tipo.CASOS and self.agrupar_por == self.AgruparPor.CICLO:
            errores["agrupar_por"] = "«Ciclo» solo aplica a reportes de resultados de ejecución."
        if errores:
            raise ValidationError(errores)

    def resultados(self):
        """Filas [{'etiqueta', 'color', 'total', 'porcentaje'}] según tipo, filtros y agrupación."""
        if self.tipo == self.Tipo.EJECUCION:
            qs = Ejecucion.objects.all()
            pref = "caso__"
            if self.ciclo_id:
                qs = qs.filter(ciclo=self.ciclo)
            if self.plan_id:
                qs = qs.filter(ciclo__plan=self.plan)
            if self.entorno_id:
                qs = qs.filter(ciclo__entorno=self.entorno)
        else:
            qs = CasoDePrueba.objects.all()
            pref = ""
            if self.plan_id:
                qs = qs.filter(planes=self.plan)
            if self.ciclo_id:
                qs = qs.filter(ejecuciones__ciclo=self.ciclo)
            if self.entorno_id:
                qs = qs.filter(ejecuciones__ciclo__entorno=self.entorno).distinct()
        if self.componente_id:
            qs = qs.filter(**{f"{pref}componente": self.componente})

        g = self.agrupar_por
        if g == self.AgruparPor.ESTATUS:
            campo, etiqueta, color = "estatus", "estatus__nombre", "estatus__color"
        elif g == self.AgruparPor.PRIORIDAD:
            campo, etiqueta, color = f"{pref}prioridad", f"{pref}prioridad__nombre", f"{pref}prioridad__color"
        elif g == self.AgruparPor.COMPONENTE:
            campo, etiqueta, color = f"{pref}componente", f"{pref}componente__nombre", None
        elif g == self.AgruparPor.ASIGNADO:
            campo, etiqueta, color = "asignado", "asignado__username", None
        elif g == self.AgruparPor.TIPO:
            campo, etiqueta, color = f"{pref}tipo", f"{pref}tipo", None
        else:
            campo, etiqueta, color = "ciclo", "ciclo__nombre", None

        valores = [etiqueta] + ([color] if color else [])
        filas = list(qs.values(campo, *valores).annotate(total=models.Count("id", distinct=True)).order_by("-total"))
        total = sum(f["total"] for f in filas) or 1
        etiquetas_tipo = dict(CasoDePrueba.Tipo.choices)
        resultado = []
        for f in filas:
            texto = f[etiqueta]
            if g == self.AgruparPor.TIPO:
                texto = etiquetas_tipo.get(texto, texto)
            resultado.append(
                {
                    "etiqueta": texto or "Sin asignar",
                    "color": (f.get(color) if color else None) or "azul",
                    "total": f["total"],
                    "porcentaje": round(f["total"] * 100 / total),
                }
            )
        return resultado
