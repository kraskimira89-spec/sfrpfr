/**
 * Captcha для формы лида WPForms.
 * Если clientKey начинается с ysc1_ — Yandex SmartCaptcha, иначе Google reCAPTCHA Enterprise (legacy).
 */
(function () {
  var CLIENT_KEY =
    (window.SFRFR_SMARTCAPTCHA && window.SFRFR_SMARTCAPTCHA.clientKey) ||
    (window.SFRFR_RECAPTCHA && window.SFRFR_RECAPTCHA.siteKey) ||
    "";
  var ACTION =
    (window.SFRFR_RECAPTCHA && window.SFRFR_RECAPTCHA.action) || "lead";
  var IS_YANDEX = String(CLIENT_KEY).indexOf("ysc1_") === 0;

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
    if (typeof form.requestSubmit === "function") {
      form.requestSubmit(submitBtn || undefined);
    } else {
      HTMLFormElement.prototype.submit.call(form);
    }
  }

  /* ---------- Yandex SmartCaptcha ---------- */
  function ensureYandexWidget(form) {
    var existing = form.querySelector(".sfrfr-smartcaptcha-widget");
    if (existing) return existing;
    var box = document.createElement("div");
    box.className = "sfrfr-smartcaptcha-widget smart-captcha";
    box.setAttribute("data-sitekey", CLIENT_KEY);
    box.style.height = "100px";
    box.style.margin = "0.75rem 0";
    var submit = form.querySelector(".wpforms-submit-container");
    if (submit && submit.parentNode) {
      submit.parentNode.insertBefore(box, submit);
    } else {
      form.appendChild(box);
    }
    return box;
  }

  function loadYandex() {
    if (document.getElementById("sfrfr-smartcaptcha-js")) return;
    var script = document.createElement("script");
    script.id = "sfrfr-smartcaptcha-js";
    // URL из консоли YC (alias); docs также допускают smartcaptcha.cloud.yandex.ru
    script.src = "https://smartcaptcha.yandexcloud.net/captcha.js";
    script.defer = true;
    document.head.appendChild(script);
  }

  function readYandexToken(form) {
    var el =
      form.querySelector(".smart-captcha input[name='smart-token']") ||
      form.querySelector("input[name='smart-token']");
    return el && el.value ? String(el.value) : "";
  }

  function mountYandex() {
    if (!CLIENT_KEY || !IS_YANDEX) return;
    document.querySelectorAll("form.wpforms-form").forEach(function (form) {
      ensureYandexWidget(form);
      ensureTokenInput(form);
    });
    loadYandex();
  }

  /* ---------- Google reCAPTCHA Enterprise (legacy) ---------- */
  function loadGoogle() {
    if (document.getElementById("sfrfr-recaptcha-enterprise")) return;
    var script = document.createElement("script");
    script.id = "sfrfr-recaptcha-enterprise";
    script.src =
      "https://www.google.com/recaptcha/enterprise.js?render=" +
      encodeURIComponent(CLIENT_KEY);
    script.async = true;
    document.head.appendChild(script);
  }

  function readyGoogle() {
    loadGoogle();
    return new Promise(function (resolve, reject) {
      var tries = 0;
      (function wait() {
        if (
          window.grecaptcha &&
          window.grecaptcha.enterprise &&
          typeof window.grecaptcha.enterprise.execute === "function"
        ) {
          window.grecaptcha.enterprise.ready(function () {
            resolve();
          });
          return;
        }
        tries += 1;
        if (tries > 80) {
          reject(new Error("reCAPTCHA Enterprise не загрузилась"));
          return;
        }
        setTimeout(wait, 100);
      })();
    });
  }

  if (IS_YANDEX) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", mountYandex);
    } else {
      mountYandex();
    }
    setTimeout(mountYandex, 800);
  } else if (CLIENT_KEY) {
    loadGoogle();
  }

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
      if (!form.querySelector('input[type="checkbox"]:checked')) {
        return;
      }
      if (!CLIENT_KEY) {
        window.alert("Капча не настроена. Обратитесь к администратору.");
        ev.preventDefault();
        return;
      }

      var submitBtn = form.querySelector(".wpforms-submit");

      if (IS_YANDEX) {
        ensureYandexWidget(form);
        var yToken = readYandexToken(form);
        if (!yToken) {
          ev.preventDefault();
          ev.stopPropagation();
          if (typeof ev.stopImmediatePropagation === "function") {
            ev.stopImmediatePropagation();
          }
          window.alert("Отметьте «Я не робот» и при необходимости пройдите проверку.");
          return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        if (typeof ev.stopImmediatePropagation === "function") {
          ev.stopImmediatePropagation();
        }
        if (submitBtn) submitBtn.disabled = true;
        submitWithToken(form, submitBtn, yToken);
        return;
      }

      ev.preventDefault();
      ev.stopPropagation();
      if (typeof ev.stopImmediatePropagation === "function") {
        ev.stopImmediatePropagation();
      }
      if (submitBtn) submitBtn.disabled = true;

      readyGoogle()
        .then(function () {
          return window.grecaptcha.enterprise.execute(CLIENT_KEY, { action: ACTION });
        })
        .then(function (token) {
          submitWithToken(form, submitBtn, token);
        })
        .catch(function () {
          if (submitBtn) submitBtn.disabled = false;
          window.alert(
            "Не удалось проверить форму (капча). Обновите страницу и попробуйте снова."
          );
        });
    },
    true
  );
})();
