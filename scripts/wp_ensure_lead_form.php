<?php
/**
 * Создаёт/обновляет форму WPForms Lite «Заявка с сайта».
 * Поля: имя, телефон/канал, согласие. Без файлов и СНИЛС.
 * Печатает ID формы в stdout.
 */
if (!function_exists('wpforms')) {
    echo '0';
    return;
}

$title = 'Заявка с сайта';
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
        'type' => 'name',
        'label' => 'Имя',
        'format' => 'simple',
        'required' => '1',
        'size' => 'medium',
    ],
    '2' => [
        'id' => '2',
        'type' => 'text',
        'label' => 'Телефон или канал связи',
        'description' => 'Телефон / MAX. Без СНИЛС.',
        'required' => '1',
        'size' => 'medium',
    ],
    '3' => [
        'id' => '3',
        'type' => 'checkbox',
        'label' => 'Согласие',
        'choices' => [
            '1' => [
                'label' => 'Согласен(на) на связь и обработку данных (Политика и Согласие на сайте). Сканы через форму не отправляю.',
                'value' => '',
                'image' => '',
            ],
        ],
        'required' => '1',
        'choices_images' => '0',
    ],
];

$settings = [
    'form_title' => $title,
    'form_desc' => 'Сканы документов не принимаем на сайте — только в MAX или кабинете.',
    'submit_text' => 'Отправить заявку',
    'submit_text_processing' => 'Отправка…',
    'notification_enable' => '1',
    'notifications' => [
        '1' => [
            'email' => '{admin_email}',
            'subject' => 'Проверка стажа: заявка с сайта',
            'sender_name' => 'Проверка стажа',
            'sender_address' => '{admin_email}',
            'replyto' => '',
            'message' => '{all_fields}',
        ],
    ],
    'confirmations' => [
        '1' => [
            'type' => 'message',
            'message' => '<p>Спасибо! Заявка принята.</p><p>Выберите канал работы с делом:</p><ul><li><a href="https://max.ru/id8905998693_1_bot?startapp">Мини-приложение MAX</a></li><li><a href="https://cabinet.taxi-doroga-dobra.ru/">Веб-кабинет</a></li></ul><p>Сканы документов загружайте только в MAX или кабинете — не через эту форму.</p>',
            'message_scroll' => '1',
        ],
    ],
    'disable_entries' => '0',
];

# Webhook → FastAPI public lead (если задан SFRFR_PUBLIC_LEAD_URL на VPS).
$lead_url = getenv('SFRFR_PUBLIC_LEAD_URL') ?: '';
$lead_token = getenv('SFRFR_PUBLIC_LEAD_TOKEN') ?: '';
if ($lead_url !== '') {
    $settings['webhooks'] = [
        '1' => [
            'url' => $lead_url,
            'method' => 'post',
            'format' => 'json',
            'headers' => $lead_token !== ''
                ? "X-Public-Lead-Token: {$lead_token}"
                : '',
        ],
    ];
}
$form_data = [
    'fields' => $fields,
    'id' => $form_id,
    'field_id' => 4,
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
