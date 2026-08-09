<?php
/**
 * Обновить контент главной из scripts/assets/sfrfr-home.html (с формой WPForms).
 * wp eval-file scripts/wp_apply_home.php
 * Env: SFRFR_HOME_PATH, MAX_PUBLIC_BOT_URL / MAX_CHAT_URL, MAX_CHANNEL_URL
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
// ТЗ-20/21: CTA лендинга — личный чат, не mini-app (?startapp)
$max_url = preg_replace('/\?startapp.*$/i', '', $max_url) ?: $max_url;
if ($max_url === '') {
    $max_url = 'https://max.ru/id8905998693_1_bot';
}

$max_channel_url = trim((string) (getenv('MAX_CHANNEL_URL') ?: ''));
if ($max_channel_url === '') {
    $max_channel_url = (string) get_option('sfrfr_max_channel_url', '');
}
if ($max_channel_url === '') {
    $max_channel_url = 'https://max.ru/channel_proverkastaza';
}

$text = file_get_contents($home_path);
$text = str_replace('{{MAX_BTN_URL}}', $max_url, $text);
$text = str_replace('{{MAX_CHANNEL_URL}}', $max_channel_url, $text);
$cabinet_url = rtrim(
    (string) (getenv('SFRFR_CABINET_PUBLIC_URL')
        ?: getenv('CABINET_URL')
        ?: 'https://cabinet.proverkastaza.ru'),
    '/',
) . '/';
$text = str_replace('{{CABINET_URL}}', $cabinet_url, $text);

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
