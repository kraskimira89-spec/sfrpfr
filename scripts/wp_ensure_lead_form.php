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
        'description' => 'Телефон, MAX или другой удобный канал. Не указывайте СНИЛС.',
        'required' => '1',
        'size' => 'medium',
    ],
    '3' => [
        'id' => '3',
        'type' => 'checkbox',
        'label' => 'Согласие',
        'choices' => [
            '1' => [
                'label' => 'Согласен(на) на связь и обработку данных обращения (см. Политику и Согласие на сайте). Сканы документов через эту форму не отправляю.',
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
    'form_desc' => 'Не присылайте сканы ИЛС, трудовых, паспортов или СНИЛС через сайт. Документы — только в MAX или кабинете.',
    'submit_text' => 'Отправить заявку',
    'submit_text_processing' => 'Отправка…',
    'notification_enable' => '1',
    'notifications' => [
        '1' => [
            'email' => '{admin_email}',
            'subject' => 'SFRFR: заявка с сайта',
            'sender_name' => 'SFRFR',
            'sender_address' => '{admin_email}',
            'replyto' => '',
            'message' => '{all_fields}',
        ],
    ],
    'confirmations' => [
        '1' => [
            'type' => 'message',
            'message' => '<p>Спасибо! Мы свяжемся с вами и пришлём ссылку на чат MAX. Документы загружайте только там или в кабинете.</p>',
            'message_scroll' => '1',
        ],
    ],
    'disable_entries' => '0',
];

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
