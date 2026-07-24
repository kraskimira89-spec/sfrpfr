<?php
/**
 * Обновить контент главной из scripts/assets/sfrfr-home.html (с формой WPForms).
 * wp eval-file scripts/wp_apply_home.php
 * Env: SFRFR_HOME_PATH, MAX_PUBLIC_BOT_URL / MAX_CHAT_URL
 */
$home_path = getenv('SFRFR_HOME_PATH') ?: dirname(__FILE__) . '/assets/sfrfr-home.html';
if (!is_readable($home_path)) {
    fwrite(STDERR, "home html not readable: {$home_path}\n");
    echo '0';
    return;
}

$max_url = getenv('MAX_CHAT_URL')
    ?: getenv('MAX_PUBLIC_BOT_URL')
    ?: 'https://max.ru/id8905998693_1_bot';
// Для CTA «Написать в MAX» на лендинге — чат без startapp, если не задано иное
if (str_contains($max_url, '?startapp') && getenv('MAX_CHAT_URL')) {
    $max_url = getenv('MAX_CHAT_URL');
}
if (!getenv('MAX_CHAT_URL') && !getenv('MAX_PUBLIC_BOT_URL')) {
    $max_url = 'https://max.ru/id8905998693_1_bot';
}

$text = file_get_contents($home_path);
$text = str_replace('{{MAX_BTN_URL}}', $max_url, $text);

$form_block = '<!-- wp:paragraph --><p><em>Форма заявки временно недоступна.</em></p><!-- /wp:paragraph -->';
if (function_exists('wpforms')) {
    $forms = wpforms()->form->get('', ['post_type' => 'wpforms']);
    $form_id = 0;
    if (is_array($forms)) {
        foreach ($forms as $form) {
            if (isset($form->post_title) && $form->post_title === 'Заявка с сайта') {
                $form_id = (int) $form->ID;
                break;
            }
        }
    }
    if ($form_id > 0) {
        $form_block = "<!-- wp:shortcode -->\n[wpforms id=\"{$form_id}\" title=\"false\" description=\"true\"]\n<!-- /wp:shortcode -->";
    }
}

$marker = '<!-- SFRFR_FORM -->';
if (!str_contains($text, $marker)) {
    fwrite(STDERR, "SFRFR_FORM marker missing\n");
    echo '0';
    return;
}
[$before, $after] = explode($marker, $text, 2);
$content = rtrim($before) . "\n<!-- /wp:html -->\n" . $form_block . "\n<!-- wp:html -->\n" . ltrim($after);

$home_id = (int) get_option('page_on_front');
if ($home_id <= 0) {
    $page = get_page_by_path('home');
    if (!$page) {
        $pages = get_posts([
            'post_type' => 'page',
            'name' => 'home',
            'post_status' => 'publish',
            'numberposts' => 1,
        ]);
        $page = $pages[0] ?? null;
    }
    $home_id = $page ? (int) $page->ID : 0;
}
if ($home_id <= 0) {
    fwrite(STDERR, "front page not found\n");
    echo '0';
    return;
}

wp_update_post([
    'ID' => $home_id,
    'post_content' => $content,
    'post_status' => 'publish',
]);
echo (string) $home_id;
