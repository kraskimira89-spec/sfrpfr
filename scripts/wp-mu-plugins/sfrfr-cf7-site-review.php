<?php
/**
 * Plugin Name: SFRFR CF7 Site Review
 * Description: Форма «Отзыв на сайте» (CF7): почта + очередь модерации API + MAX.
 */

if (!defined('ABSPATH')) {
    exit;
}

const SFRFR_CF7_SITE_REVIEW_MARKER = '<!-- SFRFR_SITE_REVIEW_FORM -->';
const SFRFR_CF7_SITE_REVIEW_TITLE = 'Отзыв на сайте';

function sfrfr_cf7_site_review_id(): int
{
    static $id = null;
    if ($id !== null) {
        return $id;
    }
    $id = (int) get_option('sfrfr_cf7_site_review_id', 0);
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
        if ($form instanceof WPCF7_ContactForm && $form->title() === SFRFR_CF7_SITE_REVIEW_TITLE) {
            $id = (int) $form->id();
            if ($id > 0) {
                update_option('sfrfr_cf7_site_review_id', $id, false);
            }
            return $id;
        }
    }
    return 0;
}

function sfrfr_cf7_site_review_panel_html(): string
{
    $formId = sfrfr_cf7_site_review_id();
    $inner = $formId > 0
        ? do_shortcode('[contact-form-7 id="' . $formId . '" title="' . SFRFR_CF7_SITE_REVIEW_TITLE . '"]')
        : '<p class="sfrfr-note">Форма временно недоступна. Напишите на <a href="mailto:proverkastaza@yandex.ru">proverkastaza@yandex.ru</a>.</p>';

    return '<div class="sfrfr-cf7-site-review" id="sfrfr-otzyvy-cf7">'
        . $inner
        . '</div>';
}

add_filter('the_content', static function (string $content): string {
    if (is_admin() || !is_singular('page')) {
        return $content;
    }
    if (!str_contains($content, SFRFR_CF7_SITE_REVIEW_MARKER)) {
        return $content;
    }
    return str_replace(SFRFR_CF7_SITE_REVIEW_MARKER, sfrfr_cf7_site_review_panel_html(), $content);
}, 24);

