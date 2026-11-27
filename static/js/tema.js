/* Alternar modo claro/oscuro y menú lateral en móvil. */
(function () {
  var raiz = document.documentElement;

  function actualizarEtiquetas() {
    var oscuro = raiz.dataset.tema === "oscuro";
    document.querySelectorAll("[data-alternar-tema]").forEach(function (b) {
      b.setAttribute("aria-label", oscuro ? "Cambiar a modo claro" : "Cambiar a modo oscuro");
    });
  }

  document.addEventListener("click", function (e) {
    var botonTema = e.target.closest("[data-alternar-tema]");
    if (botonTema) {
      raiz.dataset.tema = raiz.dataset.tema === "oscuro" ? "claro" : "oscuro";
      try { localStorage.setItem("cristest-tema", raiz.dataset.tema); } catch (err) {}
      actualizarEtiquetas();
      return;
    }
    if (e.target.closest("[data-alternar-menu]")) {
      document.body.classList.toggle("menu-abierto");
      return;
    }
    if (document.body.classList.contains("menu-abierto") && !e.target.closest("#lateral")) {
      document.body.classList.remove("menu-abierto");
    }
  });

  actualizarEtiquetas();
})();
