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
    '5' => [
        'id' => '5',
        'type' => 'radio',
        'label' => 'Предпочтительный канал',
        'choices' => [
            '1' => [
                'label' => 'MAX (мессенджер)',
                'value' => 'max_miniapp',
                'image' => '',
            ],
            '2' => [
                'label' => 'Личный кабинет на сайте',
                'value' => 'web_cabinet',
                'image' => '',
            ],
        ],
        'required' => '1',
        'choices_images' => '0',
    ],
    '3' => [
        'id' => '3',
        'type' => 'checkbox',
        'label' => 'Согласие',
        'choices' => [
            '1' => [
                'label' => 'Даю согласие на обработку имени и контакта для ответа на обращение по пункту 5.1 Политики: https://proverkastaza.ru/politika-pdn/. Сканы через форму не отправляю.',
                'value' => '',
                'image' => '',
            ],
        ],
        'required' => '1',
        'choices_images' => '0',
    ],
    '4' => [
        'id' => '4',
        'type' => 'text',
        'label' => 'recaptcha_token',
        'description' => '',
        'required' => '0',
        'size' => 'medium',
        'css' => 'sfrfr-recaptcha-token',
    ],
];

$settings = [
    'form_title' => $title,
    'form_desc' => 'Сканы документов принимаются только в защищённом кабинете после отдельного согласия.',
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
            'message' => '<p>Спасибо! Заявка принята — мы создали обращение в CRM.</p><p>Продолжите в выбранном канале:</p><ul><li><a href="https://max.ru/id8905998693_1_bot?startapp">Открыть MAX</a></li><li><a href="https://cabinet.proverkastaza.ru/?from=lead">Личный кабинет на сайте</a></li></ul><p>Сканы загружайте только в MAX или кабинете — не через эту форму. Оператор свяжется с вами по указанному контакту.</p>',
            'message_scroll' => '1',
        ],
    ],
    'disable_entries' => '0',
];

# Источник истины — MU-plugin (wpforms_process). Webhook WPForms отключаем, чтобы не дублировать лиды.
$settings['webhooks'] = [];
$form_data = [
    'fields' => $fields,
    'id' => $form_id,
    'field_id' => 6,
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
