/* CRISTEST: tema claro/oscuro, menú hamburguesa y utilidades de formularios. */
(function () {
  var raiz = document.documentElement;
  var MOVIL = window.matchMedia("(max-width: 760px)");

  function guardar(clave, valor) {
    try { localStorage.setItem(clave, valor); } catch (err) {}
  }

  function actualizarEtiquetasTema() {
    var oscuro = raiz.dataset.tema === "oscuro";
    document.querySelectorAll("[data-alternar-tema]").forEach(function (b) {
      b.setAttribute("aria-label", oscuro ? "Cambiar a modo claro" : "Cambiar a modo oscuro");
    });
  }

  function menuVisible() {
    return MOVIL.matches ? document.body.classList.contains("menu-abierto") : !raiz.classList.contains("menu-oculto");
  }

  function actualizarBotonMenu() {
    document.querySelectorAll("[data-alternar-menu]").forEach(function (b) {
      b.setAttribute("aria-expanded", menuVisible() ? "true" : "false");
    });
  }

  function alternarMenu() {
    if (MOVIL.matches) {
      document.body.classList.toggle("menu-abierto");
    } else {
      raiz.classList.toggle("menu-oculto");
      guardar("cristest-menu", raiz.classList.contains("menu-oculto") ? "oculto" : "visible");
    }
    actualizarBotonMenu();
  }

  /* --- Pasos del caso de prueba --- */
  function renumerarPasos(lista) {
    var n = 0;
    lista.querySelectorAll(".paso-form").forEach(function (li) {
      var borrado = li.querySelector('input[name$="-DELETE"]');
      li.classList.toggle("eliminado", !!(borrado && borrado.checked));
      if (borrado && borrado.checked) return;
      n += 1;
      li.querySelector(".paso-numero").textContent = n;
      var orden = li.querySelector("[data-orden]");
      if (orden) orden.value = n;
    });
    var vacio = document.querySelector("[data-sin-pasos]");
    if (vacio) vacio.hidden = n > 0;
  }

  function agregarPaso() {
    var lista = document.getElementById("lista-pasos");
    var plantilla = document.getElementById("plantilla-paso");
    var total = document.querySelector('input[name="pasos-TOTAL_FORMS"]');
    if (!lista || !plantilla || !total) return;
    var indice = parseInt(total.value, 10);
    var html = plantilla.innerHTML.replace(/__prefix__/g, String(indice));
    lista.insertAdjacentHTML("beforeend", html);
    total.value = indice + 1;
    renumerarPasos(lista);
    var nuevo = lista.lastElementChild.querySelector("textarea");
    if (nuevo) nuevo.focus();
  }

  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-alternar-tema]")) {
      raiz.dataset.tema = raiz.dataset.tema === "oscuro" ? "claro" : "oscuro";
      guardar("cristest-tema", raiz.dataset.tema);
      actualizarEtiquetasTema();
      return;
    }
    if (e.target.closest("[data-alternar-menu]")) { alternarMenu(); return; }
    if (e.target.closest("[data-cerrar-menu]")) {
      document.body.classList.remove("menu-abierto");
      actualizarBotonMenu();
      return;
    }
    if (e.target.closest("[data-agregar-paso]")) { agregarPaso(); return; }
    var mover = e.target.closest("[data-mover-paso]");
    if (mover) {
      var li = mover.closest(".paso-form");
      if (mover.dataset.moverPaso === "-1" && li.previousElementSibling) {
        li.parentNode.insertBefore(li, li.previousElementSibling);
      } else if (mover.dataset.moverPaso === "1" && li.nextElementSibling) {
        li.parentNode.insertBefore(li.nextElementSibling, li);
      }
      renumerarPasos(li.parentNode);
    }
  });

  document.addEventListener("change", function (e) {
    if (e.target.matches('.paso-form input[name$="-DELETE"]')) {
      renumerarPasos(document.getElementById("lista-pasos"));
    }
    if (e.target.matches("[data-marcar-todos]")) {
      e.target.closest("table").querySelectorAll('tbody input[type="checkbox"]').forEach(function (c) {
        c.checked = e.target.checked;
      });
    }
    if (e.target.matches(".selector-estatus")) {
      var colores = {};
      (e.target.dataset.colores || "").split(",").forEach(function (par) {
        var p = par.split(":"); colores[p[0]] = p[1];
      });
      e.target.className = e.target.className.replace(/\bcolor-\w+/g, "").trim() + " color-" + (colores[e.target.value] || "gris");
    }
  });

  /* Antes de enviar: pasos nuevos que quedaron vacíos se descartan. */
  document.addEventListener("submit", function (e) {
    var lista = e.target.querySelector("#lista-pasos");
    if (!lista) return;
    lista.querySelectorAll(".paso-form").forEach(function (li) {
      var id = li.querySelector('input[name$="-id"]');
      var textos = Array.prototype.map.call(li.querySelectorAll("textarea"), function (t) { return t.value.trim(); });
      var borrado = li.querySelector('input[name$="-DELETE"]');
      if (id && !id.value && textos.join("") === "" && borrado) borrado.checked = true;
    });
    renumerarPasos(lista);
  });

  MOVIL.addEventListener("change", function () {
    document.body.classList.remove("menu-abierto");
    actualizarBotonMenu();
  });

  var lista = document.getElementById("lista-pasos");
  if (lista) renumerarPasos(lista);
  actualizarEtiquetasTema();
  actualizarBotonMenu();
})();
