<?php
/**
 * Создаёт/обновляет форму WPForms Lite «Заявка с сайта».
 * Поля: имя (обяз.), email и телефон (хотя бы одно), канал, согласие.
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
    '6' => [
        'id' => '6',
        'type' => 'email',
        'label' => 'Электронная почта',
        'description' => 'По желанию. Нужна для кода входа в кабинет, если без телефона.',
        'required' => '0',
        'size' => 'medium',
    ],
    '2' => [
        'id' => '2',
        'type' => 'text',
        'label' => 'Телефон',
        'description' => 'По желанию. Нужен для связи / MAX, если без почты. Заполните почту или телефон.',
        'required' => '0',
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
        'description' => 'Документ: <a href="https://proverkastaza.ru/soglasie/" target="_blank" rel="noopener noreferrer">СОПД</a> (согласие на обработку персональных данных).',
        'choices' => [
            '1' => [
                'label' => 'Согласен с СОПД',
                'value' => '1',
                'image' => '',
            ],
        ],
        'required' => '1',
        'choices_images' => '0',
    ],
    '4' => [
        'id' => '4',
        'type' => 'text',
        'label' => 'smartcaptcha_token',
        'description' => '',
        'required' => '0',
        'size' => 'medium',
        'css' => 'sfrfr-recaptcha-token',
    ],
];

$settings = [
    'form_title' => $title,
    'form_desc' => 'Укажите имя и хотя бы один контакт: почту или телефон — по ним придёт код входа в кабинет. Сканы через форму не принимаются.',
    'submit_text' => 'Отправить заявку',
    'submit_text_processing' => 'Отправка…',
    'notification_enable' => '1',
    'notifications' => [
        '1' => [
            'email' => 'info@proverkastaza.ru',
            'subject' => 'Проверка стажа: заявка с сайта',
            'sender_name' => 'Проверка стажа',
            'sender_address' => 'info@proverkastaza.ru',
            'replyto' => '',
            'message' => '{all_fields}',
        ],
    ],
    'confirmations' => [
        '1' => [
            'type' => 'message',
            'message' => '<p>Спасибо! Заявка принята — обращение создано в CRM.</p><p>Осталось подтвердить вход в кабинете: код придёт на указанную почту или в MAX.</p><p><a class="sfrfr-cabinet-register" href="https://cabinet.proverkastaza.ru/?mode=register&amp;from_lead=1">Зарегистрироваться в кабинете</a> · <a href="https://max.ru/id8905998693_1_bot?startapp">Открыть MAX</a></p><p>Сканы загружайте только в MAX или кабинете.</p>',
            'message_scroll' => '1',
        ],
    ],
    'disable_entries' => '0',
];

$settings['webhooks'] = [];
$form_data = [
    'fields' => $fields,
    'id' => $form_id,
    'field_id' => 7,
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
