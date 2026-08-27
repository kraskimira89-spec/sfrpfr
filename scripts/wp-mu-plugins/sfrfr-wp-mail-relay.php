<?php
/**
 * Plugin Name: SFRFR WP Mail Relay
 * Description: wp_mail → API SFRFR → Яндекс SMTP (без SMTP-плагина и postfix на WP).
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * @return string
 */
function sfrfr_wp_mail_relay_url(): string
{
    if (function_exists('sfrfr_env')) {
        $custom = sfrfr_env('SFRFR_WP_MAIL_RELAY_URL');
        if ($custom !== '') {
            return $custom;
        }
    }
    return 'https://api.proverkastaza.ru/api/public/wp-mail-relay';
}

/**
 * @param array|false $null
 * @param array       $atts
 * @return array|false|null
 */
add_filter('pre_wp_mail', static function ($null, $atts) {
    if ($null !== null) {
        return $null;
    }
    if (!is_array($atts)) {
        return null;
    }
    $to = $atts['to'] ?? '';
    if (is_array($to)) {
        $to = implode(',', array_map('strval', $to));
    }
    $to = trim((string) $to);
    $subject = trim((string) ($atts['subject'] ?? ''));
    $message = (string) ($atts['message'] ?? '');
    if ($to === '' || $subject === '' || $message === '') {
        return null;
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

    $isHtml = false;
    $rawHeaders = $atts['headers'] ?? [];
    if (is_string($rawHeaders)) {
        $rawHeaders = preg_split('/\r\n|\r|\n/', $rawHeaders) ?: [];
    }
    if (is_array($rawHeaders)) {
        foreach ($rawHeaders as $h) {
            if (stripos((string) $h, 'content-type:') !== false && stripos((string) $h, 'text/html') !== false) {
                $isHtml = true;
                break;
            }
        }
    }

    $payload = [
        'to' => $to,
        'subject' => mb_substr($subject, 0, 200),
        'body' => $isHtml ? wp_strip_all_tags($message) : $message,
    ];
    if ($isHtml) {
        $payload['html'] = $message;
    }

    $response = wp_remote_post(
        sfrfr_wp_mail_relay_url(),
        [
            'timeout' => 25,
            'headers' => $headers,
            'body' => wp_json_encode($payload),
            'data_format' => 'body',
        ]
    );
    if (is_wp_error($response)) {
        error_log('SFRFR wp_mail relay: ' . $response->get_error_message());
        // #region agent log
        @file_put_contents(
            '/tmp/debug-e6d4c0.log',
            wp_json_encode([
                'sessionId' => 'e6d4c0',
                'hypothesisId' => 'A',
                'location' => 'sfrfr-wp-mail-relay.php:pre_wp_mail',
                'message' => 'relay wp_error',
                'data' => [
                    'subjectLen' => function_exists('mb_strlen') ? mb_strlen($subject) : strlen($subject),
                    'bodyLen' => function_exists('mb_strlen') ? mb_strlen($message) : strlen($message),
                    'hasSnilsWord' => (function_exists('mb_stripos')
                        ? mb_stripos($message, 'СНИЛС') !== false
                        : stripos($message, 'СНИЛС') !== false),
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
            'hypothesisId' => 'A',
            'location' => 'sfrfr-wp-mail-relay.php:pre_wp_mail',
            'message' => 'relay http result',
            'data' => [
                'subjectLen' => function_exists('mb_strlen') ? mb_strlen($subject) : strlen($subject),
                'bodyLen' => function_exists('mb_strlen') ? mb_strlen($message) : strlen($message),
                'hasSnilsWord' => (function_exists('mb_stripos')
                    ? mb_stripos($message, 'СНИЛС') !== false
                    : stripos($message, 'СНИЛС') !== false),
                'code' => $code,
                'body' => $respBody,
            ],
            'timestamp' => (int) round(microtime(true) * 1000),
        ], JSON_UNESCAPED_UNICODE) . "\n",
        FILE_APPEND
    );
    // #endregion
    if ($code < 200 || $code >= 300) {
        error_log('SFRFR wp_mail relay HTTP ' . $code . ': ' . $respBody);
        return false;
    }
    return true;
}, 10, 2);
