<?php
/**
 * Plugin Name: SFRFR Site Footer
 * Description: Единый футер «Проверка стажа» на всех страницах сайта.
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * Публичный URL MAX для ссылок в футере.
 */
function sfrfr_site_footer_max_url(): string
{
    if (function_exists('sfrfr_blog_max_chat_url')) {
        return sfrfr_blog_max_chat_url();
    }
    $url = getenv('MAX_CHAT_URL') ?: getenv('MAX_PUBLIC_BOT_URL') ?: '';
    $url = is_string($url) ? trim($url) : '';
    if ($url === '') {
        $url = (string) get_option('sfrfr_max_chat_url', '');
    }
    if ($url === '') {
        $url = 'https://max.ru/id8905998693_1_bot';
    }
    return $url;
}

/**
 * Публичный URL канала MAX (вторичная ссылка, не CTA услуги).
 */
function sfrfr_site_footer_max_channel_url(): string
{
    $url = getenv('MAX_CHANNEL_URL') ?: '';
    $url = is_string($url) ? trim($url) : '';
    if ($url === '') {
        $url = (string) get_option('sfrfr_max_channel_url', '');
    }
    if ($url === '') {
        $url = 'https://max.ru/channel_proverkastaza';
    }
    return $url;
}

/**
 * Кнопка BVI (версия для слабовидящих), если плагин активен.
 */
function sfrfr_site_footer_bvi_html(): string
{
    if (shortcode_exists('bvi')) {
        return '<div class="sfrfr-bvi">' . do_shortcode('[bvi text="Версия для слабовидящих"]') . '</div>';
    }
    // Плагин установлен, но shortcode ещё не зарегистрирован — ссылка с классом bvi-open
    if (!function_exists('is_plugin_active')) {
        require_once ABSPATH . 'wp-admin/includes/plugin.php';
    }
    $active = is_plugin_active('button-visually-impaired/Button-visually-impaired.php')
        || is_plugin_active('button-visually-impaired/button-visually-impaired.php');
    if (!$active) {
        return '';
    }
    return '<div class="sfrfr-bvi"><a href="#" class="bvi-open">Версия для слабовидящих</a></div>';
}

/**
 * HTML футера.
 */
