(function () {
  "use strict";

  function parseSlides() {
    var node = document.getElementById("sfrfr-awards-data");
    if (!node) return [];
    try {
      var data = JSON.parse(node.textContent || "[]");
      return Array.isArray(data) ? data : [];
    } catch (e) {
      return [];
    }
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function initRoot(root) {
    var slides = parseSlides().filter(function (item) {
      return item && item.src && item.alt;
    });
    var emptyEl = root.querySelector("[data-sfrfr-awards-empty]");
    var sliderEl = root.querySelector("[data-sfrfr-awards-slider]");
    var track = root.querySelector("[data-sfrfr-awards-track]");
    var viewport = root.querySelector("[data-sfrfr-awards-viewport]");
    var prevBtn = root.querySelector("[data-sfrfr-awards-prev]");
    var nextBtn = root.querySelector("[data-sfrfr-awards-next]");
    var indicator = root.querySelector("[data-sfrfr-awards-indicator]");
    if (!emptyEl || !sliderEl || !track) return;

    if (!slides.length) {
      emptyEl.hidden = false;
      sliderEl.hidden = true;
      return;
    }

    emptyEl.hidden = true;
    sliderEl.hidden = false;
    var index = 0;

    track.innerHTML = slides
      .map(function (item, i) {
        var title = escapeHtml(item.title || "Материал");
        var year = item.year != null && item.year !== "" ? escapeHtml(item.year) : "";
        var note = escapeHtml(item.note || "");
        var alt = escapeHtml(item.alt);
        var src = escapeHtml(item.src);
        var srcset = item.srcset ? ' srcset="' + escapeHtml(item.srcset) + '"' : "";
        var sizes = item.sizes ? ' sizes="' + escapeHtml(item.sizes) + '"' : ' sizes="(max-width: 720px) 100vw, 560px"';
        return (
          '<article class="sfrfr-awards__slide" data-sfrfr-awards-slide="' +
          i +
          '" aria-hidden="' +
          (i === 0 ? "false" : "true") +
          '">' +
          '<button type="button" class="sfrfr-awards__media" data-sfrfr-awards-zoom data-index="' +
          i +
          '" aria-label="Увеличить: ' +
          alt +
          '">' +
          '<img src="' +
          src +
          '"' +
          srcset +
          sizes +
          ' alt="' +
          alt +
          '" width="560" height="400" loading="lazy" decoding="async">' +
          "</button>" +
          '<div class="sfrfr-awards__meta">' +
          "<p class=\"sfrfr-awards__name\">" +
          title +
          (year ? " · " + year : "") +
          "</p>" +
          (note ? '<p class="sfrfr-awards__note">' + note + "</p>" : "") +
          "</div></article>"
        );
      })
      .join("");

    function render() {
      var kids = track.querySelectorAll("[data-sfrfr-awards-slide]");
      kids.forEach(function (el, i) {
        var on = i === index;
        el.classList.toggle("is-active", on);
        el.setAttribute("aria-hidden", on ? "false" : "true");
      });
      track.style.transform = "translateX(-" + index * 100 + "%)";
      if (indicator) {
        indicator.textContent = index + 1 + " / " + slides.length;
      }
      if (prevBtn) prevBtn.disabled = slides.length < 2;
      if (nextBtn) nextBtn.disabled = slides.length < 2;
    }

    function go(delta) {
      if (slides.length < 2) return;
      index = (index + delta + slides.length) % slides.length;
      render();
    }

    if (prevBtn) prevBtn.addEventListener("click", function () { go(-1); });
    if (nextBtn) nextBtn.addEventListener("click", function () { go(1); });

    var touchX = null;
    var surface = viewport || track;
    surface.addEventListener(
      "touchstart",
      function (ev) {
        if (!ev.changedTouches || !ev.changedTouches[0]) return;
        touchX = ev.changedTouches[0].clientX;
      },
      { passive: true }
    );
    surface.addEventListener(
      "touchend",
      function (ev) {
        if (touchX == null || !ev.changedTouches || !ev.changedTouches[0]) return;
        var dx = ev.changedTouches[0].clientX - touchX;
        touchX = null;
        if (Math.abs(dx) < 40) return;
        go(dx < 0 ? 1 : -1);
      },
      { passive: true }
    );

    var lightbox = null;
    function closeLightbox() {
      if (!lightbox) return;
      lightbox.remove();
      lightbox = null;
      document.documentElement.classList.remove("sfrfr-awards-lightbox-open");
    }

    function openLightbox(i) {
      var item = slides[i];
      if (!item) return;
      closeLightbox();
      lightbox = document.createElement("div");
      lightbox.className = "sfrfr-awards-lightbox";
      lightbox.setAttribute("role", "dialog");
      lightbox.setAttribute("aria-modal", "true");
      lightbox.setAttribute("aria-label", item.alt || item.title || "Просмотр");
      lightbox.innerHTML =
        '<button type="button" class="sfrfr-awards-lightbox__close" aria-label="Закрыть">×</button>' +
        '<img src="' +
        escapeHtml(item.src) +
        '" alt="' +
        escapeHtml(item.alt) +
        '">' +
        '<p class="sfrfr-awards-lightbox__caption">' +
        escapeHtml(item.title || "") +
        (item.year ? " · " + escapeHtml(item.year) : "") +
        "</p>";
      document.body.appendChild(lightbox);
      document.documentElement.classList.add("sfrfr-awards-lightbox-open");
      lightbox.addEventListener("click", function (ev) {
        if (ev.target === lightbox || ev.target.classList.contains("sfrfr-awards-lightbox__close")) {
          closeLightbox();
        }
      });
      document.addEventListener(
        "keydown",
        function onKey(ev) {
          if (ev.key === "Escape") {
            document.removeEventListener("keydown", onKey);
            closeLightbox();
          }
        }
      );
    }

    root.addEventListener("click", function (ev) {
      var btn = ev.target.closest("[data-sfrfr-awards-zoom]");
      if (!btn || !root.contains(btn)) return;
      var i = parseInt(btn.getAttribute("data-index") || "", 10);
      if (!isNaN(i)) openLightbox(i);
    });

    render();
  }

  function boot() {
    document.querySelectorAll("[data-sfrfr-awards]").forEach(initRoot);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
