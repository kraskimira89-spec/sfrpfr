/**
 * Yandex SmartCaptcha для формы лида WPForms.
 * Токен уходит в поле формы и далее как smartcaptcha_token / recaptcha_token на API.
 */
(function () {
  var CLIENT_KEY =
    (window.SFRFR_SMARTCAPTCHA && window.SFRFR_SMARTCAPTCHA.clientKey) ||
    (window.SFRFR_RECAPTCHA && window.SFRFR_RECAPTCHA.siteKey) ||
    "";
  var SCRIPT_ID = "sfrfr-smartcaptcha-js";
  var WIDGET_CLASS = "sfrfr-smartcaptcha-widget";

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
    el.className = "sfrfr-captcha-token-input";
    form.appendChild(el);
    return el;
  }

  function readWidgetToken(form) {
    var fromWidget =
      form.querySelector(".smart-captcha input[name='smart-token']") ||
      form.querySelector("input[name='smart-token']");
    return fromWidget && fromWidget.value ? String(fromWidget.value) : "";
  }

  function ensureWidget(form) {
    if (!CLIENT_KEY) return null;
    var existing = form.querySelector("." + WIDGET_CLASS);
    if (existing) return existing;
    var box = document.createElement("div");
    box.className = WIDGET_CLASS + " smart-captcha";
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

  function loadScript() {
    if (document.getElementById(SCRIPT_ID)) return;
    var script = document.createElement("script");
    script.id = SCRIPT_ID;
    script.src = "https://smartcaptcha.cloud.yandex.ru/captcha.js";
    script.defer = true;
    document.head.appendChild(script);
  }

  function readySmartCaptcha() {
    loadScript();
    return new Promise(function (resolve, reject) {
      var tries = 0;
      (function wait() {
        if (window.smartCaptcha && typeof window.smartCaptcha.render === "function") {
          resolve();
          return;
        }
        // auto-mount mode: script loaded and widgets present
        if (document.getElementById(SCRIPT_ID) && document.querySelector(".smart-captcha iframe")) {
          resolve();
          return;
        }
        tries += 1;
        if (tries > 100) {
          reject(new Error("Yandex SmartCaptcha не загрузилась"));
          return;
        }
        setTimeout(wait, 100);
      })();
    });
  }

  function mountWidgets() {
    if (!CLIENT_KEY) return;
    document.querySelectorAll("form.wpforms-form").forEach(function (form) {
      ensureWidget(form);
      ensureTokenInput(form);
    });
    loadScript();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountWidgets);
  } else {
    mountWidgets();
  }
  // WPForms иногда перерисовывает форму
  setTimeout(mountWidgets, 800);

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
        window.alert(
          "Капча не настроена (нет клиентского ключа SmartCaptcha). Обратитесь к администратору."
        );
        ev.preventDefault();
        return;
      }

      ensureWidget(form);
      var token = readWidgetToken(form);
      if (!token) {
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

      var submitBtn = form.querySelector(".wpforms-submit");
      if (submitBtn) {
        submitBtn.disabled = true;
      }

      readySmartCaptcha()
        .then(function () {
          var input = ensureTokenInput(form);
          input.value = token;
          form.setAttribute("data-sfrfr-captcha-ok", "1");
          if (typeof form.requestSubmit === "function") {
            form.requestSubmit(submitBtn || undefined);
          } else {
            HTMLFormElement.prototype.submit.call(form);
          }
        })
        .catch(function () {
          if (submitBtn) {
            submitBtn.disabled = false;
          }
          window.alert(
            "Не удалось проверить форму (SmartCaptcha). Обновите страницу и попробуйте снова."
          );
        });
    },
    true
  );
})();