add_action('wp_enqueue_scripts', static function (): void {
    if (is_admin() || !is_page('otzyvy')) {
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
    wp_register_script('sfrfr-cf7-site-review', '', $deps, '20260827', true);
    wp_enqueue_script('sfrfr-cf7-site-review');
    wp_add_inline_script('sfrfr-cf7-site-review', <<<'JS'
(function () {
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
    bindConsent(root);
    renderCaptcha(root);
  }

  document.querySelectorAll(".sfrfr-cf7-site-review").forEach(init);

  document.addEventListener("wpcf7mailsent", function (ev) {
    if (typeof window.sfrfrMetrikaGoal === "function") {
      window.sfrfrMetrikaGoal("cf7_site_review_ok");
    }
    var form = ev && ev.target;
    var root = form && form.closest ? form.closest(".sfrfr-cf7-site-review") : null;
    if (root) {
      setTimeout(function () { renderCaptcha(root); }, 80);
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
    if (!$submission instanceof WPCF7_Submission) {
        return $spam;
    }
    $contact = $submission->get_contact_form();
    if (!($contact instanceof WPCF7_ContactForm) || $contact->title() !== SFRFR_CF7_SITE_REVIEW_TITLE) {
        return $spam;
    }
    $hp = isset($_POST['sfrfr_hp']) ? trim((string) wp_unslash($_POST['sfrfr_hp'])) : '';
    if ($hp !== '') {
        return true;
    }
    return $spam;
}, 10, 2);

/** CF7: обязательный textarea* валидируется отдельным хуком `wpcf7_validate_textarea*`. */
$sfrfr_cf7_site_review_validate_len = static function ($result, $tag) {
    if (!($result instanceof WPCF7_Validation) || !is_object($tag)) {
        return $result;
    }
    $name = isset($tag->name) ? (string) $tag->name : '';
    if ($name !== 'your-review') {
        return $result;
    }
    $submission = WPCF7_Submission::get_instance();
    if (!$submission instanceof WPCF7_Submission) {
        return $result;
    }
    $contact = $submission->get_contact_form();
    if (!($contact instanceof WPCF7_ContactForm) || $contact->title() !== SFRFR_CF7_SITE_REVIEW_TITLE) {
        return $result;
    }
    $posted = $submission->get_posted_data();
    $text = isset($posted['your-review']) ? trim((string) $posted['your-review']) : '';
    $len = function_exists('mb_strlen') ? mb_strlen($text) : strlen($text);
    // #region agent log
    @file_put_contents(
        '/tmp/debug-e6d4c0.log',
        wp_json_encode([
            'sessionId' => 'e6d4c0',
            'hypothesisId' => 'D',
            'location' => 'sfrfr-cf7-site-review.php:validate_len',
            'message' => 'cf7 review length check',
            'data' => ['len' => $len, 'ok' => $len >= 40],
            'timestamp' => (int) round(microtime(true) * 1000),
        ], JSON_UNESCAPED_UNICODE) . "\n",
        FILE_APPEND
    );
    // #endregion
    if ($len < 40) {
        $result->invalidate($tag, 'Напишите чуть подробнее — хотя бы два-три предложения.');
    }
    return $result;
};
add_filter('wpcf7_validate_textarea', $sfrfr_cf7_site_review_validate_len, 20, 2);
add_filter('wpcf7_validate_textarea*', $sfrfr_cf7_site_review_validate_len, 20, 2);

add_filter('wpcf7_autop_or_not', static function ($autop, $contact_form = null) {
    if ($contact_form instanceof WPCF7_ContactForm && $contact_form->title() === SFRFR_CF7_SITE_REVIEW_TITLE) {
        return false;
    }
    return $autop;
}, 10, 2);

/**
 * Очередь модерации + MAX (+ письмо через API, если CF7 mail не ушёл).
 *
 * @param bool $mailAlreadySent true = CF7 уже отправил письмо; false = API шлёт через Яндекс SMTP.
 */
function sfrfr_cf7_site_review_enqueue_api(bool $mailAlreadySent): bool
{
    $submission = WPCF7_Submission::get_instance();
    if (!$submission instanceof WPCF7_Submission) {
        return false;
    }
    $posted = $submission->get_posted_data();
    $text = isset($posted['your-review']) ? trim((string) $posted['your-review']) : '';
    if ($text === '') {
        return false;
    }

    $url = 'https://api.proverkastaza.ru/api/public/site-reviews';
    if (function_exists('sfrfr_env')) {
        $custom = sfrfr_env('SFRFR_PUBLIC_SITE_REVIEWS_URL');
        if ($custom !== '') {
            $url = $custom;
        }
    }

    $headers = [
        'Content-Type' => 'application/json',
        'Accept' => 'application/json',
    ];
    if (function_exists('sfrfr_public_lead_token')) {
        $token = sfrfr_public_lead_token();
        if ($token !== '') {
            $headers['X-Public-Lead-Token'] = $token;
        }
    }

    $payload = [
        'text' => mb_substr($text, 0, 600),
        'consent' => true,
        'mail_already_sent' => $mailAlreadySent,
        'source' => 'cf7',
    ];
    $smart = isset($posted['smart-token']) ? trim((string) $posted['smart-token']) : '';
    if ($smart !== '') {
        $payload['smartcaptcha_token'] = $smart;
    }

    $response = wp_remote_post(
        $url,
        [
            'timeout' => 20,
            'headers' => $headers,
            'body' => wp_json_encode($payload),
            'data_format' => 'body',
        ]
    );
    if (is_wp_error($response)) {
        error_log('SFRFR site review queue: ' . $response->get_error_message());
        // #region agent log
        @file_put_contents(
            '/tmp/debug-e6d4c0.log',
            wp_json_encode([
                'sessionId' => 'e6d4c0',
                'hypothesisId' => 'B',
                'location' => 'sfrfr-cf7-site-review.php:enqueue',
                'message' => 'queue wp_error',
                'data' => [
                    'mailAlreadySent' => $mailAlreadySent,
                    'hasToken' => isset($headers['X-Public-Lead-Token']),
                    'textLen' => function_exists('mb_strlen') ? mb_strlen($text) : strlen($text),
                    'err' => $response->get_error_message(),
                ],
                'timestamp' => (int) round(microtime(true) * 1000),
            ], JSON_UNESCAPED_UNICODE) . "\n",
            FILE_APPEND
        );
        // #endregion
        return false;
    }
    $code = (int) wp_remote_retrieve_response_code($response);
    $respBody = substr((string) wp_remote_retrieve_body($response), 0, 300);
    // #region agent log
    @file_put_contents(
        '/tmp/debug-e6d4c0.log',
        wp_json_encode([
            'sessionId' => 'e6d4c0',
            'hypothesisId' => 'B',
            'location' => 'sfrfr-cf7-site-review.php:enqueue',
            'message' => 'queue http result',
            'data' => [
                'mailAlreadySent' => $mailAlreadySent,
                'hasToken' => isset($headers['X-Public-Lead-Token']),
                'textLen' => function_exists('mb_strlen') ? mb_strlen($text) : strlen($text),
                'code' => $code,
                'body' => $respBody,
            ],
            'timestamp' => (int) round(microtime(true) * 1000),
        ], JSON_UNESCAPED_UNICODE) . "\n",
        FILE_APPEND
    );
    // #endregion
    if ($code < 200 || $code >= 300) {
        error_log('SFRFR site review queue HTTP ' . $code . ': ' . $respBody);
        return false;
    }
    return true;
}

add_action('wpcf7_mail_sent', static function ($contact_form): void {
    if (!($contact_form instanceof WPCF7_ContactForm)) {
        return;
    }
    if ($contact_form->title() !== SFRFR_CF7_SITE_REVIEW_TITLE) {
        return;
    }
    sfrfr_cf7_site_review_enqueue_api(true);
}, 20);

/** WP без SMTP: Flamingo пишет, mail падает — API шлёт письмо через Яндекс SMTP. */
add_action('wpcf7_mail_failed', static function ($contact_form): void {
    if (!($contact_form instanceof WPCF7_ContactForm)) {
        return;
    }
    if ($contact_form->title() !== SFRFR_CF7_SITE_REVIEW_TITLE) {
        return;
    }
    $ok = sfrfr_cf7_site_review_enqueue_api(false);
    if ($ok) {
        $submission = WPCF7_Submission::get_instance();
        if ($submission instanceof WPCF7_Submission) {
            $submission->set_response(
                'Спасибо. Отзыв принят и ждёт проверки перед публикацией на сайте.'
            );
        }
    }
}, 20);

/** Показать клиенту успех, если при mail_failed очередь API всё же приняла отзыв. */
add_filter('wpcf7_feedback_response', static function ($response, $result) {
    if (!is_array($response) || !is_array($result)) {
        return $response;
    }
    if (($result['status'] ?? '') !== 'mail_failed') {
        return $response;
    }
    $submission = WPCF7_Submission::get_instance();
    if (!$submission instanceof WPCF7_Submission) {
        return $response;
    }
    $contact = $submission->get_contact_form();
    if (!($contact instanceof WPCF7_ContactForm) || $contact->title() !== SFRFR_CF7_SITE_REVIEW_TITLE) {
        return $response;
    }
    $msg = $submission->get_response();
    if (is_string($msg) && str_contains($msg, 'принят')) {
        $response['status'] = 'mail_sent';
        $response['message'] = $msg;
    }
    return $response;
}, 20, 2);
