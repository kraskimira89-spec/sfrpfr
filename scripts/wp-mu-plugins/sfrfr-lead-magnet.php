<?php
/**
 * Plugin Name: SFRFR Lead Magnet Checklist
 * Description: REST выдача лид-магнита /chek-list-dokumentov/ (согласие ПДн отдельно от маркетинга).
 */

if (!defined('ABSPATH')) {
    exit;
}

const SFRFR_LEAD_MAGNET_CONSENT_VERSION = 'pdn-leadmagnet-2026-08-23';
const SFRFR_LEAD_MAGNET_RATE_KEY = 'sfrfr_lm_rl_';

add_action('rest_api_init', static function (): void {
    register_rest_route('proverkastaza/v1', '/lead-magnet/bootstrap', [
        'methods' => 'GET',
        'permission_callback' => '__return_true',
        'callback' => static function () {
            return [
                'nonce' => wp_create_nonce('wp_rest'),
                'deliver_url' => home_url('/chek-list-dokumentov/pechat/'),
                'consent_version' => SFRFR_LEAD_MAGNET_CONSENT_VERSION,
            ];
        },
    ]);

    register_rest_route('proverkastaza/v1', '/lead-magnet', [
        'methods' => 'POST',
        'permission_callback' => '__return_true',
        'callback' => 'sfrfr_lead_magnet_handle',
    ]);
});

/**
 * @param WP_REST_Request $request
 * @return WP_REST_Response|WP_Error
 */
function sfrfr_lead_magnet_handle(WP_REST_Request $request)
{
    $ip = isset($_SERVER['REMOTE_ADDR']) ? (string) $_SERVER['REMOTE_ADDR'] : 'unknown';
    $rateKey = SFRFR_LEAD_MAGNET_RATE_KEY . md5($ip);
    $hits = (int) get_transient($rateKey);
    if ($hits >= 8) {
        return new WP_Error('rate_limited', 'Слишком много попыток. Попробуйте позже.', ['status' => 429]);
    }
    set_transient($rateKey, $hits + 1, 15 * MINUTE_IN_SECONDS);

    $params = $request->get_json_params();
    if (!is_array($params)) {
        $params = $request->get_params();
    }

    // Honeypot
    $company = trim((string) ($params['company'] ?? ''));
    if ($company !== '') {
        return new WP_REST_Response([
            'ok' => true,
            'message' => 'Готово.',
            'deliver_url' => home_url('/chek-list-dokumentov/pechat/'),
        ], 200);
    }

    $pdn = !empty($params['personal_data_consent']) && $params['personal_data_consent'] !== 'false';
    if (!$pdn) {
        return new WP_Error(
            'consent_required',
            'Нужно согласие на обработку персональных данных для выдачи чек-листа.',
            ['status' => 400]
        );
    }

    $name = sanitize_text_field((string) ($params['name'] ?? ''));
    if (mb_strlen($name) > 80) {
        $name = mb_substr($name, 0, 80);
    }

    $channel = sanitize_key((string) ($params['delivery_channel'] ?? 'email'));
    if (!in_array($channel, ['email', 'max'], true)) {
        $channel = 'email';
    }

    $email = sanitize_email((string) ($params['email'] ?? ''));
    $maxContact = sanitize_text_field((string) ($params['max_contact'] ?? ''));
    if (mb_strlen($maxContact) > 120) {
        $maxContact = mb_substr($maxContact, 0, 120);
    }

    if ($channel === 'email') {
        if ($email === '' || !is_email($email)) {
            return new WP_Error('invalid_email', 'Укажите корректный e-mail.', ['status' => 400]);
        }
    } else {
        if ($maxContact === '') {
            return new WP_Error('invalid_max', 'Укажите, как связаться в MAX, или выберите e-mail.', ['status' => 400]);
        }
    }

    $marketing = !empty($params['marketing_consent']) && $params['marketing_consent'] !== 'false';
    $source = sanitize_key((string) ($params['lead_source'] ?? 'chek-list-dokumentov'));
    $formVersion = sanitize_text_field((string) ($params['form_version'] ?? 'lead-magnet-v1'));
    $consentVersion = sanitize_text_field(
        (string) ($params['consent_version'] ?? SFRFR_LEAD_MAGNET_CONSENT_VERSION)
    );

    $deliverUrl = home_url('/chek-list-dokumentov/pechat/');
    $now = gmdate('c');

    // Уведомление оператору без лишних ПДн в subject; контакт только в теле письма.
    $to = 'info@proverkastaza.ru';
    $subject = '[SFRFR] Чек-лист документов: заявка';
    $lines = [
        'Источник: ' . $source,
        'Форма: ' . $formVersion,
        'Канал: ' . $channel,
        'Имя: ' . ($name !== '' ? $name : '—'),
        'Согласие ПДн (выдача): да',
        'Версия согласия: ' . $consentVersion,
        'Согласие маркетинг: ' . ($marketing ? 'да' : 'нет'),
        'Время UTC: ' . $now,
        'Статус: checklist_sent',
        'Выдача: ' . $deliverUrl,
    ];
    if ($channel === 'email') {
        $lines[] = 'E-mail: ' . $email;
    } else {
        $lines[] = 'MAX (как указал посетитель): ' . $maxContact;
    }
    $body = implode("\n", $lines);
    // phpcs:ignore WordPressVIPMinimum.Functions.RestrictedFunctions.wp_mail_wp_mail
    wp_mail($to, $subject, $body);

    if ($channel === 'email' && $email !== '') {
        $userSubject = 'Ваш чек-лист документов — Проверка стажа';
        $userBody = "Здравствуйте" . ($name !== '' ? ', ' . $name : '') . "!\n\n"
            . "Рабочая тетрадь (веб-версия для печати):\n"
            . $deliverUrl . "\n\n"
            . "После выписки ИЛС ответьте нам: «ИЛС получил(а)» или «Есть расхождение».\n"
            . "Не отправляйте паспорт, СНИЛС, трудовую и выписку ИЛС в открытый чат.\n\n"
            . "Решение о пенсии принимает СФР. Сервис «Проверка стажа»: https://proverkastaza.ru/\n";
        if (!$marketing) {
            $userBody .= "\nВы не давали согласие на рекламные сообщения — мы не будем слать рассылку.\n";
        }
        // phpcs:ignore WordPressVIPMinimum.Functions.RestrictedFunctions.wp_mail_wp_mail
        wp_mail($email, $userSubject, $userBody);
    }

    $message = $channel === 'email'
        ? 'Готово. Проверьте почту и откройте рабочую тетрадь по ссылке.'
        : 'Готово. Откройте рабочую тетрадь и при желании напишите в MAX: «Нужен чек-лист документов».';

    return new WP_REST_Response([
        'ok' => true,
        'message' => $message,
        'deliver_url' => $deliverUrl,
        'status' => 'checklist_sent',
        'marketing_consent' => $marketing,
    ], 200);
}
