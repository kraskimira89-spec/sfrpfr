<?php
/**
 * Plugin Name: SFRFR SmartCaptcha (lead)
 * Description: Yandex SmartCaptcha на форме заявки + POST лида на FastAPI после WPForms.
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * Чекбокс согласия: текст-ссылка на СОПД, без строки «Документ: СОПД».
 *
 * @param array<string,mixed> $properties
 * @param array<string,mixed> $field
 * @param array<string,mixed> $form_data
 * @return array<string,mixed>
 */
add_filter('wpforms_field_properties', function ($properties, $field, $form_data) {
    if (($field['type'] ?? '') !== 'checkbox') {
        return $properties;
    }
    $css = (string) ($field['css'] ?? '');
    $title = (string) ($form_data['settings']['form_title'] ?? '');
    if (!str_contains($css, 'sfrfr-lead-consent') && $title !== 'Заявка с сайта') {
        return $properties;
    }
    $link = '<a class="sfrfr-consent-link" href="https://proverkastaza.ru/soglasie/" target="_blank" rel="noopener noreferrer">Даю согласие на обработку персональных данных*</a>';
    if (isset($properties['description']) && is_array($properties['description'])) {
        $properties['description']['value'] = '';
    }
    if (!empty($properties['inputs']) && is_array($properties['inputs'])) {
        foreach ($properties['inputs'] as $key => $input) {
            if (isset($properties['inputs'][$key]['label']['text'])) {
                $properties['inputs'][$key]['label']['text'] = $link;
            }
        }
    }
    return $properties;
}, 20, 3);

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
    // www-data не читает /opt/sfrfr/.env — публичные ключи кладём в MU-config (как Метрика).
    foreach ([
        __DIR__ . '/sfrfr-lead.config.php',
        '/opt/sfrfr/secrets/sfrfr-lead.public.php',
    ] as $cfg) {
        if (!is_readable($cfg)) {
            continue;
        }
        /** @var mixed $loaded */
        $loaded = include $cfg;
        if (!is_array($loaded)) {
            continue;
        }
        foreach ($loaded as $k => $v) {
            if (is_string($k) && (is_string($v) || is_int($v))) {
                $map[$k] = (string) $v;
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

function sfrfr_smartcaptcha_client_key(): string
{
    $key = sfrfr_env('SMARTCAPTCHA_CLIENT_KEY', sfrfr_env('SFRFR_SMARTCAPTCHA_CLIENT_KEY'));
    if ($key === '' && defined('SFRFR_SMARTCAPTCHA_CLIENT_KEY')) {
        $key = (string) SFRFR_SMARTCAPTCHA_CLIENT_KEY;
    }
    return trim($key);
}

function sfrfr_captcha_client_key(): string
{
    return sfrfr_smartcaptcha_client_key();
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
    if (is_admin()) {
        return;
    }
    // UTM first-party cookie на всех публичных страницах (сегментные лендинги + главная).
    $utm_src = '/opt/sfrfr/scripts/assets/sfrfr-utm-attr.js';
    $utm_mu = WPMU_PLUGIN_DIR . '/sfrfr-utm-attr.js';
    $utm_url = '';
    $utm_ver = '1';
    if (is_readable($utm_mu)) {
        $utm_url = content_url('mu-plugins/sfrfr-utm-attr.js');
        $utm_ver = (string) filemtime($utm_mu);
    } elseif (is_readable($utm_src)) {
        $upload = wp_upload_dir();
        $dest = trailingslashit($upload['basedir']) . 'sfrfr/sfrfr-utm-attr.js';
        if (!is_dir(dirname($dest))) {
            wp_mkdir_p(dirname($dest));
        }
        if (!is_readable($dest) || filemtime($utm_src) > (int) @filemtime($dest)) {
            @copy($utm_src, $dest);
        }
        $utm_url = trailingslashit($upload['baseurl']) . 'sfrfr/sfrfr-utm-attr.js';
        $utm_ver = (string) @filemtime($dest);
    }
    if ($utm_url !== '') {
        wp_enqueue_script('sfrfr-utm-attr', $utm_url, [], $utm_ver, true);
    }

    $client_key = sfrfr_captcha_client_key();
    if ($client_key === '') {
        return;
    }

    // Анкета и страница отзывов: SmartCaptcha без авто-класса smart-captcha.
    if (is_page('anketa-otzyv') || is_page('otzyvy')) {
        wp_enqueue_script(
            'yandex-smartcaptcha',
            'https://smartcaptcha.cloud.yandex.ru/captcha.js',
            [],
            null,
            true
        );
        wp_add_inline_script(
            'yandex-smartcaptcha',
            'window.SFRFR_SMARTCAPTCHA_SITEKEY=' . wp_json_encode($client_key) . ';'
            . 'window.SFRFR_SMARTCAPTCHA=' . wp_json_encode(['clientKey' => $client_key]) . ';',
            'before'
        );
        return;
    }

    if (!is_front_page()) {
        return;
    }
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
    wp_enqueue_script('sfrfr-smartcaptcha-lead', $url, [], $ver, true);
    wp_add_inline_script(
        'sfrfr-smartcaptcha-lead',
        'window.SFRFR_SMARTCAPTCHA=' . wp_json_encode(['clientKey' => $client_key]) . ';',
        'before'
    );
}, 20);

add_action('wp_head', function () {
    if (!is_page('anketa-otzyv') && !is_page('otzyvy')) {
        return;
    }
    $client_key = sfrfr_captcha_client_key();
    if ($client_key === '') {
        return;
    }
    echo '<script>window.SFRFR_SMARTCAPTCHA_SITEKEY=' . wp_json_encode($client_key)
        . ';window.SFRFR_SMARTCAPTCHA=' . wp_json_encode(['clientKey' => $client_key])
        . ';</script>' . "\n";
}, 4);

add_action('wp_head', function () {
    if (!is_front_page()) {
        return;
    }
    echo '<style id="sfrfr-captcha-hide">.wpforms-field.sfrfr-recaptcha-token,.wpforms-field-recaptcha_token,.wpforms-field-smartcaptcha_token{position:absolute!important;left:-9999px!important;height:0!important;overflow:hidden!important;}</style>' . "\n";
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
    if (!empty(wpforms()->process->errors[$form_id])) {
        return;
    }

    $full_name = '';
    $email = '';
    $phone = '';
    $consent = false;
    $channel = 'unset';
    $captcha = '';

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
        if (
            str_contains($label, 'smartcaptcha')
            || str_contains($label, 'recaptcha')
            || str_contains($label, 'g-recaptcha')
            || str_contains($label, 'smart-token')
        ) {
            $captcha = $value;
            continue;
        }
        if ($type === 'checkbox' || str_contains($label, 'соглас')) {
            $consent = $value !== '' && !in_array(mb_strtolower($value), ['0', 'false', 'no', 'нет'], true);
            continue;
        }
        if (
            str_contains($label, 'предпочтительн')
            || str_contains($label, 'куда ответить')
            || str_contains($label, 'ответить по заявке')
            || ($type === 'radio' && (str_contains($label, 'канал') || str_contains($label, 'ответить')))
        ) {
            $low = mb_strtolower($value);
            if (str_contains($low, 'max') || str_contains($low, 'мессенджер')) {
                $channel = 'max_miniapp';
            } elseif (str_contains($low, 'кабинет') || str_contains($low, 'сайт') || str_contains($low, 'web')) {
                $channel = 'web_cabinet';
            }
            continue;
        }
        if ($type === 'name' || $label === 'имя' || str_contains($label, 'имя') || str_contains($label, 'фио')) {
            if ($full_name === '' && $value !== '') {
                $full_name = $value;
            }
            continue;
        }
        if ($type === 'email' || str_contains($label, 'почт') || str_contains($label, 'email')) {
            if ($value !== '') {
                $email = $value;
            }
            continue;
        }
        if (
            $type === 'phone'
            || str_contains($label, 'телефон')
            || str_contains($label, 'phone')
            || ($type === 'text' && str_contains($label, 'телефон'))
        ) {
            if ($phone === '' && $value !== '') {
                $phone = $value;
            }
            continue;
        }
    }

    if ($full_name === '') {
        wpforms()->process->errors[$form_id]['header'] = 'Укажите имя.';
        return;
    }
    if ($email === '' || $phone === '') {
        wpforms()->process->errors[$form_id]['header'] =
            'Укажите электронную почту и телефон.';
        return;
    }
    if (!$consent) {
        wpforms()->process->errors[$form_id]['header'] =
            'Отметьте согласие с СОПД — без него заявку отправить нельзя.';
        return;
    }

    $payload = [
        'full_name' => mb_substr($full_name, 0, 200),
        'email' => $email !== '' ? mb_substr($email, 0, 200) : null,
        'phone' => $phone !== '' ? mb_substr($phone, 0, 64) : null,
        'consent' => true,
        'preferred_channel' => $channel,
        'source' => 'wordpress_wpforms',
        'smartcaptcha_token' => (
            $captcha !== '' && str_starts_with(sfrfr_captcha_client_key(), 'ysc1_')
        ) ? mb_substr($captcha, 0, 4000) : null,
        'recaptcha_token' => (
            $captcha !== '' && !str_starts_with(sfrfr_captcha_client_key(), 'ysc1_')
        ) ? mb_substr($captcha, 0, 4000) : (
            $captcha !== '' ? mb_substr($captcha, 0, 4000) : null
        ),
    ];

    // UTM / first-touch из cookie sfrfr_attr (90 дней) и query — без ПДн.
    $attr = [];
    if (!empty($_COOKIE['sfrfr_attr'])) {
        $decoded = json_decode(wp_unslash((string) $_COOKIE['sfrfr_attr']), true);
        if (is_array($decoded)) {
            $attr = $decoded;
        }
    }
    $utm_keys = [
        'utm_source' => 'source',
        'utm_medium' => 'medium',
        'utm_campaign' => 'campaign',
        'utm_content' => 'content',
        'utm_term' => 'term',
        'landing_variant' => 'landing_variant',
        'audience_segment' => 'audience_segment',
        'region_bucket' => 'region_bucket',
        'referral_code' => 'referral_code',
        'first_source' => 'first_source',
        'last_source' => 'last_source',
        'first_touch_at' => 'first_touch_at',
        'last_touch_at' => 'last_touch_at',
    ];
    foreach ($utm_keys as $from => $to) {
        $val = '';
        if (isset($_GET[$from]) && is_string($_GET[$from])) {
            $val = sanitize_text_field(wp_unslash($_GET[$from]));
        } elseif (isset($attr[$from]) && is_string($attr[$from])) {
            $val = sanitize_text_field($attr[$from]);
        } elseif (isset($attr[$to]) && is_string($attr[$to])) {
            $val = sanitize_text_field($attr[$to]);
        }
        if ($val !== '') {
            // source формы оставляем wordpress_wpforms; utm_source → last_source / medium…
            if ($to === 'source') {
                $payload['last_source'] = mb_substr($val, 0, 64);
                if (empty($payload['first_source'])) {
                    $payload['first_source'] = mb_substr(
                        is_string($attr['first_source'] ?? null) ? $attr['first_source'] : $val,
                        0,
                        64
                    );
                }
            } else {
                $payload[$to] = mb_substr($val, 0, ($to === 'campaign' || $to === 'content' || $to === 'term') ? 120 : 64);
            }
        }
    }

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
        if ($code === 400 && (str_contains($body, 'captcha') || str_contains($body, 'recaptcha'))) {
            $msg = 'Проверка защиты не пройдена. Отметьте «Я не робот» и отправьте заявку снова.';
        }
        if ($code === 503 && str_contains($body, 'smartcaptcha')) {
            $msg = 'Капча временно недоступна. Напишите в MAX или попробуйте позже.';
        }
        wpforms()->process->errors[$form_id]['header'] = $msg;
        return;
    }

    // Prefill регистрации в кабинете — те же контакты, что в заявке.
    $cabinet_url = sfrfr_build_cabinet_register_url($full_name, $email, $phone);
    $decoded = json_decode($body, true);
    if (is_array($decoded) && !empty($decoded['cabinet_url']) && is_string($decoded['cabinet_url'])) {
        $api_url = trim($decoded['cabinet_url']);
        if ($api_url !== '' && str_starts_with($api_url, 'https://')) {
            $cabinet_url = $api_url;
        }
    }
    if (!str_contains($cabinet_url, 'from_lead=')) {
        $cabinet_url .= (str_contains($cabinet_url, '?') ? '&' : '?') . 'from_lead=1';
    }
    $GLOBALS['sfrfr_lead_cabinet_url'] = $cabinet_url;
}, 20, 3);

