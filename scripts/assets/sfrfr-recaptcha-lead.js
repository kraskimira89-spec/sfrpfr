/**
 * reCAPTCHA Enterprise для формы лида WPForms.
 * Action MUST be `lead` (бэкенд отклонит LOGIN/иное).
 */
(function () {
  var SITE_KEY =
    (window.SFRFR_RECAPTCHA && window.SFRFR_RECAPTCHA.siteKey) ||
    "6Lf7UWMtAAAAANDXkb8MR9ufU8QYO9UwZsEC3NHu";
  var ACTION = "lead";

  function findTokenInput(form) {
    return (
      form.querySelector('input[name*="recaptcha_token"]') ||
      form.querySelector('input[name*="[fields][4]"]') ||
      form.querySelector(".sfrfr-recaptcha-token input") ||
      form.querySelector('input[type="hidden"][data-sfrfr-recaptcha]')
    );
  }

  function ensureTokenInput(form) {
    var el = findTokenInput(form);
    if (el) return el;
    el = document.createElement("input");
    el.type = "hidden";
    el.name = "wpforms[fields][4]";
    el.setAttribute("data-sfrfr-recaptcha", "1");
    el.className = "sfrfr-recaptcha-token-input";
    form.appendChild(el);
    return el;
  }

  function readyEnterprise() {
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

  async function getToken() {
    await readyEnterprise();
    return window.grecaptcha.enterprise.execute(SITE_KEY, { action: ACTION });
  }

  document.addEventListener(
    "submit",
    function (ev) {
      var form = ev.target;
      if (!form || !form.classList || !form.classList.contains("wpforms-form")) {
        return;
      }
      if (form.getAttribute("data-sfrfr-recaptcha-ok") === "1") {
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

      getToken()
        .then(function (token) {
          var input = ensureTokenInput(form);
          input.value = token || "";
          form.setAttribute("data-sfrfr-recaptcha-ok", "1");
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
            "Не удалось проверить форму (reCAPTCHA). Обновите страницу и попробуйте снова."
          );
        });
    },
    true
  );
})();
