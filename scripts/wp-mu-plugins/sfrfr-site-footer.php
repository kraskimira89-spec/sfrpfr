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
 * HTML футера.
 */
function sfrfr_site_footer_html(): string
{
    $home = esc_url(home_url('/'));
    $logo = esc_url(content_url('uploads/sfrfr/sfrfr-logo-light.png'));
    $max = esc_url(sfrfr_site_footer_max_url());

    return <<<HTML
<footer class="sfrfr-site-footer" role="contentinfo">
  <div class="sfrfr-wrap sfrfr-site-footer__grid">
    <div>
      <p class="sfrfr-brand sfrfr-brand--footer">
        <a class="sfrfr-brand__link" href="{$home}" title="На главную" aria-label="На главную">
          <img class="sfrfr-brand__logo" src="{$logo}" width="40" height="40" alt="Проверка стажа">
          <span>Проверка стажа</span>
        </a>
      </p>
      <p>Сервис не является государственным органом. Решение о перерасчёте принимает СФР.</p>
      <p class="sfrfr-iks">
        <a href="https://webmaster.yandex.ru/siteinfo/?site=https://proverkastaza.ru" target="_blank" rel="noopener noreferrer" title="Индекс качества сайта в Яндекс Вебмастере">
          <img width="88" height="31" alt="Индекс качества сайта Яндекса" src="https://yandex.ru/cycounter?https://proverkastaza.ru&amp;theme=dark&amp;lang=ru" style="border:0;border-radius:8px;vertical-align:middle" loading="lazy" decoding="async">
        </a>
      </p>
      <p class="sfrfr-req">
        <strong>ООО «ПОД ПРИСМОТРОМ»</strong><br>
        ИНН 8905066468 · КПП 890501001 · ОГРН 1208900000572<br>
        Ген. директор: Лопакова Наталия Федоровна<br>
        629804, ЯНАО, г.&nbsp;Ноябрьск, ул.&nbsp;Рабочая, д.&nbsp;109Б, кв.&nbsp;4
      </p>
    </div>
    <div>
      <p><strong>Документы</strong></p>
      <p class="sfrfr-legal-links">
        <a href="{$home}proverka-stazha/">Услуга</a><br>
        <a href="{$home}tarify/">Тарифы</a><br>
        <a href="{$home}kak-rabotaem/">Как мы работаем</a><br>
        <a href="{$home}kontakty/">Контакты и реквизиты</a><br>
        <a href="{$home}expert/lopakova-nataliya/">Кто оказывает</a><br>
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
        Телефон: <a href="tel:+79091950408">+7&nbsp;909&nbsp;195‑04‑08</a><br>
        Почта: <a href="mailto:info@proverkastaza.ru">info@proverkastaza.ru</a><br>
        Диалог: <a href="{$max}" target="_blank" rel="noopener noreferrer">Уточнить ситуацию в MAX</a>
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
