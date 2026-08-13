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
    var submit = form.querySelector(".wpforms-submit-container");
    if (channel) {
      if (box.parentNode !== channel) {
        channel.appendChild(box);
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

  function mountYandex() {
    if (!CLIENT_KEY) return;
    document.querySelectorAll("form.wpforms-form").forEach(function (form) {
      ensureYandexWidget(form);
      ensureTokenInput(form);
    });
    loadYandex(renderYandexWidgets);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountYandex);
  } else {
    mountYandex();
  }
  setTimeout(mountYandex, 800);

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
      submitWithToken(form, submitBtn, yToken);
    },
    true
  );
})();
