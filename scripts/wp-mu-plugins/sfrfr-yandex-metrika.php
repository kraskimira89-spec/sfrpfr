<?php
/**
 * Plugin Name: SFRFR Yandex Metrika
 * Description: Счётчик Метрики только после согласия; цели без ПДн.
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * @return array<string,string>
 */
function sfrfr_metrika_env_map(): array
{
    static $map = null;
    if (is_array($map)) {
        return $map;
    }
    $map = [];
    foreach ([
        __DIR__ . '/sfrfr-yandex-metrika.config.php',
        '/opt/sfrfr/secrets/yandex-metrika.public.php',
    ] as $cfg) {
        if (is_readable($cfg)) {
            /** @var mixed $loaded */
            $loaded = include $cfg;
            if (is_array($loaded)) {
                foreach ($loaded as $k => $v) {
                    if (is_string($k) && (is_string($v) || is_int($v))) {
                        $map[$k] = (string) $v;
                    }
                }
            }
        }
    }
    $path = '/opt/sfrfr/.env';
    if (!is_readable($path)) {
        return $map;
    }
    $lines = file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    if (!is_array($lines)) {
        return $map;
    }
    foreach ($lines as $line) {
        $line = trim($line);
        if ($line === '' || str_starts_with($line, '#') || !str_contains($line, '=')) {
            continue;
        }
        [$k, $v] = explode('=', $line, 2);
        $k = trim($k);
        $v = trim($v, " \t\"'");
        if ($k !== '' && !isset($map[$k])) {
            $map[$k] = $v;
        }
    }
    return $map;
}

function sfrfr_metrika_env(string $key, string $default = ''): string
{
    $val = getenv($key);
    if (is_string($val) && trim($val) !== '') {
        return trim($val);
    }
    $map = sfrfr_metrika_env_map();
    return isset($map[$key]) && $map[$key] !== '' ? $map[$key] : $default;
}

function sfrfr_metrika_counter_id(): string
{
    $id = preg_replace('/\D+/', '', sfrfr_metrika_env('YANDEX_METRIKA_COUNTER_ID', ''));
    return is_string($id) ? $id : '';
}

/** Версия согласия — при смене политики сбросить выбор. */
function sfrfr_metrika_consent_version(): string
{
    return 'metrika-consent-2026-07-29';
}

add_action('wp_footer', static function (): void {
    $id = sfrfr_metrika_counter_id();
    if ($id === '') {
        return;
    }
    $webvisor = sfrfr_metrika_env('YANDEX_METRIKA_WEBVISOR', '0') === '1';
    $cid = (int) $id;
    $ver = sfrfr_metrika_consent_version();
    $cookies_url = esc_url(home_url('/cookies/'));
    ?>
<style id="sfrfr-metrika-consent-css">
#sfrfr-metrika-consent{
  position:fixed;z-index:99999;left:12px;right:12px;bottom:12px;max-width:560px;margin:0 auto;
  background:#fff;color:#1a2b3c;border:1px solid #d5dde6;border-radius:12px;
  box-shadow:0 10px 32px rgba(16,40,64,.18);padding:14px 16px;font:14px/1.45 system-ui,sans-serif;
}
#sfrfr-metrika-consent[hidden]{display:none!important}
#sfrfr-metrika-consent p{margin:0 0 10px}
#sfrfr-metrika-consent a{color:#1e4e79}
#sfrfr-metrika-consent .sfrfr-mc-actions{display:flex;flex-wrap:wrap;gap:8px}
#sfrfr-metrika-consent button{
  flex:1 1 140px;min-height:40px;border-radius:8px;border:1px solid #1e4e79;
  cursor:pointer;font:600 14px/1 system-ui,sans-serif;padding:8px 12px;
}
#sfrfr-metrika-consent .sfrfr-mc-allow{background:#1e4e79;color:#fff}
#sfrfr-metrika-consent .sfrfr-mc-deny{background:#fff;color:#1e4e79}
#sfrfr-metrika-consent-change{
  position:fixed;z-index:99998;right:12px;bottom:12px;font:12px/1 system-ui,sans-serif;
  background:transparent;border:0;color:#6b7c8d;cursor:pointer;text-decoration:underline;padding:4px;
}
#sfrfr-metrika-consent-change[hidden]{display:none!important}
</style>
<div id="sfrfr-metrika-consent" hidden role="dialog" aria-live="polite" aria-label="Согласие на статистику">
  <p>Для улучшения сайта можем включить необязательную обезличенную статистику Яндекс Метрики.
  Подробнее: <a href="<?php echo $cookies_url; ?>">файлы браузера</a>.</p>
  <div class="sfrfr-mc-actions">
    <button type="button" class="sfrfr-mc-allow" data-sfrfr-metrika-consent="1">Разрешить</button>
    <button type="button" class="sfrfr-mc-deny" data-sfrfr-metrika-consent="0">Отказаться</button>
  </div>