function sfrfr_site_footer_html(): string
{
    $home = esc_url(home_url('/'));
    $logo = esc_url(content_url('uploads/sfrfr/sfrfr-logo-light.png'));
    $max = esc_url(sfrfr_site_footer_max_url());
    $channel = esc_url(sfrfr_site_footer_max_channel_url());
    $bvi = sfrfr_site_footer_bvi_html();

    return <<<HTML
<footer class="sfrfr-site-footer" role="contentinfo" itemscope itemtype="https://schema.org/Organization">
  <meta itemprop="url" content="{$home}">
  <div class="sfrfr-wrap sfrfr-site-footer__grid">
    <div>
      <p class="sfrfr-brand sfrfr-brand--footer">
        <a class="sfrfr-brand__link" href="{$home}" title="На главную" aria-label="На главную">
          <img class="sfrfr-brand__logo" src="{$logo}" width="40" height="40" alt="Проверка стажа" itemprop="logo">
          <span itemprop="name">Проверка стажа</span>
        </a>
      </p>
      <p>Сервис не является государственным органом. Мы готовим документы, черновики и понятный план. А подаёте обращение через СФР, МФЦ или Госуслуги вы сами. Решение о пенсии и перерасчёте принимает только СФР.</p>
      {$bvi}
      <p class="sfrfr-iks">
        <a href="https://webmaster.yandex.ru/siteinfo/?site=https://proverkastaza.ru" target="_blank" rel="noopener noreferrer" title="Индекс качества сайта в Яндекс Вебмастере">
          <img width="88" height="31" alt="Индекс качества сайта Яндекса" src="https://yandex.ru/cycounter?https://proverkastaza.ru&amp;theme=light&amp;lang=ru" style="border:0;border-radius:8px;vertical-align:middle" loading="lazy" decoding="async">
        </a>
      </p>
      <p class="sfrfr-req" itemprop="address" itemscope itemtype="https://schema.org/PostalAddress">
        <strong>ООО «ПОД ПРИСМОТРОМ»</strong><br>
        ИНН 8905066468 · КПП 890501001 · ОГРН 1208900000572<br>
        Ген. директор: Лопакова Наталия Федоровна<br>
        <span itemprop="postalCode">629804</span>, ЯНАО, г.&nbsp;<span itemprop="addressLocality">Ноябрьск</span>, <span itemprop="streetAddress">ул.&nbsp;Рабочая, д.&nbsp;109Б, кв.&nbsp;4</span>
        <meta itemprop="addressCountry" content="RU">
      </p>
    </div>
    <div>
      <p><strong>Документы</strong></p>
      <p class="sfrfr-legal-links">
        <a href="{$home}proverka-stazha/">Услуга</a><br>
        <a href="{$home}tarify/">Тарифы</a><br>
        <a href="{$home}kak-rabotaem/">Как мы работаем</a><br>
        <a href="{$home}kontakty/">Контакты и реквизиты</a><br>
        <a href="{$home}expert/">Кто оказывает</a><br>
        <a href="{$home}oferta/">Оферта</a><br>
        <a href="{$home}politika-pdn/">Политика обработки персональных данных</a><br>
        <a href="{$home}soglasie/">Согласие на обработку ПДн</a><br>
        <a href="{$home}cookies/">Файлы браузера</a><br>
        <a href="{$home}blog/">Статьи</a>
      </p>
    </div>
    <div>
      <p><strong>Контакты</strong></p>
      <p class="sfrfr-req">
        Телефон: <a href="tel:+79091950408" itemprop="telephone">+7&nbsp;909&nbsp;195‑04‑08</a><br>
        Почта: <a href="mailto:info@proverkastaza.ru" itemprop="email">info@proverkastaza.ru</a><br>
        Диалог: <a href="{$max}" target="_blank" rel="noopener noreferrer">Уточнить ситуацию в MAX</a><br>
        Материалы: <a href="{$channel}" target="_blank" rel="noopener noreferrer">канал в MAX</a>
      </p>
      <p><strong>Банковские реквизиты</strong></p>
      <p class="sfrfr-req">
        р/с 40702810467400005864<br>
        Банк: Западно-Сибирское отделение №&nbsp;8647 ПАО Сбербанк<br>
        БИК 047102651<br>
        к/с 30101810800000000651
      </p>
    </div>
  </div>
</footer>
HTML;
}

/**
 * Компактная кнопка BVI поверх страницы (fixed), без полосы под шапкой —
 * не сдвигает hero и заголовок.
 */
add_action('wp_footer', static function (): void {
    if (is_admin()) {
        return;
    }
    $html = sfrfr_site_footer_bvi_html();
    if ($html === '') {
        return;
    }
    echo '<div class="sfrfr-bvi-float" role="navigation" aria-label="Версия для слабовидящих">' . $html . '</div>';
}, 4);

/**
 * Слайдер наград на главной (ТЗ-22).
 */
add_action('wp_enqueue_scripts', static function (): void {
    if (is_admin() || !is_front_page()) {
        return;
    }
    $js = WP_CONTENT_DIR . '/mu-plugins/sfrfr-awards.js';
    if (!is_readable($js)) {
        return;
    }
    $ver = (string) filemtime($js);
    wp_enqueue_script(
        'sfrfr-awards',
        content_url('mu-plugins/sfrfr-awards.js'),
        [],
        $ver,
        true
    );
});

/**
 * Вывод перед закрытием body (на всех публичных страницах).
 */
add_action('wp_footer', static function (): void {
    if (is_admin()) {
        return;
    }
    // Не дублировать, если футер уже в контенте (старые черновики).
    // На фронте контент уже отдан — проверяем только через флаг.
    if (!empty($GLOBALS['sfrfr_site_footer_printed'])) {
        return;
    }
    $GLOBALS['sfrfr_site_footer_printed'] = true;
    // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- собран через esc_* выше
    echo sfrfr_site_footer_html();
}, 5);

/**
 * Debug 016b5f: зонд стилей выпадающего меню «Главная» (временно).
 */
