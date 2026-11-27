"""Modelo de datos de CRISTEST.

Jerarquía principal:
    Carpeta (árbol por sección) ─┬─ CasoDePrueba ── PasoDePrueba
                                 ├─ PlanDePrueba (agrupa casos)
                                 └─ CicloDePrueba ── Ejecucion (un caso dentro de un ciclo)
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from treebeard.mp_tree import MP_Node


class Seccion(models.TextChoices):
    CASOS = "casos", "Casos de Prueba"
    CICLOS = "ciclos", "Ciclos de Prueba"
    PLANES = "planes", "Planes de Prueba"


class Auditoria(models.Model):
    """Campos de auditoría comunes."""

    creado = models.DateTimeField("creado", auto_now_add=True)
    actualizado = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        abstract = True


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

    def clean(self):
        padre = Carpeta.objects.get_parent(self) if self.pk and self.depth > 1 else None
        if padre and padre.seccion != self.seccion:
            raise ValidationError(
                {"seccion": "Una subcarpeta debe pertenecer a la misma sección que su carpeta padre."}
            )


def _validar_carpeta(carpeta, seccion, errores):
    if carpeta is not None and carpeta.seccion != seccion:
        errores["carpeta"] = (
            f"La carpeta debe pertenecer a la sección «{Seccion(seccion).label}»."
        )


class CasoDePrueba(Auditoria):
    class Prioridad(models.TextChoices):
        BAJA = "baja", "Baja"
        MEDIA = "media", "Media"
        ALTA = "alta", "Alta"
        CRITICA = "critica", "Crítica"

    class Tipo(models.TextChoices):
        MANUAL = "manual", "Manual"
        AUTOMATIZADO = "automatizado", "Automatizado"

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        LISTO = "listo", "Listo"
        OBSOLETO = "obsoleto", "Obsoleto"

    titulo = models.CharField("título", max_length=200)
    descripcion = models.TextField("descripción", blank=True)
    precondiciones = models.TextField("precondiciones", blank=True)
    carpeta = models.ForeignKey(
        Carpeta,
        verbose_name="carpeta",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="casos",
        limit_choices_to={"seccion": Seccion.CASOS},
    )
    prioridad = models.CharField(
        "prioridad", max_length=10, choices=Prioridad.choices, default=Prioridad.MEDIA
    )
    tipo = models.CharField("tipo", max_length=15, choices=Tipo.choices, default=Tipo.MANUAL)
    estado = models.CharField(
        "estado", max_length=10, choices=Estado.choices, default=Estado.BORRADOR
    )
    etiquetas = models.CharField(
        "etiquetas", max_length=200, blank=True, help_text="Separadas por comas."
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="autor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="casos_creados",
    )

    class Meta:
        verbose_name = "caso de prueba"
        verbose_name_plural = "casos de prueba"
        ordering = ["id"]

    def __str__(self):
        return f"{self.codigo} · {self.titulo}"

    @property
    def codigo(self):
        return f"TC-{self.pk:04d}" if self.pk else "TC-nuevo"

    @property
    def lista_etiquetas(self):
        return [e.strip() for e in self.etiquetas.split(",") if e.strip()]

    def clean(self):
        errores = {}
        _validar_carpeta(self.carpeta, Seccion.CASOS, errores)
        if errores:
            raise ValidationError(errores)


class PasoDePrueba(models.Model):
    caso = models.ForeignKey(
        CasoDePrueba, verbose_name="caso", on_delete=models.CASCADE, related_name="pasos"
    )
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


class PlanDePrueba(Auditoria):
    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        CERRADO = "cerrado", "Cerrado"

    nombre = models.CharField("nombre", max_length=200)
    descripcion = models.TextField("descripción / alcance", blank=True)
    carpeta = models.ForeignKey(
        Carpeta,
        verbose_name="carpeta",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planes",
        limit_choices_to={"seccion": Seccion.PLANES},
    )
    casos = models.ManyToManyField(
        CasoDePrueba, verbose_name="casos", blank=True, related_name="planes"
    )
    estado = models.CharField(
        "estado", max_length=10, choices=Estado.choices, default=Estado.ACTIVO
    )
    fecha_inicio = models.DateField("fecha de inicio", null=True, blank=True)
    fecha_fin = models.DateField("fecha de fin", null=True, blank=True)
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="autor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planes_creados",
    )

    class Meta:
        verbose_name = "plan de prueba"
        verbose_name_plural = "planes de prueba"
        ordering = ["-creado"]

    def __str__(self):
        return self.nombre

    def clean(self):
        errores = {}
        _validar_carpeta(self.carpeta, Seccion.PLANES, errores)
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            errores["fecha_fin"] = "La fecha de fin no puede ser anterior a la de inicio."
        if errores:
            raise ValidationError(errores)


class CicloDePrueba(Auditoria):
    class Estado(models.TextChoices):
        PLANIFICADO = "planificado", "Planificado"
        EN_PROGRESO = "en_progreso", "En progreso"
        COMPLETADO = "completado", "Completado"

    nombre = models.CharField("nombre", max_length=200)
    descripcion = models.TextField("descripción", blank=True)
    carpeta = models.ForeignKey(
        Carpeta,
        verbose_name="carpeta",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ciclos",
        limit_choices_to={"seccion": Seccion.CICLOS},
    )
    plan = models.ForeignKey(
        PlanDePrueba,
        verbose_name="plan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ciclos",
    )
    version = models.CharField("versión / build", max_length=60, blank=True)
    entorno = models.CharField(
        "entorno", max_length=60, blank=True, help_text="Ej.: QA, Staging, Producción."
    )
    estado = models.CharField(
        "estado", max_length=12, choices=Estado.choices, default=Estado.PLANIFICADO
    )
    fecha_inicio = models.DateField("fecha de inicio", null=True, blank=True)
    fecha_fin = models.DateField("fecha de fin", null=True, blank=True)
    casos = models.ManyToManyField(
        CasoDePrueba,
        through="Ejecucion",
        verbose_name="casos",
        blank=True,
        related_name="ciclos",
    )

    class Meta:
        verbose_name = "ciclo de prueba"
        verbose_name_plural = "ciclos de prueba"
        ordering = ["-creado"]

    def __str__(self):
        return self.nombre

    def clean(self):
        errores = {}
        _validar_carpeta(self.carpeta, Seccion.CICLOS, errores)
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            errores["fecha_fin"] = "La fecha de fin no puede ser anterior a la de inicio."
        if errores:
            raise ValidationError(errores)

    def resumen(self):
        """Conteo de ejecuciones por estado, p. ej. {'paso': 3, 'fallo': 1, ...}."""
        conteo = {estado: 0 for estado in Ejecucion.Estado.values}
        for fila in self.ejecuciones.values("estado").annotate(total=models.Count("id")):
            conteo[fila["estado"]] = fila["total"]
        return conteo

    @property
    def progreso(self):
        """Porcentaje de casos ya ejecutados (cualquier estado distinto de «No ejecutado»)."""
        total = self.ejecuciones.count()
        if not total:
            return 0
        ejecutados = self.ejecuciones.exclude(estado=Ejecucion.Estado.NO_EJECUTADO).count()
        return round(ejecutados * 100 / total)


class Ejecucion(models.Model):
    """Resultado de un caso de prueba dentro de un ciclo."""

    class Estado(models.TextChoices):
        NO_EJECUTADO = "no_ejecutado", "No ejecutado"
        PASO = "paso", "Pasó"
        FALLO = "fallo", "Falló"
        BLOQUEADO = "bloqueado", "Bloqueado"
        OMITIDO = "omitido", "Omitido"

    ciclo = models.ForeignKey(
        CicloDePrueba, verbose_name="ciclo", on_delete=models.CASCADE, related_name="ejecuciones"
    )
    caso = models.ForeignKey(
        CasoDePrueba, verbose_name="caso", on_delete=models.CASCADE, related_name="ejecuciones"
    )
    estado = models.CharField(
        "estado", max_length=12, choices=Estado.choices, default=Estado.NO_EJECUTADO
    )
    comentario = models.TextField("comentario", blank=True)
    ejecutado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ejecutado por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ejecuciones",
    )
    fecha_ejecucion = models.DateTimeField("fecha de ejecución", null=True, blank=True)

    class Meta:
        verbose_name = "ejecución"
        verbose_name_plural = "ejecuciones"
        ordering = ["ciclo", "caso"]
        constraints = [
            models.UniqueConstraint(fields=["ciclo", "caso"], name="ejecucion_unica_por_ciclo"),
        ]

    def __str__(self):
        return f"{self.caso.codigo} en {self.ciclo} · {self.get_estado_display()}"
