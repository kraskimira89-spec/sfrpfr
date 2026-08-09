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
      return item && item.src && (item.alt || item.title);
    });
    var emptyEl = root.querySelector("[data-sfrfr-awards-empty]");
    var gridEl = root.querySelector("[data-sfrfr-awards-grid]");
    var sliderEl = root.querySelector("[data-sfrfr-awards-slider]");
    if (!emptyEl) return;

    if (!slides.length) {
      emptyEl.hidden = false;
      if (gridEl) gridEl.hidden = true;
      if (sliderEl) sliderEl.hidden = true;
      return;
    }

    emptyEl.hidden = true;
    if (sliderEl) sliderEl.hidden = true;

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
      var label = item.alt || item.title || "Просмотр";
      lightbox.setAttribute("aria-label", label);
      var caption = escapeHtml(item.title || "");
      if (item.note) caption += (caption ? " · " : "") + escapeHtml(item.note);
      lightbox.innerHTML =
        '<button type="button" class="sfrfr-awards-lightbox__close" aria-label="Закрыть">×</button>' +
        '<img src="' +
        escapeHtml(item.src) +
        '" alt="' +
        escapeHtml(label) +
        '" width="480" height="360">' +
        '<p class="sfrfr-awards-lightbox__caption">' +
        caption +
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

    if (gridEl) {
      gridEl.hidden = false;
      gridEl.innerHTML = slides
        .map(function (item, i) {
          var title = escapeHtml(item.title || "Награда");
          var alt = escapeHtml(item.alt || item.title || "Награда");
          var note = escapeHtml(item.note || "");
          var src = escapeHtml(item.src);
          return (
            '<figure class="sfrfr-awards__card">' +
            '<button type="button" class="sfrfr-awards__thumb" data-sfrfr-awards-zoom data-index="' +
            i +
            '" aria-label="Увеличить: ' +
            alt +
            '">' +
            '<img src="' +
            src +
            '" alt="' +
            alt +
            '" width="480" height="360" loading="lazy" decoding="async">' +
            "</button>" +
            '<figcaption class="sfrfr-awards__cap">' +
            "<span class=\"sfrfr-awards__name\">" +
            title +
            "</span>" +
            (note ? '<span class="sfrfr-awards__note">' + note + "</span>" : "") +
            "</figcaption></figure>"
          );
        })
        .join("");
    }

    root.addEventListener("click", function (ev) {
      var btn = ev.target.closest("[data-sfrfr-awards-zoom]");
      if (!btn || !root.contains(btn)) return;
      var i = parseInt(btn.getAttribute("data-index") || "", 10);
      if (!isNaN(i)) openLightbox(i);
    });
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
