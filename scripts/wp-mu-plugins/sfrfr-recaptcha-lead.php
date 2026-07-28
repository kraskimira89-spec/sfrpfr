<?php
/**
 * Plugin Name: SFRFR reCAPTCHA Enterprise (lead)
 * Description: Enterprise JS (action=lead) + POST лида на FastAPI после WPForms.
 */

if (!defined('ABSPATH')) {
    exit;
}

const SFRFR_RECAPTCHA_SITE_KEY_DEFAULT = '6Lf7UWMtAAAAANDXkb8MR9ufU8QYO9UwZsEC3NHu';

/**
 * @return array<string,string>
 */
function sfrfr_lead_env_map(): array
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

function sfrfr_env(string $key, string $default = ''): string
{
    $val = getenv($key);
    if (is_string($val) && trim($val) !== '') {
        return trim($val);
    }
    $map = sfrfr_lead_env_map();
    if (isset($map[$key]) && $map[$key] !== '') {
        return $map[$key];
    }
    return $default;
}

function sfrfr_recaptcha_site_key(): string
{
    $key = sfrfr_env('RECAPTCHA_SITE_KEY', sfrfr_env('SFRFR_RECAPTCHA_SITE_KEY'));
    if ($key === '' && defined('SFRFR_RECAPTCHA_SITE_KEY')) {
        $key = (string) SFRFR_RECAPTCHA_SITE_KEY;
    }
    return $key !== '' ? $key : SFRFR_RECAPTCHA_SITE_KEY_DEFAULT;
}

function sfrfr_public_lead_url(): string
{
    $url = sfrfr_env('SFRFR_PUBLIC_LEAD_URL');
    if ($url === '' && defined('SFRFR_PUBLIC_LEAD_URL')) {
        $url = (string) SFRFR_PUBLIC_LEAD_URL;
    }
    if ($url === '') {
        $url = 'https://api.proverkastaza.ru/api/public/leads';
    }
    return trim($url);
}

function sfrfr_public_lead_token(): string
{
    $tok = sfrfr_env('SFRFR_PUBLIC_LEAD_TOKEN', sfrfr_env('PUBLIC_LEAD_TOKEN'));
    if ($tok === '' && defined('SFRFR_PUBLIC_LEAD_TOKEN')) {
        $tok = (string) SFRFR_PUBLIC_LEAD_TOKEN;
    }
    if ($tok === '' && defined('PUBLIC_LEAD_TOKEN')) {
        $tok = (string) PUBLIC_LEAD_TOKEN;
    }
    return trim($tok);
}

add_action('wp_enqueue_scripts', function () {
    if (is_admin() || !is_front_page()) {
        return;
    }
    $site_key = sfrfr_recaptcha_site_key();
    $mu_js = WPMU_PLUGIN_DIR . '/sfrfr-recaptcha-lead.js';
    $src_js = '/opt/sfrfr/scripts/assets/sfrfr-recaptcha-lead.js';
    $url = '';
    $ver = '1';
    if (is_readable($mu_js)) {
        $url = content_url('mu-plugins/sfrfr-recaptcha-lead.js');
        $ver = (string) filemtime($mu_js);
    } else {
        $upload = wp_upload_dir();
        $dest = trailingslashit($upload['basedir']) . 'sfrfr/sfrfr-recaptcha-lead.js';
        $dest_url = trailingslashit($upload['baseurl']) . 'sfrfr/sfrfr-recaptcha-lead.js';
        $from = is_readable($src_js) ? $src_js : '';
        if ($from !== '') {
            if (!is_dir(dirname($dest))) {
                wp_mkdir_p(dirname($dest));
            }
            if (!is_readable($dest) || filemtime($from) > (int) @filemtime($dest)) {
                @copy($from, $dest);
            }
            $url = $dest_url;
            $ver = (string) @filemtime($dest);
        }
    }
    if ($url === '') {
        return;
    }
    wp_enqueue_script('sfrfr-recaptcha-lead', $url, [], $ver, true);
    wp_add_inline_script(
        'sfrfr-recaptcha-lead',
        'window.SFRFR_RECAPTCHA=' . wp_json_encode(['siteKey' => $site_key, 'action' => 'lead']) . ';',
        'before'
    );
}, 20);

add_action('wp_head', function () {
    if (!is_front_page()) {
        return;
    }
    echo '<style id="sfrfr-recaptcha-hide">.wpforms-field.sfrfr-recaptcha-token,.wpforms-field-recaptcha_token{position:absolute!important;left:-9999px!important;height:0!important;overflow:hidden!important;}</style>' . "\n";
}, 5);