</div>
<button type="button" id="sfrfr-metrika-consent-change" hidden>Настройки статистики</button>
<script>
(function () {
  var COUNTER_ID = <?php echo $cid; ?>;
  var WEBVISOR = <?php echo $webvisor ? 'true' : 'false'; ?>;
  var CONSENT_KEY = "sfrfr_metrika_consent";
  var CONSENT_VER = <?php echo wp_json_encode($ver); ?>;
  var storageKey = CONSENT_KEY + ":" + CONSENT_VER;
  var loaded = false;
  var queue = [];
  var banner = document.getElementById("sfrfr-metrika-consent");
  var changeBtn = document.getElementById("sfrfr-metrika-consent-change");

  function readConsent() {
    try {
      var raw = localStorage.getItem(storageKey);
      if (raw === "1") return true;
      if (raw === "0") return false;
    } catch (e) {}
    return null;
  }

  function writeConsent(ok) {
    try { localStorage.setItem(storageKey, ok ? "1" : "0"); } catch (e) {}
  }

  function loadMetrika() {
    if (loaded) return;
    loaded = true;
    (function (m, e, t, r, i, k, a) {
      m[i] = m[i] || function () { (m[i].a = m[i].a || []).push(arguments); };
      m[i].l = 1 * new Date();
      for (var j = 0; j < document.scripts.length; j++) {
        if (document.scripts[j].src === r) { return; }
      }
      k = e.createElement(t); a = e.getElementsByTagName(t)[0];
      k.async = 1; k.src = r; a.parentNode.insertBefore(k, a);
    })(window, document, "script", "https://mc.yandex.ru/metrika/tag.js", "ym");
    ym(COUNTER_ID, "init", {
      clickmap: true,
      trackLinks: true,
      accurateTrackBounce: true,
      webvisor: WEBVISOR,
      trackHash: true
    });
    flushQueue();
  }

  function flushQueue() {
    if (typeof ym !== "function") return;
    while (queue.length) {
      var name = queue.shift();
      try { ym(COUNTER_ID, "reachGoal", String(name)); } catch (e) {}
    }
  }

  window.sfrfrMetrikaGoal = function (name) {
    if (!name || readConsent() !== true) return;
    if (!loaded || typeof ym !== "function") {
      queue.push(String(name));
      if (readConsent() === true) loadMetrika();
      return;
    }
    try { ym(COUNTER_ID, "reachGoal", String(name)); } catch (e) {}
  };

  function showBanner(show) {
    if (banner) banner.hidden = !show;
    if (changeBtn) changeBtn.hidden = show;
  }

  function applyConsent(ok) {
    writeConsent(ok);
    showBanner(false);
    if (ok) loadMetrika();
  }

  function bindUI() {
    if (banner) {
      banner.addEventListener("click", function (ev) {
        var t = ev.target;
        if (!t || !t.getAttribute) return;
        var v = t.getAttribute("data-sfrfr-metrika-consent");
        if (v === "1") applyConsent(true);
        if (v === "0") applyConsent(false);
      });
    }
    if (changeBtn) {
      changeBtn.addEventListener("click", function () {
        try { localStorage.removeItem(storageKey); } catch (e) {}
        showBanner(true);
      });
    }
  }

  function once(el, flag, fn) {
    if (!el || el.dataset[flag]) return;
    el.dataset[flag] = "1";
    fn(el);
  }

  function bindGoals() {
    document.querySelectorAll('a[href*="max.ru"], a[href*="startapp"]').forEach(function (a) {
      once(a, "sfrfrMetrikaMax", function (el) {
        el.addEventListener("click", function () {
          window.sfrfrMetrikaGoal("max_click");
        });
      });
    });
    document.querySelectorAll('a[href*="cabinet.proverkastaza.ru"]').forEach(function (a) {
      once(a, "sfrfrMetrikaCab", function (el) {
        el.addEventListener("click", function () {
          window.sfrfrMetrikaGoal("cabinet_click");
        });
      });
    });
    document.querySelectorAll('a[href="#zayavka"], a[href*="#zayavka"]').forEach(function (a) {
      once(a, "sfrfrMetrikaLeadStartA", function (el) {
        el.addEventListener("click", function () {
          window.sfrfrMetrikaGoal("lead_start");
        });
      });
    });
    var form = document.querySelector("#zayavka form, .wpforms-form, form.wpforms-form");
    if (form) {
      once(form, "sfrfrMetrikaLeadStartF", function (el) {
        el.addEventListener("focusin", function () {
          window.sfrfrMetrikaGoal("lead_start");
        }, { once: true });
      });
    }
    var tarify = document.getElementById("tarify");
    if (tarify && "IntersectionObserver" in window) {
      once(tarify, "sfrfrMetrikaTariff", function (el) {
        var io = new IntersectionObserver(function (entries) {
          entries.forEach(function (en) {
            if (en.isIntersecting) {
              window.sfrfrMetrikaGoal("tariff_view");
              io.disconnect();
            }
          });
        }, { threshold: 0.35 });
        io.observe(el);
      });
    }
  }

  document.addEventListener("wpformsAjaxSubmitSuccess", function () {
    window.sfrfrMetrikaGoal("lead_ok");
  });
  document.addEventListener("wpformsAjaxSubmitError", function () {
    window.sfrfrMetrikaGoal("form_error");
  });
  document.addEventListener("wpformsAjaxSubmitFailed", function () {
    window.sfrfrMetrikaGoal("form_error");
  });

  bindUI();
  bindGoals();
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindGoals);
  }

  var consent = readConsent();
  if (consent === true) {
    showBanner(false);
    loadMetrika();
  } else if (consent === false) {
    showBanner(false);
    if (changeBtn) changeBtn.hidden = false;
  } else {
    showBanner(true);
  }
})();
</script>
    <?php
}, 5);