/**
 * URL регистрации в кабинете с prefills из заявки.
 */
function sfrfr_build_cabinet_register_url(string $name, string $email, string $phone): string
{
    $base = rtrim(sfrfr_env('SFRFR_CABINET_PUBLIC_URL', 'https://cabinet.proverkastaza.ru'), '/');
    $q = array_filter(
        [
            'mode' => 'register',
            'from_lead' => '1',
            'name' => $name,
            'email' => $email,
            'phone' => $phone,
        ],
        static fn ($v) => is_string($v) && trim($v) !== ''
    );
    return $base . '/?' . http_build_query($q);
}

/**
 * Подставить prefilled cabinet_url в success-сообщение WPForms.
 *
 * @param string               $message
 * @param array<string,mixed>  $form_data
 * @return string
 */
add_filter('wpforms_frontend_confirmation_message', static function ($message, $form_data) {
    $url = '';
    if (!empty($GLOBALS['sfrfr_lead_cabinet_url']) && is_string($GLOBALS['sfrfr_lead_cabinet_url'])) {
        $url = $GLOBALS['sfrfr_lead_cabinet_url'];
    }
    if ($url === '') {
        return $message;
    }
    $safe = esc_url($url);
    $message = (string) $message;
    // Якорь с классом или любой href на cabinet … mode=register
    $message = preg_replace(
        '#(<a[^>]*class="[^"]*sfrfr-cabinet-register[^"]*"[^>]*href=")[^"]*(")#i',
        '$1' . $safe . '$2',
        $message,
        1
    ) ?? $message;
    $message = preg_replace(
        '#(href=")https?://cabinet\.proverkastaza\.ru/\?mode=register[^"]*(")#i',
        '$1' . $safe . '$2',
        $message,
        1
    ) ?? $message;
    return $message;
}, 10, 2);
