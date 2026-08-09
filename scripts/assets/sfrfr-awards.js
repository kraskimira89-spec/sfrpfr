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
    var rowEl = root.querySelector("[data-sfrfr-awards-row]");
    var scroller = root.querySelector("[data-sfrfr-awards-scroller]");
    var prevBtn = root.querySelector("[data-sfrfr-awards-prev]");
    var nextBtn = root.querySelector("[data-sfrfr-awards-next]");
    // совместимость со старой разметкой
    var gridEl = root.querySelector("[data-sfrfr-awards-grid]");
    if (!emptyEl) return;
    if (!scroller && gridEl) scroller = gridEl;
    if (!rowEl && scroller) rowEl = scroller.parentElement;

    if (!slides.length) {
      emptyEl.hidden = false;
      if (rowEl) rowEl.hidden = true;
      if (scroller) scroller.hidden = true;
      return;
    }

    emptyEl.hidden = true;
    if (rowEl) rowEl.hidden = false;
    if (scroller) scroller.hidden = false;

    var lightbox = null;
    var lightboxIndex = 0;
    var onLightboxKey = null;

    function closeLightbox() {
      if (!lightbox) return;
      if (onLightboxKey) {
        document.removeEventListener("keydown", onLightboxKey);
        onLightboxKey = null;
      }
      lightbox.remove();
      lightbox = null;
      document.documentElement.classList.remove("sfrfr-awards-lightbox-open");
    }

    function renderLightboxContent() {
      if (!lightbox) return;
      var item = slides[lightboxIndex];
      if (!item) return;
      var label = item.alt || item.title || "Просмотр";
      var caption = escapeHtml(item.title || "");
      if (item.note) caption += (caption ? " · " : "") + escapeHtml(item.note);
      lightbox.setAttribute("aria-label", label);
      var img = lightbox.querySelector(".sfrfr-awards-lightbox__img");
      var cap = lightbox.querySelector(".sfrfr-awards-lightbox__caption");
      var counter = lightbox.querySelector(".sfrfr-awards-lightbox__counter");
      var lbPrev = lightbox.querySelector(".sfrfr-awards-lightbox__nav--prev");
      var lbNext = lightbox.querySelector(".sfrfr-awards-lightbox__nav--next");
      if (img) {
        img.src = item.src;
        img.alt = label;
      }
      if (cap) cap.innerHTML = caption;
      if (counter) {
        counter.textContent = lightboxIndex + 1 + " / " + slides.length;
      }
      if (lbPrev) lbPrev.disabled = lightboxIndex <= 0;
      if (lbNext) lbNext.disabled = lightboxIndex >= slides.length - 1;
    }

    function stepLightbox(delta) {
      var next = lightboxIndex + delta;
      if (next < 0 || next >= slides.length) return;
      lightboxIndex = next;
      renderLightboxContent();
    }

    function openLightbox(i) {
      var item = slides[i];
      if (!item) return;
      closeLightbox();
      lightboxIndex = i;
      lightbox = document.createElement("div");
      lightbox.className = "sfrfr-awards-lightbox";
      lightbox.setAttribute("role", "dialog");
      lightbox.setAttribute("aria-modal", "true");
      lightbox.innerHTML =
        '<button type="button" class="sfrfr-awards-lightbox__close" aria-label="Закрыть">' +
        '<span class="sfrfr-awards-lightbox__close-x" aria-hidden="true">×</span>' +
        '<span class="sfrfr-awards-lightbox__close-text">Закрыть</span>' +
        "</button>" +
        '<div class="sfrfr-awards-lightbox__stage">' +
        '<button type="button" class="sfrfr-awards-lightbox__nav sfrfr-awards-lightbox__nav--prev" aria-label="Предыдущий">‹</button>' +
        '<img class="sfrfr-awards-lightbox__img" src="" alt="" width="480" height="360">' +
        '<button type="button" class="sfrfr-awards-lightbox__nav sfrfr-awards-lightbox__nav--next" aria-label="Следующий">›</button>' +
        "</div>" +
        '<p class="sfrfr-awards-lightbox__caption"></p>' +
        '<p class="sfrfr-awards-lightbox__counter" aria-live="polite"></p>';
      document.body.appendChild(lightbox);
      document.documentElement.classList.add("sfrfr-awards-lightbox-open");
      renderLightboxContent();

      lightbox.addEventListener("click", function (ev) {
        if (ev.target === lightbox) {
          closeLightbox();
          return;
        }
        var closeBtn = ev.target.closest(".sfrfr-awards-lightbox__close");
        if (closeBtn) {
          closeLightbox();
          return;
        }
        var navPrev = ev.target.closest(".sfrfr-awards-lightbox__nav--prev");
        if (navPrev && !navPrev.disabled) {
          stepLightbox(-1);
          return;
        }
        var navNext = ev.target.closest(".sfrfr-awards-lightbox__nav--next");
        if (navNext && !navNext.disabled) {
          stepLightbox(1);
        }
      });

      onLightboxKey = function (ev) {
        if (ev.key === "Escape") {
          closeLightbox();
        } else if (ev.key === "ArrowLeft") {
          stepLightbox(-1);
        } else if (ev.key === "ArrowRight") {
          stepLightbox(1);
        }
      };
      document.addEventListener("keydown", onLightboxKey);
      var focusClose = lightbox.querySelector(".sfrfr-awards-lightbox__close");
      if (focusClose) focusClose.focus();
    }

    if (scroller) {
      scroller.classList.add("sfrfr-awards__scroller");
      scroller.innerHTML = slides
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
            '<span class="sfrfr-awards__name">' +
            title +
            "</span>" +
            (note ? '<span class="sfrfr-awards__note">' + note + "</span>" : "") +
            "</figcaption></figure>"
          );
        })
        .join("");
    }

    function scrollStep() {
      if (!scroller) return 240;
      var card = scroller.querySelector(".sfrfr-awards__card");
      if (!card) return Math.max(200, Math.floor(scroller.clientWidth * 0.8));
      var styles = window.getComputedStyle(scroller);
      var gap = parseFloat(styles.columnGap || styles.gap || "12") || 12;
      return Math.round(card.getBoundingClientRect().width + gap);
    }

    function updateNav() {
      if (!scroller) return;
      var max = scroller.scrollWidth - scroller.clientWidth - 2;
      var left = scroller.scrollLeft;
      if (prevBtn) prevBtn.disabled = left <= 2;
      if (nextBtn) nextBtn.disabled = left >= max;
    }

    if (prevBtn) {
      prevBtn.addEventListener("click", function () {
        scroller.scrollBy({ left: -scrollStep(), behavior: "smooth" });
      });
    }
    if (nextBtn) {
      nextBtn.addEventListener("click", function () {
        scroller.scrollBy({ left: scrollStep(), behavior: "smooth" });
      });
    }
    if (scroller) {
      scroller.addEventListener("scroll", updateNav, { passive: true });
      window.addEventListener("resize", updateNav);
      updateNav();
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
