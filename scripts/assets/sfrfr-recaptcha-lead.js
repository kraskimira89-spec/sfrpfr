/**
 * Yandex SmartCaptcha для формы лида WPForms.
 */
(function () {
  var CLIENT_KEY =
    (window.SFRFR_SMARTCAPTCHA && window.SFRFR_SMARTCAPTCHA.clientKey) || "";

  function findTokenInput(form) {
    return (
      form.querySelector('input[name*="smartcaptcha_token"]') ||
      form.querySelector('input[name*="recaptcha_token"]') ||
      form.querySelector('input[name*="[fields][4]"]') ||
      form.querySelector(".sfrfr-recaptcha-token input") ||
      form.querySelector('input[type="hidden"][data-sfrfr-captcha]')
    );
  }

  function ensureTokenInput(form) {
    var el = findTokenInput(form);
    if (el) return el;
    el = document.createElement("input");
    el.type = "hidden";
    el.name = "wpforms[fields][4]";
    el.setAttribute("data-sfrfr-captcha", "1");
    form.appendChild(el);
    return el;
  }

  function submitWithToken(form, submitBtn, token) {
    var input = ensureTokenInput(form);
    input.value = token || "";
    form.setAttribute("data-sfrfr-captcha-ok", "1");
    // Нельзя requestSubmit(disabledBtn) — InvalidStateError, кнопка «молчит».
    if (submitBtn) submitBtn.disabled = false;
    try {
      if (typeof form.requestSubmit === "function") {
        form.requestSubmit(submitBtn && !submitBtn.disabled ? submitBtn : undefined);
      } else {
        HTMLFormElement.prototype.submit.call(form);
      }
    } catch (err) {
      form.removeAttribute("data-sfrfr-captcha-ok");
      if (submitBtn) submitBtn.disabled = false;
      window.alert("Не удалось отправить форму. Обновите страницу и попробуйте снова.");
    }
  }

  /* ---------- Yandex SmartCaptcha ---------- */
  function ensureYandexWidget(form) {
    var box = form.querySelector(".sfrfr-smartcaptcha-widget");
    if (!box) {
      box = document.createElement("div");
      box.className = "sfrfr-smartcaptcha-widget smart-captcha";
      box.setAttribute("data-sitekey", CLIENT_KEY);
      box.style.height = "100px";
    }
    var channel =
      form.querySelector(".sfrfr-lead-channel") ||
      form.querySelector(".wpforms-field-radio");
    var consent = form.querySelector(".sfrfr-lead-consent");
    var marketing = form.querySelector(".sfrfr-lead-marketing-consent");
    var submit = form.querySelector(".wpforms-submit-container");
    if (channel) {
      if (box.parentNode !== channel) {
        channel.appendChild(box);
      }
      if (consent && consent.parentNode !== channel) {
        channel.appendChild(consent);
      }
      if (marketing && marketing.parentNode !== channel) {
        channel.appendChild(marketing);
      }
    } else if (submit && submit.parentNode) {
      submit.parentNode.insertBefore(box, submit);
    } else {
      form.appendChild(box);
    }
    return box;
  }

  function loadYandex(onReady) {
    if (window.smartCaptcha && typeof window.smartCaptcha.render === "function") {
      if (typeof onReady === "function") onReady();
      return;
    }
    var existing = document.getElementById("sfrfr-smartcaptcha-js");
    if (existing) {
      if (typeof onReady === "function") {
        existing.addEventListener("load", onReady);
        // на случай, если скрипт уже успел загрузиться
        setTimeout(function () {
          if (window.smartCaptcha && typeof onReady === "function") onReady();
        }, 50);
      }
      return;
    }
    var script = document.createElement("script");
    script.id = "sfrfr-smartcaptcha-js";
    // URL из консоли YC (alias); docs также допускают smartcaptcha.cloud.yandex.ru
    script.src = "https://smartcaptcha.cloud.yandex.ru/captcha.js";
    script.async = true;
    if (typeof onReady === "function") {
      script.addEventListener("load", onReady);
    }
    document.head.appendChild(script);
  }

  function readYandexToken(form) {
    var el =
      form.querySelector(".smart-captcha input[name='smart-token']") ||
      form.querySelector("input[name='smart-token']") ||
      form.querySelector(".sfrfr-smartcaptcha-widget input[type='hidden']");
    return el && el.value ? String(el.value) : "";
  }

  function renderYandexWidgets() {
    if (!window.smartCaptcha || typeof window.smartCaptcha.render !== "function") {
      return;
    }
    document.querySelectorAll(".sfrfr-smartcaptcha-widget").forEach(function (box) {
      if (box.getAttribute("data-sfrfr-rendered") === "1") return;
      if (!box.id) {
        box.id = "sfrfr-smartcaptcha-" + Math.random().toString(36).slice(2, 10);
      }
      try {
        window.smartCaptcha.render(box.id, { sitekey: CLIENT_KEY });
        box.setAttribute("data-sfrfr-rendered", "1");
      } catch (err) {
        // уже отрисовано авто-инициализацией captcha.js
        box.setAttribute("data-sfrfr-rendered", "1");
      }
    });
  }

  function linkConsentLabel() {
    document
      .querySelectorAll(".sfrfr-lead-consent .wpforms-field-label-inline")
      .forEach(function (label) {
      if (label.querySelector("a")) return;
      var a = document.createElement("a");
      a.href = "/soglasie/";
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.className = "sfrfr-consent-link";
      a.textContent = "Даю согласие на обработку персональных данных*";
      a.addEventListener("click", function (ev) {
        ev.stopPropagation();
      });
      label.textContent = "";
      label.appendChild(a);
    });
    document.querySelectorAll(".sfrfr-lead-consent .wpforms-field-description").forEach(function (el) {
      el.remove();
    });
  }

  function hasPdnConsent(form) {
    var pdn = form.querySelector(".sfrfr-lead-consent input[type='checkbox']");
    if (pdn) return !!pdn.checked;
    // Партнёрская / старая разметка без класса — первый обязательный checkbox.
    var required = form.querySelector(
      ".wpforms-field-checkbox input[type='checkbox'][required], .wpforms-field-checkbox input[type='checkbox'][aria-required='true']"
    );
    return required ? !!required.checked : true;
  }

  function warnNeedConsent(form) {
    var msg = "Отметьте «Даю согласие на обработку персональных данных», чтобы отправить заявку.";
    var box =
      form.querySelector(".sfrfr-lead-consent") ||
      form.querySelector(".wpforms-field-checkbox");
    var prev = form.querySelector(".sfrfr-consent-warn");
    if (prev) prev.remove();
    if (box) {
      var warn = document.createElement("p");
      warn.className = "sfrfr-consent-warn";
      warn.setAttribute("role", "alert");
      warn.textContent = msg;
      box.appendChild(warn);
      try {
        box.scrollIntoView({ behavior: "smooth", block: "center" });
      } catch (e) {}
    }
    window.alert(msg);
  }

  function moveConsentIntoChannel() {
    document.querySelectorAll("form.wpforms-form").forEach(function (form) {
      var channel =
        form.querySelector(".sfrfr-lead-channel") ||
        form.querySelector(".wpforms-field-radio");
      var consent = form.querySelector(".sfrfr-lead-consent");
      var marketing = form.querySelector(".sfrfr-lead-marketing-consent");
      if (channel && consent && consent.parentNode !== channel) {
        channel.appendChild(consent);
      }
      if (channel && marketing && marketing.parentNode !== channel) {
        channel.appendChild(marketing);
      }
    });
  }

  function mountYandex() {
    document.querySelectorAll("form.wpforms-form").forEach(function (form) {
      if (CLIENT_KEY) {
        ensureYandexWidget(form);
        ensureTokenInput(form);
      } else {
        moveConsentIntoChannel();
      }
    });
    if (CLIENT_KEY) {
      loadYandex(renderYandexWidgets);
    }
  }

  function bootLeadForm() {
    linkConsentLabel();
    moveConsentIntoChannel();
    mountYandex();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootLeadForm);
  } else {
    bootLeadForm();
  }
  setTimeout(bootLeadForm, 800);

  document.addEventListener(
    "submit",
    function (ev) {
      var form = ev.target;
      if (!form || !form.classList || !form.classList.contains("wpforms-form")) {
        return;
      }
      if (form.getAttribute("data-sfrfr-captcha-ok") === "1") {
        return;
      }

      function stopSubmit() {
        ev.preventDefault();
        ev.stopPropagation();
        if (typeof ev.stopImmediatePropagation === "function") {
          ev.stopImmediatePropagation();
        }
      }

      if (!hasPdnConsent(form)) {
        stopSubmit();
        warnNeedConsent(form);
        return;
      }

      var warnEl = form.querySelector(".sfrfr-consent-warn");
      if (warnEl) warnEl.remove();

      if (!CLIENT_KEY) {
        stopSubmit();
        window.alert("Капча не настроена. Обратитесь к администратору.");
        return;
      }

      var submitBtn = form.querySelector(".wpforms-submit");

      ensureYandexWidget(form);
      var yToken = readYandexToken(form);
      if (!yToken) {
        stopSubmit();
        window.alert("Отметьте «Я не робот» и при необходимости пройдите проверку.");
        return;
      }
      stopSubmit();
      submitWithToken(form, submitBtn, yToken);
    },
    true
  );
})();
