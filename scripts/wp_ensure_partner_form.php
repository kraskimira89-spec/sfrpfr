<?php
/**
 * WPForms Lite: форма B2B «Партнёрство» для /partneram/.
 * Без СНИЛС, паспортов и загрузки документов граждан.
 *
 * wp eval-file scripts/wp_ensure_partner_form.php
 */
if (!function_exists('wpforms')) {
    echo '0';
    return;
}

$title = 'Партнёрство';
$forms = wpforms()->form->get('', ['post_type' => 'wpforms']);
$form_id = 0;
if (is_array($forms)) {
    foreach ($forms as $form) {
        if (isset($form->post_title) && $form->post_title === $title) {
            $form_id = (int) $form->ID;
            break;
        }
    }
}

$fields = [
    '1' => [
        'id' => '1',
        'type' => 'text',
        'label' => 'Организация',
        'required' => '1',
        'size' => 'medium',
        'css' => 'sfrfr-partner-org',
    ],
    '2' => [
        'id' => '2',
        'type' => 'name',
        'label' => 'ФИО и должность',
        'format' => 'simple',
        'required' => '1',
        'size' => 'medium',
        'css' => 'sfrfr-partner-name',
    ],
    '3' => [
        'id' => '3',
        'type' => 'text',
        'label' => 'Рабочий телефон',
        'required' => '1',
        'size' => 'medium',
        'css' => 'sfrfr-partner-phone',
    ],
    '4' => [
        'id' => '4',
        'type' => 'email',
        'label' => 'Рабочая почта',
        'required' => '1',
        'size' => 'medium',
        'css' => 'sfrfr-partner-email',
    ],
    '5' => [
        'id' => '5',
        'type' => 'text',
        'label' => 'Регион',
        'required' => '1',
        'size' => 'medium',
        'css' => 'sfrfr-partner-region',
    ],
    '6' => [
        'id' => '6',
        'type' => 'textarea',
        'label' => 'Кратко опишите формат взаимодействия',
        'required' => '1',
        'size' => 'medium',
        'css' => 'sfrfr-partner-format',
    ],
    '7' => [
        'id' => '7',
        'type' => 'checkbox',
        'label' => 'Согласие на обработку персональных данных',
        'choices' => [
            '1' => [
                'label' => 'Даю согласие на обработку персональных данных*',
                'value' => '1',
                'image' => '',
            ],
        ],
        'required' => '1',
        'choices_images' => '0',
        'css' => 'sfrfr-partner-consent sfrfr-lead-consent',
    ],
    '8' => [
        'id' => '8',
        'type' => 'text',
        'label' => 'smartcaptcha_token',
        'required' => '0',
        'size' => 'medium',
        'css' => 'sfrfr-recaptcha-token',
    ],
];

$settings = [
    'form_title' => $title,
    'form_desc' => 'Обращение от организации или партнёра. Не отправляйте через эту форму документы граждан, СНИЛС и паспортные данные.',
    'submit_text' => 'Отправить обращение',
    'submit_text_processing' => 'Отправка…',
    'required_indicator' => '*',
    'notification_enable' => '1',
    'notifications' => [
        '1' => [
            'email' => 'info@proverkastaza.ru',
            'subject' => 'Проверка стажа: партнёрство (partnerstvo)',
            'sender_name' => 'Проверка стажа',
            'sender_address' => 'info@proverkastaza.ru',
            'replyto' => '{field_id="4"}',
            'message' => "Тема: partnerstvo\n\n{all_fields}",
        ],
    ],
    'confirmations' => [
        '1' => [
            'type' => 'message',
            'message' => '<p>Спасибо! Обращение получено. Мы свяжемся с вами по рабочим контактам для обсуждения формата партнёрства.</p><p>Не передавайте через эту форму документы граждан и персональные данные посетителей приёмных.</p>',
            'message_scroll' => '1',
        ],
    ],
    'disable_entries' => '0',
    'webhooks' => [],
];

$form_data = [
    'fields' => $fields,
    'id' => $form_id,
    'field_id' => 9,
    'settings' => $settings,
    'meta' => ['template' => 'blank'],
];

$postarr = [
    'post_title' => $title,
    'post_status' => 'publish',
    'post_type' => 'wpforms',
    'post_content' => wpforms_encode($form_data),
];

if ($form_id > 0) {
    $postarr['ID'] = $form_id;
    $result = wp_update_post($postarr, true);
} else {
    $result = wp_insert_post($postarr, true);
}

if (is_wp_error($result)) {
    echo '0';
    return;
}

echo (int) $result;