/**
 * Во время обработки WPForms — создать лид в FastAPI + amoCRM.
 * При ошибке API форма НЕ считается успешной (клиент видит сообщение).
 *
 * @param array<int|string,mixed> $fields
 * @param array<string,mixed>     $entry
 * @param array<string,mixed>     $form_data
 */
add_action('wpforms_process', function ($fields, $entry, $form_data) {
    $url = sfrfr_public_lead_url();
    if ($url === '') {
        return;
    }
    $form_title = (string) ($form_data['settings']['form_title'] ?? $form_data['settings']['form_name'] ?? '');
    if ($form_title !== '' && $form_title !== 'Заявка с сайта') {
        return;
    }
    $form_id = absint($form_data['id'] ?? 0);
    if ($form_id <= 0 || !function_exists('wpforms')) {
        return;
    }
    // Уже есть ошибки валидации — не дергаем API.
    if (!empty(wpforms()->process->errors[$form_id])) {
        return;
    }

    $full_name = '';
    $contact = '';
    $consent = false;
    $channel = 'unset';
    $recaptcha = '';

    if (!is_array($fields)) {
        return;
    }
    foreach ($fields as $field) {
        if (!is_array($field)) {
            continue;
        }
        $label = mb_strtolower((string) ($field['name'] ?? $field['label'] ?? ''));
        $value = trim((string) ($field['value'] ?? ''));
        $type = (string) ($field['type'] ?? '');
        if (str_contains($label, 'recaptcha') || str_contains($label, 'g-recaptcha')) {
            $recaptcha = $value;
            continue;
        }
        if ($type === 'checkbox' || str_contains($label, 'соглас')) {
            $consent = $value !== '' && !in_array(mb_strtolower($value), ['0', 'false', 'no', 'нет'], true);
            continue;
        }
        if (str_contains($label, 'предпочтительн') || (str_contains($label, 'канал') && $type === 'radio')) {
            $low = mb_strtolower($value);
            if (str_contains($low, 'max') || str_contains($low, 'мессенджер')) {
                $channel = 'max_miniapp';
            } elseif (str_contains($low, 'кабинет') || str_contains($low, 'сайт') || str_contains($low, 'web')) {
                $channel = 'web_cabinet';
            }
            continue;
        }
        if ($type === 'name' || $label === 'имя' || str_contains($label, 'имя')) {
            if ($full_name === '' && $value !== '') {
                $full_name = $value;
            }
            continue;
        }
        if (
            $contact === ''
            && $value !== ''
            && (str_contains($label, 'телефон') || str_contains($label, 'связ') || $type === 'text' || $type === 'phone')
        ) {
            $contact = $value;
        }
    }

    if ($full_name === '' || $contact === '') {
        wpforms()->process->errors[$form_id]['header'] = 'Заполните имя и контакт для связи.';
        return;
    }
    if (!$consent) {
        wpforms()->process->errors[$form_id]['header'] = 'Нужно согласие на обработку данных обращения.';
        return;
    }

    $payload = [
        'full_name' => mb_substr($full_name, 0, 200),
        'contact' => mb_substr($contact, 0, 200),
        'consent' => true,
        'preferred_channel' => $channel,
        'source' => 'wordpress_wpforms',
        'recaptcha_token' => $recaptcha !== '' ? mb_substr($recaptcha, 0, 4000) : null,
    ];

    $headers = [
        'Content-Type' => 'application/json',
        'Accept' => 'application/json',
    ];
    $token = sfrfr_public_lead_token();
    if ($token !== '') {
        $headers['X-Public-Lead-Token'] = $token;
    }

    $response = wp_remote_post(
        $url,
        [
            'timeout' => 25,
            'headers' => $headers,
            'body' => wp_json_encode($payload),
            'data_format' => 'body',
        ]
    );
    if (is_wp_error($response)) {
        error_log('SFRFR public lead: ' . $response->get_error_message());
        wpforms()->process->errors[$form_id]['header'] =
            'Не удалось отправить заявку. Попробуйте ещё раз или напишите в MAX.';
        return;
    }
    $code = (int) wp_remote_retrieve_response_code($response);
    $body = (string) wp_remote_retrieve_body($response);
    if ($code < 200 || $code >= 300) {
        error_log('SFRFR public lead HTTP ' . $code . ': ' . substr($body, 0, 300));
        $msg = 'Не удалось создать заявку в CRM. Попробуйте ещё раз или напишите в MAX.';
        if ($code === 400 && str_contains($body, 'recaptcha')) {
            $msg = 'Проверка защиты не пройдена. Обновите страницу и отправьте заявку снова.';
        }
        wpforms()->process->errors[$form_id]['header'] = $msg;
    }
}, 20, 3);
