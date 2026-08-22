<?php
/**
 * Plugin Name: SFRFR CF7 Feedback
 * Description: Одна форма Contact Form 7: тема по странице, honeypot, SmartCaptcha.
 */

if (!defined('ABSPATH')) {
    exit;
}

const SFRFR_CF7_FEEDBACK_MARKER = '<!-- SFRFR_FEEDBACK_FORM -->';
const SFRFR_CF7_FEEDBACK_TITLE = 'Обратная связь';

/**
 * @return array<string,string>
 */
function sfrfr_cf7_topic_map(): array
{
    return [
        'kontakty' => 'Другой вопрос',
        'proverka-stazha' => 'Проверка стажа',
        'proverka-severnogo-stazha' => 'Северный стаж',
        'stazh-do-2002' => 'Стаж до 2002',
        'proverka-stazha-pered-pensiey' => 'Перед пенсией',
        'pomoch-rodstvenniku-proverit-stazh' => 'Помочь родственнику',
        'tarify' => 'Тарифы',
        'kak-rabotaem' => 'Как работаем',
        'ne-uchli-stazh' => 'Не учли стаж',
        'arhivnaya-spravka-stazh' => 'Архивная справка',
        'otkaz-sfr' => 'Отказ СФР',
        'expert' => 'Другой вопрос',
        'expert/lopakova-nataliya' => 'Другой вопрос',
        'expert/bogdanovskiy-sergey' => 'Другой вопрос',
    ];
}

function sfrfr_cf7_page_uri(): string
{
    if (!is_singular('page')) {
        return '';
    }
    $post = get_queried_object();
    if (!$post instanceof WP_Post) {
        return '';
    }
    $uri = get_page_uri($post);
    return is_string($uri) ? $uri : (string) $post->post_name;
}

function sfrfr_cf7_topic_for_page(): string
{
    $map = sfrfr_cf7_topic_map();
    $uri = sfrfr_cf7_page_uri();
    return $map[$uri] ?? '';
}

function sfrfr_cf7_feedback_id(): int
{
    static $id = null;
    if ($id !== null) {
        return $id;
    }
    $id = (int) get_option('sfrfr_cf7_feedback_id', 0);
    if ($id > 0) {
        return $id;
    }
    if (!class_exists('WPCF7_ContactForm')) {
        return 0;
    }
    $forms = WPCF7_ContactForm::find(['posts_per_page' => 80]);
    if (!is_array($forms)) {
        return 0;
    }
    foreach ($forms as $form) {
        if ($form instanceof WPCF7_ContactForm && $form->title() === SFRFR_CF7_FEEDBACK_TITLE) {
            $id = (int) $form->id();
            if ($id > 0) {
                update_option('sfrfr_cf7_feedback_id', $id, false);
            }
            return $id;
        }
    }
    return 0;
}

function sfrfr_cf7_panel_html(string $topic): string
{
    $formId = sfrfr_cf7_feedback_id();
    $inner = $formId > 0
        ? do_shortcode('[contact-form-7 id="' . $formId . '" title="' . SFRFR_CF7_FEEDBACK_TITLE . '"]')
        : '<p class="sfrfr-note">Форма временно недоступна. Напишите на <a href="mailto:info@proverkastaza.ru">info@proverkastaza.ru</a>.</p>';

    return sprintf(
        '<div class="sfrfr-cf7-feedback" id="obratnaya-svyaz" data-sfrfr-cf7-topic="%s">'
        . '<h2>Написать нам</h2>'
        . '<p class="sfrfr-section__lead">Короткий вопрос по теме страницы. Документы и сканы сюда не отправляйте — после диалога загрузите их в кабинет.</p>'
        . '%s'
        . '</div>',
        esc_attr($topic),
        $inner
    );
}

function sfrfr_cf7_block_html(string $topic, bool $outerSection = false): string
{
    $panel = sfrfr_cf7_panel_html($topic);
    if (!$outerSection) {
        return $panel;
    }
    return '<section class="sfrfr-section sfrfr-cf7-feedback-section"><div class="sfrfr-wrap">'
        . $panel
        . '</div></section>';
}

add_filter('the_content', static function (string $content): string {
    if (is_admin() || !is_singular('page')) {
        return $content;
    }
    $topic = sfrfr_cf7_topic_for_page();
    if ($topic === '') {
        return $content;
    }
    if (str_contains($content, 'sfrfr-cf7-feedback') && !str_contains($content, SFRFR_CF7_FEEDBACK_MARKER)) {
        return $content;
    }
    if (str_contains($content, SFRFR_CF7_FEEDBACK_MARKER)) {
        return str_replace(SFRFR_CF7_FEEDBACK_MARKER, sfrfr_cf7_block_html($topic, false), $content);
    }
    return $content . sfrfr_cf7_block_html($topic, true);
}, 25);

