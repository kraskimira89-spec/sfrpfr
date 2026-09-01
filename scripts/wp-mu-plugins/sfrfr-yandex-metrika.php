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

/**
 * Роботы Яндекса должны видеть счётчик без cookie-баннера (рекомендация Вебмастера).
 */
function sfrfr_metrika_is_yandex_robot(): bool
{
    $ua = (string) ($_SERVER['HTTP_USER_AGENT'] ?? '');
    return $ua !== '' && (bool) preg_match('/Yandex(Bot|Metrika|Webmaster|Direct|Images|MobileBot|Favicons)/i', $ua);
}

/** Версия согласия на статистические cookies (не СОПД). */
function sfrfr_metrika_consent_version(): string
{
    return 'stat-cookies-2026-07-29';
}

/**
 * Для роботов Яндекса — классический счётчик в head (без баннера согласия).
 */
add_action('wp_head', static function (): void {
    if (is_admin() || !sfrfr_metrika_is_yandex_robot()) {
        return;
    }
    $id = sfrfr_metrika_counter_id();
    if ($id === '') {
        return;
    }
    $cid = (int) $id;
    ?>
<!-- Yandex.Metrika counter (robots) -->
<script type="text/javascript">
(function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
m[i].l=1*new Date();
for (var j = 0; j < document.scripts.length; j++) {if (document.scripts[j].src === r) { return; }}
k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)})
(window, document, "script", "https://mc.yandex.ru/metrika/tag.js", "ym");
ym(<?php echo $cid; ?>, "init", {clickmap:true, trackLinks:true, accurateTrackBounce:true, webvisor:false});
</script>
<noscript><div><img src="https://mc.yandex.ru/watch/<?php echo $cid; ?>" style="position:absolute; left:-9999px;" alt="" /></div></noscript>
<!-- /Yandex.Metrika counter -->
    <?php
}, 2);

