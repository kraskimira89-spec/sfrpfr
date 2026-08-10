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
      <p>Сервис не является государственным органом. Мы готовим документы, проект обращения и понятный план. Мы расскажем по шагам, но обращение через СФР, МФЦ или Госуслуги подаёте вы сами. Решение о пенсии и перерасчёте принимает только СФР.</p>
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