add_action('wp_enqueue_scripts', static function (): void {
    if (is_admin() || sfrfr_cf7_topic_for_page() === '') {
        return;
    }
    $clientKey = '';
    if (function_exists('sfrfr_smartcaptcha_client_key')) {
        $clientKey = sfrfr_smartcaptcha_client_key();
    }
    if ($clientKey !== '') {
        wp_enqueue_script(
            'yandex-smartcaptcha',
            'https://smartcaptcha.cloud.yandex.ru/captcha.js',
            [],
            null,
            true
        );
        wp_add_inline_script(
            'yandex-smartcaptcha',
            'window.SFRFR_SMARTCAPTCHA_SITEKEY=' . wp_json_encode($clientKey) . ';'
            . 'window.SFRFR_SMARTCAPTCHA=' . wp_json_encode(['clientKey' => $clientKey]) . ';',
            'before'
        );
    }
    $deps = $clientKey !== '' ? ['yandex-smartcaptcha'] : [];
    wp_register_script('sfrfr-cf7-feedback', '', $deps, '20260822', true);
    wp_enqueue_script('sfrfr-cf7-feedback');
    wp_add_inline_script('sfrfr-cf7-feedback', <<<'JS'
(function () {
  function applyTopic(root) {
    var topic = root.getAttribute("data-sfrfr-cf7-topic") || "";
    if (!topic) return;
    var sel = root.querySelector('select[name="topic"]');
    if (!sel || sel.value) return;
    for (var i = 0; i < sel.options.length; i++) {
      if (sel.options[i].value === topic) {
        sel.selectedIndex = i;
        break;
      }
    }
  }

  function fillHidden(root) {
    var url = root.querySelector('input[name="page-url"]');
    if (url && !url.value) url.value = window.location.href;
  }

  function bindConsent(root) {
    root.querySelectorAll('a[href*="/soglasie/"]').forEach(function (a) {
      a.addEventListener("click", function (e) { e.stopPropagation(); });
    });
  }

  function renderCaptcha(root) {
    var key = window.SFRFR_SMARTCAPTCHA_SITEKEY
      || (window.SFRFR_SMARTCAPTCHA && window.SFRFR_SMARTCAPTCHA.clientKey)
      || "";
    var box = root.querySelector(".sfrfr-cf7-captcha");
    if (!key || !box || box.getAttribute("data-ready") === "1") return;
    var hidden = root.querySelector('input[name="smart-token"]');
    function setToken(token) {
      if (hidden) hidden.value = token || "";
    }
    function draw() {
      if (!window.smartCaptcha || typeof window.smartCaptcha.render !== "function") return false;
      window.smartCaptcha.render(box, { sitekey: key, callback: setToken });
      box.setAttribute("data-ready", "1");
      return true;
    }
    if (!draw()) {
      var n = 0;
      var t = setInterval(function () {
        n += 1;
        if (draw() || n > 40) clearInterval(t);
      }, 250);
    }
  }

  function init(root) {
    applyTopic(root);
    fillHidden(root);
    bindConsent(root);
    renderCaptcha(root);
  }

  document.querySelectorAll(".sfrfr-cf7-feedback").forEach(init);

  document.addEventListener("wpcf7mailsent", function (ev) {
    if (typeof window.sfrfrMetrikaGoal === "function") {
      window.sfrfrMetrikaGoal("cf7_feedback_ok");
    }
    var form = ev && ev.target;
    var root = form && form.closest ? form.closest(".sfrfr-cf7-feedback") : null;
    if (root) {
      setTimeout(function () { applyTopic(root); fillHidden(root); }, 80);
    }
  });
})();
JS
    );
}, 30);

add_filter('wpcf7_spam', static function ($spam, $submission = null) {
    if ($spam) {
        return $spam;
    }
    $hp = isset($_POST['sfrfr_hp']) ? trim((string) wp_unslash($_POST['sfrfr_hp'])) : '';
    if ($hp !== '') {
        return true;
    }
    return $spam;
}, 10, 2);

add_filter('wpcf7_autop_or_not', static function ($autop, $contact_form = null) {
    if ($contact_form instanceof WPCF7_ContactForm && $contact_form->title() === SFRFR_CF7_FEEDBACK_TITLE) {
        return false;
    }
    return $autop;
}, 10, 2);