add_action('wp_footer', static function (): void {
    $id = sfrfr_metrika_counter_id();
    if ($id === '') {
        return;
    }
    // Роботам уже отдали счётчик в head.
    if (sfrfr_metrika_is_yandex_robot()) {
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
  position:fixed;z-index:10050;left:16px;bottom:16px;right:auto;max-width:320px;margin:0;
  background:rgba(255,255,255,.96);color:#445566;border:1px solid #e4ebf2;border-radius:10px;
  box-shadow:0 4px 18px rgba(20,40,60,.08);padding:12px 14px;font:12.5px/1.4 system-ui,sans-serif;
  opacity:0;transform:translateY(8px);pointer-events:none;transition:opacity .25s ease, transform .25s ease;
  /* Выше sticky «Оставить заявку» (z-index 1000), не перекрывается ею */
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
@media (max-width:767px){
  /* Над sticky CTA (~52px + отступы) + safe-area */
  #sfrfr-metrika-consent{
    left:10px;right:10px;max-width:none;
    bottom:calc(4.5rem + env(safe-area-inset-bottom, 0px));
  }
}
@media (max-width:480px){
  #sfrfr-metrika-consent{left:10px;right:10px;max-width:none}
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
      var item = queue.shift();
      var name = typeof item === "string" ? item : (item && item.name);
      var params = item && typeof item === "object" ? item.params : null;
      if (!name) continue;
      try {
        if (params) ym(COUNTER_ID, "reachGoal", String(name), params);
        else ym(COUNTER_ID, "reachGoal", String(name));
      } catch (e) {}
    }
  }

  window.sfrfrMetrikaGoal = function (name, params) {
    if (!name || readConsent() !== true) return;
    var payload = { name: String(name), params: params && typeof params === "object" ? params : null };
    if (!loaded || typeof ym !== "function") {
      queue.push(payload);
      if (readConsent() === true) loadMetrika();
      return;
    }
    try {
      if (payload.params) ym(COUNTER_ID, "reachGoal", payload.name, payload.params);
      else ym(COUNTER_ID, "reachGoal", payload.name);
    } catch (e) {}
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

  function placementOf(el) {
    if (!el || !el.closest) return undefined;
    if (el.closest(".sfrfr-hero")) return "hero";
    if (el.closest("#o-servise, .sfrfr-trust")) return "trust";
    if (el.closest("#tarify, .sfrfr-site-footer")) {
      if (el.closest("#tarify")) return "tariffs";
    }
    if (el.closest(".sfrfr-site-footer, footer")) return "footer";
    if (el.closest("#tarify")) return "tariffs";
    return undefined;
  }

  function isMaxChannelHref(href) {
    var h = String(href || "").toLowerCase();
    return (
      h.indexOf("joinchat") !== -1 ||
      h.indexOf("/channel") !== -1 ||
      h.indexOf("channel_proverkastaza") !== -1
    );
  }

  function goalWithPlacement(name, el) {
    var placement = placementOf(el);
    var params = {};
    if (placement) params.placement = placement;
    var segmentRoot = el && el.closest ? el.closest("[data-audience-segment]") : null;
    if (segmentRoot && segmentRoot.getAttribute) {
      var seg = segmentRoot.getAttribute("data-audience-segment");
      if (seg) params.audience_segment = seg;
      var pageType = segmentRoot.getAttribute("data-page-type");
      if (pageType) params.page_type = pageType;
    }
    window.sfrfrMetrikaGoal(name, Object.keys(params).length ? params : undefined);
  }

  function bindGoals() {
    document.querySelectorAll('a[href*="max.ru"], a[href*="startapp"]').forEach(function (a) {
      once(a, "sfrfrMetrikaMax", function (el) {
        el.addEventListener("click", function () {
          var custom = el.getAttribute && el.getAttribute("data-sfrfr-goal");
          var href = el.getAttribute ? el.getAttribute("href") : "";
          if (custom === "max_chat_click") {
            goalWithPlacement("max_chat_click", el);
          } else if (custom === "max_channel_click" || isMaxChannelHref(href)) {
            goalWithPlacement("max_channel_click", el);
          } else {
            goalWithPlacement("max_click", el);
          }
        });
      });
    });
    document.querySelectorAll('a[href^="tel:+79091950408"], a[href="tel:+79091950408"], a[data-sfrfr-goal="callback_click"]').forEach(function (a) {
      once(a, "sfrfrMetrikaPhone", function (el) {
        el.addEventListener("click", function () {
          var custom = el.getAttribute && el.getAttribute("data-sfrfr-goal");
          if (custom === "callback_click") {
            goalWithPlacement("callback_click", el);
          } else {
            goalWithPlacement("phone_click", el);
          }
        });
      });
    });
    document.querySelectorAll('a[href="/kontakty/"], a[href*="/kontakty/"]').forEach(function (a) {
      once(a, "sfrfrMetrikaContacts", function (el) {
        el.addEventListener("click", function () {
          goalWithPlacement("contacts_click", el);
        });
      });
    });
    document.querySelectorAll('a[href*="cabinet.proverkastaza.ru"], a[data-sfrfr-goal="cabinet_open_click"]').forEach(function (a) {
      once(a, "sfrfrMetrikaCab", function (el) {
        el.addEventListener("click", function () {
          window.sfrfrMetrikaGoal("cabinet_open_click");
          window.sfrfrMetrikaGoal("cabinet_click");
        });
      });
    });
    document.querySelectorAll('a[href="#kak-prohodit"], a[href*="#kak-prohodit"], a[data-sfrfr-goal="how_it_works_click"]').forEach(function (a) {
      once(a, "sfrfrMetrikaHowItWorks", function (el) {
        el.addEventListener("click", function () {
          goalWithPlacement("how_it_works_click", el);
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
    document.querySelectorAll('a[href*="checklist"], a[data-sfrfr-goal="checklist_download"]').forEach(function (a) {
      once(a, "sfrfrMetrikaChecklist", function (el) {
        el.addEventListener("click", function () {
          goalWithPlacement("checklist_download", el);
        });
      });
    });
    document.querySelectorAll('a[data-sfrfr-goal="checklist_print_open"], a[href*="/chek-list-dokumentov/pechat"]').forEach(function (a) {
      once(a, "sfrfrMetrikaChecklistPrint", function (el) {
        el.addEventListener("click", function () {
          goalWithPlacement("checklist_print_open", el);
        });
      });
    });
    document.querySelectorAll('a[data-sfrfr-goal="checklist_cta_click"]').forEach(function (a) {
      once(a, "sfrfrMetrikaChecklistCta", function (el) {
        el.addEventListener("click", function () {
          goalWithPlacement("checklist_cta_click", el);
        });
      });
    });
    document.querySelectorAll('a[data-sfrfr-goal="checklist_max_click"]').forEach(function (a) {
      once(a, "sfrfrMetrikaChecklistMax", function (el) {
        el.addEventListener("click", function () {
          goalWithPlacement("checklist_max_click", el);
        });
      });
    });
    var checklistPage = document.getElementById("sfrfr-checklist-page");
    if (checklistPage) {
      once(checklistPage, "sfrfrMetrikaChecklistView", function () {
        window.sfrfrMetrikaGoal("checklist_view");
      });
    }
    document.querySelectorAll('a[data-sfrfr-goal="partner_cta_click"]').forEach(function (a) {
      once(a, "sfrfrMetrikaPartnerCta", function (el) {
        el.addEventListener("click", function () {
          window.sfrfrMetrikaGoal("partner_cta_click");
        });
      });
    });
    document.querySelectorAll('#sfrfr-partneram-page a[download], a[data-sfrfr-goal="partner_pptx_download"]').forEach(function (a) {
      once(a, "sfrfrMetrikaPartnerPptx", function (el) {
        el.addEventListener("click", function () {
          window.sfrfrMetrikaGoal("partner_pptx_download");
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
    var tarify = document.getElementById("tarify") || (location.pathname.indexOf("/tarify") === 0 ? document.body : null);
    if (tarify && "IntersectionObserver" in window) {
      once(tarify, "sfrfrMetrikaTariff", function (el) {
        var io = new IntersectionObserver(function (entries) {
          entries.forEach(function (en) {
            if (en.isIntersecting) {
              window.sfrfrMetrikaGoal("tariffs_view", { placement: "tariffs" });
              window.sfrfrMetrikaGoal("tariff_view", { placement: "tariffs" });
              io.disconnect();
            }
          });
        }, { threshold: 0.35 });
        io.observe(el);
      });
    } else if (location.pathname.indexOf("/tarify") === 0) {
      window.sfrfrMetrikaGoal("tariffs_view", { placement: "tariffs" });
      window.sfrfrMetrikaGoal("tariff_view", { placement: "tariffs" });
    }
    var segment = document.querySelector(".sfrfr-landing[data-audience-segment]");
    if (segment) {
      once(segment, "sfrfrMetrikaSegment", function (el) {
        var seg = el.getAttribute("data-audience-segment") || "unknown";
        var pageType = el.getAttribute("data-page-type") || "segment";
        window.sfrfrMetrikaGoal("segment_page_view", {
          audience_segment: seg,
          page_type: pageType,
          placement: "segment_landing",
        });
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