add_action('wp_footer', static function (): void {
    if (is_admin()) {
        return;
    }
    ?>
    <!-- #region agent log -->
    <script>
    (function () {
      var ENDPOINT = 'http://127.0.0.1:7431/ingest/15b5aa1f-f97a-42c4-8de4-bc9cab7ebdc3';
      var sent = false;
      function send(hypothesisId, message, data) {
        fetch(ENDPOINT, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Debug-Session-Id': '016b5f'
          },
          body: JSON.stringify({
            sessionId: '016b5f',
            runId: 'user-browser',
            hypothesisId: hypothesisId,
            location: 'sfrfr-site-footer.php:nav-debug',
            message: message,
            data: data || {},
            timestamp: Date.now()
          })
        }).catch(function () {});
      }
      function probe(reason) {
        var cssEl = document.getElementById('wp-custom-css');
        var cssText = cssEl ? (cssEl.textContent || '') : '';
        var home = Array.prototype.find.call(
          document.querySelectorAll('#ast-hf-menu-1 > .menu-item'),
          function (li) {
            var t = ((li.querySelector(':scope > .menu-link') || {}).textContent || '');
            return t.indexOf('Главная') !== -1;
          }
        );
        var sub = home ? home.querySelector(':scope > .sub-menu') : null;
        var link = sub ? sub.querySelector(':scope > .menu-item > .menu-link') : null;
        var cs = sub ? getComputedStyle(sub) : null;
        var cl = link ? getComputedStyle(link) : null;
        send('H1', 'browser menu structure', {
          reason: reason,
          homeFound: !!home,
          subFound: !!sub,
          tops: Array.prototype.map.call(
            document.querySelectorAll('#ast-hf-menu-1 > .menu-item'),
            function (li) {
              var a = li.querySelector(':scope > .menu-link');
              return {
                text: ((a && a.textContent) || '').replace(/\s+/g, ' ').trim(),
                hasSub: !!li.querySelector(':scope > .sub-menu')
              };
            }
          )
        });
        send('H2', 'browser css markers', {
          reason: reason,
          hasCustomCss: !!cssEl,
          hasInsetRight: cssText.indexOf('inset -3px 0 0') !== -1,
          hasWhiteSub: cssText.indexOf('background: #ffffff !important') !== -1,
          hasNavV2: cssText.indexOf('sfrfr-nav-dropdown-v2') !== -1,
          hasNavV3: cssText.indexOf('sfrfr-nav-dropdown-v3') !== -1,
          hasHeaderLayoutV1: cssText.indexOf('sfrfr-header-layout-v1') !== -1,
          hasGreenHoverBg: cssText.indexOf('background: #f3f7f4 !important') !== -1
        });
        var title = document.querySelector('.site-title');
        var tr = title ? title.getBoundingClientRect() : null;
        send('L6', 'browser header brand geometry', {
          reason: reason,
          titleW: tr && Math.round(tr.width),
          titleH: tr && Math.round(tr.height),
          crushed: !!(tr && tr.width < 80 && tr.height > 60),
          titleWhiteSpace: title ? getComputedStyle(title).whiteSpace : null
        });
        send('H3', 'browser computed submenu', {
          reason: reason,
          runIdHint: 'post-fix',
          subBg: cs && cs.backgroundColor,
          subBorderLeft: cs && cs.borderLeft,
          subBorderRight: cs && cs.borderRight,
          subShadow: cs && cs.boxShadow,
          linkBg: cl && cl.backgroundColor,
          linkColor: cl && cl.color,
          linkShadow: cl && cl.boxShadow
        });
      }
      function onReady() {
        send('H4', 'debug probe loaded', { href: location.href, ua: navigator.userAgent.slice(0, 80) });
        probe('load');
        var home = Array.prototype.find.call(
          document.querySelectorAll('#ast-hf-menu-1 > .menu-item'),
          function (li) {
            var t = ((li.querySelector(':scope > .menu-link') || {}).textContent || '');
            return t.indexOf('Главная') !== -1;
          }
        );
        if (!home) return;
        home.addEventListener('mouseenter', function () {
          if (sent) return;
          sent = true;
          setTimeout(function () { probe('glavnaya-hover'); }, 120);
        });
      }
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', onReady);
      } else {
        onReady();
      }
    })();
    </script>
    <!-- #endregion -->
    <?php
}, 99);
