<?php
/**
 * Plugin Name: SFRFR Yandex Metrika
 * Description: Счётчик Метрики из YANDEX_METRIKA_COUNTER_ID; цели lead_ok / max_click без ПДн.
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
        if ($k !== '') {
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

add_action('wp_head', static function (): void {
    $id = sfrfr_metrika_counter_id();
    if ($id === '') {
        return;
    }
    $webvisor = sfrfr_metrika_env('YANDEX_METRIKA_WEBVISOR', '0') === '1';
    $clickmap = true;
    $trackHash = true;
    // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- numeric id only
    $cid = $id;
    ?>
<!-- SFRFR Yandex.Metrika -->
<script type="text/javascript">
(function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
m[i].l=1*new Date();
for (var j = 0; j < document.scripts.length; j++) {if (document.scripts[j].src === r) { return; }}
k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)})
(window, document, "script", "https://mc.yandex.ru/metrika/tag.js", "ym");
ym(<?php echo (int) $cid; ?>, "init", {
  clickmap: <?php echo $clickmap ? 'true' : 'false'; ?>,
  trackLinks: true,
  accurateTrackBounce: true,
  webvisor: <?php echo $webvisor ? 'true' : 'false'; ?>,
  trackHash: <?php echo $trackHash ? 'true' : 'false'; ?>
});
window.sfrfrMetrikaGoal = function (name) {
  if (!name || typeof ym !== "function") return;
  try { ym(<?php echo (int) $cid; ?>, "reachGoal", String(name)); } catch (e) {}
};
</script>
<noscript><div><img src="https://mc.yandex.ru/watch/<?php echo (int) $cid; ?>" style="position:absolute; left:-9999px;" alt="" /></div></noscript>
<!-- /SFRFR Yandex.Metrika -->
    <?php
}, 5);

add_action('wp_footer', static function (): void {
    if (sfrfr_metrika_counter_id() === '') {
        return;
    }
    ?>
<script>
(function () {
  function bindMaxClicks() {
    document.querySelectorAll('a[href*="max.ru"], a[href*="startapp"]').forEach(function (a) {
      if (a.dataset.sfrfrMetrikaBound) return;
      a.dataset.sfrfrMetrikaBound = "1";
      a.addEventListener("click", function () {
        if (typeof window.sfrfrMetrikaGoal === "function") {
          window.sfrfrMetrikaGoal("max_click");
        }
      });
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindMaxClicks);
  } else {
    bindMaxClicks();
  }
  document.addEventListener("wpformsAjaxSubmitSuccess", function () {
    if (typeof window.sfrfrMetrikaGoal === "function") {
      window.sfrfrMetrikaGoal("lead_ok");
    }
  });
})();
</script>
    <?php
}, 20);
