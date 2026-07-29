<?php
/**
 * Plugin Name: SFRFR Yandex Metrika
 * Description: Метрика только после согласия на статистические cookies; цели без ПДн.
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

/** Версия согласия на статистические cookies (не СОПД). */
function sfrfr_metrika_consent_version(): string
{
    return 'stat-cookies-2026-07-29';
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
    $ajax_url = esc_url(admin_url('admin-ajax.php'));
    ?>
<style id="sfrfr-metrika-consent-css">
#sfrfr-metrika-consent{
  position:fixed;z-index:40;left:16px;bottom:16px;right:auto;max-width:320px;margin:0;
  background:rgba(255,255,255,.96);color:#445566;border:1px solid #e4ebf2;border-radius:10px;
  box-shadow:0 4px 18px rgba(20,40,60,.08);padding:12px 14px;font:12.5px/1.4 system-ui,sans-serif;
  opacity:0;transform:translateY(8px);pointer-events:none;transition:opacity .25s ease, transform .25s ease;
}
#sfrfr-metrika-consent.sfrfr-mc-visible{
  opacity:1;transform:none;pointer-events:auto;
}
#sfrfr-metrika-consent[hidden]{display:none!important}
#sfrfr-metrika-consent p{margin:0 0 8px;font-weight:400}
#sfrfr-metrika-consent a{color:#1e4e79;text-decoration:underline}
#sfrfr-metrika-consent .sfrfr-mc-actions{display:flex;gap:6px}
#sfrfr-metrika-consent button{
  flex:1 1 auto;min-height:32px;border-radius:6px;border:1px solid #c5d0dc;
  cursor:pointer;font:500 12.5px/1 system-ui,sans-serif;padding:6px 8px;background:#fff;color:#334455;
}
#sfrfr-metrika-consent .sfrfr-mc-allow{background:#1e4e79;border-color:#1e4e79;color:#fff}
@media (max-width:480px){
  #sfrfr-metrika-consent{left:10px;right:10px;max-width:none;bottom:10px}
}
</style>
<div id="sfrfr-metrika-consent" hidden role="dialog" aria-live="polite" aria-label="Статистические файлы браузера">
  <p>Обезличенная статистика (Яндекс Метрика) — по желанию.
  Не относится к персональным данным заявки.
  <a href="<?php echo $cookies_url; ?>">Подробнее</a></p>
  <div class="sfrfr-mc-actions">
    <button type="button" class="sfrfr-mc-allow" data-sfrfr-metrika-consent="1">OK</button>
    <button type="button" class="sfrfr-mc-deny" data-sfrfr-metrika-consent="0">Нет</button>
  </div>
</div>
<script>
(function () {
  var COUNTER_ID = <?php echo $cid; ?>;
  var WEBVISOR = <?php echo $webvisor ? 'true' : 'false'; ?>;
  var CONSENT_KEY = "sfrfr_metrika_consent";
  var CONSENT_VER = <?php echo wp_json_encode($ver); ?>;
  var AJAX = <?php echo wp_json_encode($ajax_url); ?>;
  var storageKey = CONSENT_KEY + ":" + CONSENT_VER;
  var cookieName = "sfrfr_mc";
  var loaded = false;
  var queue = [];
  var banner = document.getElementById("sfrfr-metrika-consent");
  var SHOW_DELAY_MS = 2500;

  function readCookie(name) {
    var m = document.cookie.match(new RegExp("(?:^|; )" + name.replace(/([.$?*|{}()[\]\\/+^])/g, "\\$1") + "=([^;]*)"));
    return m ? decodeURIComponent(m[1]) : null;
  }

  function writeCookie(name, value) {
    var maxAge = 60 * 60 * 24 * 400; // ~13 мес., один раз на браузер
    document.cookie = name + "=" + encodeURIComponent(value)
      + "; Path=/; Max-Age=" + maxAge + "; SameSite=Lax";
  }

  function readConsent() {
    try {
      var raw = localStorage.getItem(storageKey);
      if (raw === "1") return true;
      if (raw === "0") return false;
    } catch (e) {}
    var c = readCookie(cookieName);
    if (c === "1") return true;
    if (c === "0") return false;
    return null;
  }

  function writeConsent(ok) {
    var v = ok ? "1" : "0";
    try { localStorage.setItem(storageKey, v); } catch (e) {}
    try { writeCookie(cookieName, v); } catch (e) {}
  }

  function pingInternal(eventCode) {
    try {
      var body = "action=sfrfr_stat_hit&e=" + encodeURIComponent(eventCode);
      if (navigator.sendBeacon) {
        navigator.sendBeacon(AJAX, new Blob([body], { type: "application/x-www-form-urlencoded" }));
        return;
      }
      fetch(AJAX, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: body,
        keepalive: true,
        credentials: "same-origin"
      }).catch(function () {});
    } catch (e) {}
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

  function hideBanner() {
    if (!banner) return;
    banner.classList.remove("sfrfr-mc-visible");
    banner.hidden = true;
  }

  function revealBannerOnce() {
    if (!banner || readConsent() !== null) return;
    banner.hidden = false;
    requestAnimationFrame(function () {
      banner.classList.add("sfrfr-mc-visible");
    });
  }

  function applyConsent(ok) {
    writeConsent(ok);
    hideBanner();
    pingInternal(ok ? "consent_allow" : "consent_deny");
    if (ok) loadMetrika();
  }

  function bindUI() {
    if (!banner) return;
    banner.addEventListener("click", function (ev) {
      var t = ev.target;
      if (!t || !t.getAttribute) return;
      var v = t.getAttribute("data-sfrfr-metrika-consent");
      if (v === "1") applyConsent(true);
      if (v === "0") applyConsent(false);
    });
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

  window.addEventListener("error", function () {
    pingInternal("tech_error");
  }, { once: true });

  bindUI();
  bindGoals();
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindGoals);
  }

  var consent = readConsent();
  if (consent === true) {
    hideBanner();
    loadMetrika();
  } else if (consent === false) {
    hideBanner();
  } else {
    // Один показ на пользователя; после выбора больше не появляется.
    setTimeout(revealBannerOnce, SHOW_DELAY_MS);
  }
})();
</script>
    <?php
}, 5);
