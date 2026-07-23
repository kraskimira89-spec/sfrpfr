<?php
/**
 * Создаёт/обновляет форму WPForms Lite «Заявка с сайта».
 * Поля: имя, телефон/канал, согласие. Без файлов и СНИЛС.
 * Печатает ID формы в stdout для bash-сида.
 */

if (!function_exists('wpforms')) {
    fwrite(STDERR, "WPForms not loaded\n");
    exit(1);
}

$title = 'Заявка с сайта';
$existing = get_posts([
    'post_type'      => 'wpforms',
    'post_status'    => 'any',
    'title'          => $title,
    'posts_per_page' => 1,
    'fields'         => 'ids',
]);

$admin_email = get_option('admin_email');

$fields = [
    '1' => [
        'id'       => '1',
        'type'     => 'text',
        'label'    => 'Имя',
        'required' => '1',
        'size'     => 'medium',
    ],
    '2' => [
        'id'          => '2',
        'type'        => 'text',
        'label'       => 'Телефон или канал связи',
        'description' => 'Телефон, MAX или другой удобный канал. Не присылайте сканы документов.',
        'required'    => '1',
        'size'        => 'medium',
    ],
    '3' => [
        'id'       => '3',
        'type'     => 'checkbox',
        'label'    => 'Согласие',
        'choices'  => [
            '1' => [
                'label' => 'Согласен(на) на связь и обработку данных обращения (см. Согласие и Политику ПДн)',
                'value' => 'Да',
            ],
        ],
        'required' => '1',
    ],
];

$settings = [
    'form_title'               => $title,
    'form_desc'                => 'Не присылайте сканы ИЛС, трудовой, паспорта или СНИЛС через эту форму.',
    'submit_text'              => 'Отправить заявку',
    'submit_text_processing'   => 'Отправка…',
    'ajax_submit'              => '1',
    'notification_enable'      => '1',
    'notifications'            => [
        '1' => [
            'notification_name' => 'Admin',
            'email'             => $admin_email,
            'subject'           => 'Заявка SFRFR с сайта',
            'sender_name'       => 'SFRFR',
            'sender_address'    => $admin_email,
            'message'           => '{all_fields}',
        ],
    ],
    'confirmations'            => [
        '1' => [
            'type'           => 'message',
            'message'        => 'Спасибо! Мы свяжемся с вами. Документы передавайте только в MAX или кабинете.',
            'message_scroll' => '1',
        ],
    ],
];

$form_data = [
    'fields'   => $fields,
    'id'       => '',
    'field_id' => 4,
    'settings' => $settings,
    'meta'     => ['template' => 'blank'],
];

$content = wpforms_encode($form_data);

if (!empty($existing)) {
    $form_id = (int) $existing[0];
    wp_update_post([
        'ID'           => $form_id,
        'post_title'   => $title,
        'post_status'  => 'publish',
        'post_content' => $content,
    ]);
} else {
    $form_id = (int) wp_insert_post([
        'post_title'   => $title,
        'post_status'  => 'publish',
        'post_type'    => 'wpforms',
        'post_content' => $content,
    ]);
    if ($form_id <= 0) {
        fwrite(STDERR, "Failed to create form\n");
        exit(1);
    }
    $form_data['id'] = (string) $form_id;
    wp_update_post([
        'ID'           => $form_id,
        'post_content' => wpforms_encode($form_data),
    ]);
}

echo $form_id;
