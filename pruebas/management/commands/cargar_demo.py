"""Carga datos de ejemplo para explorar CRISTEST: python manage.py cargar_demo"""

import datetime as dt

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from pruebas.models import (
    Ambito, Carpeta, CasoDePrueba, CicloDePrueba, Componente, Entorno, Estatus, Etiqueta,
    PasoDePrueba, PlanDePrueba, Prioridad, Reporte, Seccion,
)


class Command(BaseCommand):
    help = "Carga casos, planes, ciclos y reportes de ejemplo (solo si no hay casos)."

    @transaction.atomic
    def handle(self, *args, **opciones):
        if CasoDePrueba.objects.exists():
            self.stdout.write(self.style.WARNING("Ya hay casos de prueba; no se cargó nada."))
            return

        usuario = get_user_model().objects.filter(is_superuser=True).first()
        p = {x.nombre: x for x in Prioridad.objects.all()}
        ec = {x.nombre: x for x in Estatus.objects.filter(ambito=Ambito.CASO)}
        ee = {x.nombre: x for x in Estatus.objects.filter(ambito=Ambito.EJECUCION)}
        et = {x.nombre: x for x in Etiqueta.objects.all()}
        comp = {n: Componente.objects.get_or_create(nombre=n)[0] for n in ["Autenticación", "Carrito", "Pagos"]}

        def carpeta(nombre, seccion, padre=None):
            datos = {"nombre": nombre, "seccion": seccion}
            return Carpeta.objects.add_child(padre, datos) if padre else Carpeta.objects.add_root(datos)

        login = carpeta("Módulo Login", Seccion.CASOS)
        recuperar = carpeta("Recuperar contraseña", Seccion.CASOS, login)
        compras = carpeta("Compras", Seccion.CASOS)
        carrito = carpeta("Carrito", Seccion.CASOS, compras)
        pagos = carpeta("Pagos", Seccion.CASOS, compras)

        def caso(titulo, carpeta_, prioridad, componente, estatus="Aprobado", tipo="manual", etiquetas=(), pasos=()):
            c = CasoDePrueba.objects.create(
                titulo=titulo, carpeta=carpeta_, prioridad=p[prioridad], componente=comp[componente],
                estatus=ec[estatus], tipo=tipo, autor=usuario, asignado=usuario,
                precondiciones="El usuario está registrado y activo.",
            )
            c.etiquetas.set([et[e] for e in etiquetas])
            for i, (accion, esperado) in enumerate(pasos, 1):
                PasoDePrueba.objects.create(caso=c, orden=i, accion=accion, resultado_esperado=esperado)
            return c

        casos = [
            caso("Iniciar sesión con credenciales válidas", login, "Crítica", "Autenticación", etiquetas=["Smoke"], pasos=[
                ("Abrir la página de inicio de sesión", "Se muestra el formulario"),
                ("Ingresar usuario y contraseña válidos", "Los campos aceptan el texto"),
                ("Presionar «Ingresar»", "Se redirige al inicio con la sesión iniciada"),
            ]),
            caso("Bloqueo tras 3 intentos fallidos", login, "Alta", "Autenticación", etiquetas=["Regresión"], pasos=[
                ("Ingresar una contraseña incorrecta 3 veces", "La cuenta se bloquea y se muestra un aviso"),
            ]),
            caso("Enviar correo de recuperación", recuperar, "Alta", "Autenticación", estatus="En revisión", pasos=[
                ("Ir a «¿Olvidaste tu contraseña?»", "Se muestra el formulario de correo"),
                ("Ingresar el correo registrado y enviar", "Llega un correo con el enlace"),
            ]),
            caso("Agregar producto al carrito", carrito, "Media", "Carrito", tipo="automatizado", etiquetas=["Smoke", "Regresión"], pasos=[
                ("Abrir un producto y presionar «Agregar»", "El contador del carrito aumenta en 1"),
            ]),
            caso("Eliminar producto del carrito", carrito, "Baja", "Carrito", tipo="automatizado"),
            caso("Pagar con tarjeta de crédito", pagos, "Crítica", "Pagos", etiquetas=["Crítico"], pasos=[
                ("Ir al checkout con productos en el carrito", "Se muestra el resumen de compra"),
                ("Capturar una tarjeta de prueba válida", "El pago se aprueba y se muestra el folio"),
            ]),
            caso("Pago rechazado por fondos insuficientes", pagos, "Alta", "Pagos", estatus="Borrador"),
        ]

        planes_c = carpeta("Release 1.0", Seccion.PLANES)
        plan = PlanDePrueba.objects.create(
            nombre="Regresión Release 1.0", carpeta=planes_c, autor=usuario, asignado=usuario,
            descripcion="Regresión completa de login, carrito y pagos antes del release 1.0.",
            fecha_inicio=dt.date(2026, 11, 23), fecha_fin=dt.date(2026, 12, 4),
            estatus=Estatus.objects.get(ambito=Ambito.PLAN, nombre="En progreso"),
        )
        plan.casos.set(casos)

        ciclos_c = carpeta("Sprint 12", Seccion.CICLOS)
        qa = Entorno.objects.get(nombre="QA")
        ciclo1 = CicloDePrueba.objects.create(
            nombre="Smoke 1.0.0-rc1", carpeta=ciclos_c, plan=plan, version="1.0.0-rc1", entorno=qa,
            autor=usuario, asignado=usuario, estatus=Estatus.objects.get(ambito=Ambito.CICLO, nombre="Terminado"),
        )
        ciclo1.agregar_casos(casos[:4])
        for e, r in zip(ciclo1.ejecuciones.order_by("caso_id"), ["Pasó", "Pasó", "Falló", "Pasó"]):
            e.estatus, e.ejecutado_por = ee[r], usuario
            e.save()

        ciclo2 = CicloDePrueba.objects.create(
            nombre="Regresión 1.0.0-rc2", carpeta=ciclos_c, plan=plan, version="1.0.0-rc2", entorno=qa,
            autor=usuario, asignado=usuario, estatus=Estatus.objects.get(ambito=Ambito.CICLO, nombre="En progreso"),
        )
        ciclo2.agregar_casos(casos)
        for e, r in zip(ciclo2.ejecuciones.order_by("caso_id"), ["Pasó", "Pasó", "Pasó", "Bloqueado"]):
            e.estatus, e.ejecutado_por = ee[r], usuario
            e.save()
        ciclo2.ejecuciones.filter(estatus=ee["No ejecutado"]).update(asignado=usuario)

        rep_c = carpeta("Release 1.0", Seccion.REPORTES)
        Reporte.objects.create(nombre="Resultados del ciclo rc2", carpeta=rep_c, tipo="ejecucion", agrupar_por="estatus", ciclo=ciclo2, autor=usuario)
        Reporte.objects.create(nombre="Casos por prioridad", carpeta=rep_c, tipo="casos", agrupar_por="prioridad", autor=usuario)
        Reporte.objects.create(nombre="Casos por componente", tipo="casos", agrupar_por="componente", autor=usuario)

        self.stdout.write(self.style.SUCCESS("Datos de ejemplo cargados."))
