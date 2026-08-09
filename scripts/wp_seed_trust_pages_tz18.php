<?php
/**
 * ТЗ-18 этап 2: страницы доверия и коммерции + автор/проверяющий на постах.
 *
 * wp --path=SITE eval-file scripts/wp_seed_trust_pages_tz18.php
 */

if (!defined('ABSPATH')) {
    fwrite(STDERR, "Run via WP-CLI eval-file\n");
    exit(1);
}

$assets = getenv('SFRFR_TRUST_ASSETS') ?: (__DIR__ . '/assets/trust');
$maxUrl = getenv('MAX_CHAT_URL') ?: getenv('MAX_PUBLIC_BOT_URL') ?: 'https://max.ru/id8905998693_1_bot';
$maxUrl = preg_replace('/\?startapp.*$/i', '', $maxUrl) ?: $maxUrl;
if ($maxUrl === '') {
    $maxUrl = 'https://max.ru/id8905998693_1_bot';
}
$maxUrl = htmlspecialchars((string) $maxUrl, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');

$pages = [
    [
        'slug' => 'proverka-stazha',
        'title' => 'Проверка стажа',
        'file' => 'proverka-stazha.html',
        'seo_title' => 'Проверка стажа',
        'seo_description' => 'Услуга проверки стажа и ИЛС: сверка документов, план обращения в СФР и границы сервиса без обещания перерасчёта.',
    ],
    [
        'slug' => 'proverka-stazha-pered-pensiey',
        'title' => 'Проверка стажа перед пенсией',
        'file' => 'proverka-stazha-pered-pensiey.html',
        'seo_title' => 'Проверка стажа перед пенсией',
        'seo_description' => 'Сверка ИЛС и трудовой за 1–5 лет до пенсии: чек-лист документов и план без обещания перерасчёта.',
    ],
    [
        'slug' => 'proverka-severnogo-stazha',
        'title' => 'Проверка северного стажа',
        'file' => 'proverka-severnogo-stazha.html',
        'seo_title' => 'Проверка северного и льготного стажа',
        'seo_description' => 'Сверка периодов северного и льготного стажа по документам: что отражено в ИЛС и чего не хватает для обращения.',
    ],
    [
        'slug' => 'pomoch-rodstvenniku-proverit-stazh',
        'title' => 'Помочь родственнику проверить стаж',
        'file' => 'pomoch-rodstvenniku-proverit-stazh.html',
        'seo_title' => 'Помочь родственнику проверить стаж',
        'seo_description' => 'Как помочь родителю с проверкой стажа и ИЛС: порядок действий, согласие и безопасная загрузка документов в кабинет.',
    ],
    [
        'slug' => 'tarify',
        'title' => 'Тарифы',
        'file' => 'tarify.html',
        'seo_title' => 'Тарифы',
        'seo_description' => 'Фиксированные тарифы диагностики, сопровождения и комплекса «Под ключ» для проверки пенсионного стажа.',
    ],
    [
        'slug' => 'kontakty',
        'title' => 'Контакты',
        'file' => 'kontakty.html',
        'seo_title' => 'Контакты',
        'seo_description' => 'Телефон, почта, MAX, реквизиты ООО «ПОД ПРИСМОТРОМ» и ссылки на оферту и политику ПДн.',
    ],
    [
        'slug' => 'kak-rabotaem',
        'title' => 'Как это работает',
        'file' => 'kak-rabotaem.html',
        'seo_title' => 'Как это работает',
        'seo_description' => 'Порядок работы сервиса «Проверка стажа»: заявка, документы, диагностика, план и самостоятельная подача в СФР.',
    ],
    [
        'slug' => 'expert/lopakova-nataliya',
        'title' => 'Лопакова Наталия Федоровна',
        'file' => 'expert-lopakova.html',
        'seo_title' => 'Лопакова Н. Ф. — сервис «Проверка стажа»',
        'seo_description' => 'Лопакова Наталия Федоровна: социальный предприниматель из Ноябрьска, руководитель сервиса «Проверка стажа», проекты «Под присмотром» и публикации в СМИ.',
    ],
    [
        'slug' => 'expert/bogdanovskiy-sergey',
        'title' => 'Богдановский Сергей Викторович',
        'file' => 'expert-bogdanovskiy.html',
        'seo_title' => 'Богдановский С. В. — доступная среда',
        'seo_description' => 'Богдановский Сергей Викторович: эксперт по доступной среде и социальной мобильности из Ноябрьска, председатель «Таганая», проектный менеджер «Под присмотром».',
    ],
];

function sfrfr_trust_load(string $assets, string $file, string $maxUrl): string
{
    $path = rtrim($assets, '/\\') . DIRECTORY_SEPARATOR . $file;
    if (!is_readable($path)) {
        throw new RuntimeException("Missing trust page: {$path}");
    }
    $html = (string) file_get_contents($path);
    return str_replace('{{MAX_BTN_URL}}', $maxUrl, $html);
}

function sfrfr_trust_upsert_page(array $args): int
{
    $slug = $args['slug'];
    $existing = get_page_by_path($slug);
    $postarr = [
        'post_title' => $args['title'],
        'post_name' => basename(str_replace('\\', '/', $slug)),
        'post_status' => 'publish',
        'post_type' => 'page',
        'post_content' => $args['content'],
        'comment_status' => 'closed',
        'ping_status' => 'closed',
        'post_author' => 1,
    ];
    if ($existing instanceof WP_Post) {
        $postarr['ID'] = (int) $existing->ID;
        $id = wp_update_post($postarr, true);
    } else {
        // Для вложенного slug expert/lopakova-nataliya нужен parent.
        if (str_contains($slug, '/')) {
            $parts = explode('/', $slug);
            $parentSlug = $parts[0];
            $parent = get_page_by_path($parentSlug);
            if (!$parent) {
                $parentId = wp_insert_post([
                    'post_title' => 'Эксперты',
                    'post_name' => $parentSlug,
                    'post_status' => 'publish',
                    'post_type' => 'page',
                    'post_content' => '<p>Профили ответственных лиц сервиса «Проверка стажа».</p>',
                    'comment_status' => 'closed',
                    'ping_status' => 'closed',
                ], true);
                if (is_wp_error($parentId)) {
                    throw new RuntimeException($parentId->get_error_message());
                }
                $parentId = (int) $parentId;
            } else {
                $parentId = (int) $parent->ID;
            }
            $postarr['post_parent'] = $parentId;
            $postarr['post_name'] = $parts[1];
        }
        $id = wp_insert_post($postarr, true);
    }
    if (is_wp_error($id)) {
        throw new RuntimeException($id->get_error_message());
    }
    $id = (int) $id;
    update_post_meta($id, '_sfrfr_seo_description', $args['seo_description']);
    update_post_meta($id, '_rank_math_title', $args['seo_title']);
    update_post_meta($id, '_rank_math_description', $args['seo_description']);
    update_post_meta($id, '_yoast_wpseo_title', $args['seo_title']);
    update_post_meta($id, '_yoast_wpseo_metadesc', $args['seo_description']);
    return $id;
}

$created = [];
foreach ($pages as $page) {
    $content = sfrfr_trust_load($assets, $page['file'], $maxUrl);
    $id = sfrfr_trust_upsert_page([
        'slug' => $page['slug'],
        'title' => $page['title'],
        'content' => $content,
        'seo_title' => $page['seo_title'],
        'seo_description' => $page['seo_description'],
    ]);
    $created[$page['slug']] = $id;
    echo "PAGE {$page['slug']}={$id}\n";
}

// Хаб /expert/ — список профилей (без отдельной категории блога).
$expertParent = get_page_by_path('expert');
if ($expertParent instanceof WP_Post) {
    $indexHtml = sfrfr_trust_load($assets, 'expert-index.html', $maxUrl);
    $parentId = wp_update_post([
        'ID' => (int) $expertParent->ID,
        'post_title' => 'Эксперты',
        'post_content' => $indexHtml,
        'post_status' => 'publish',
    ], true);
    if (is_wp_error($parentId)) {
        throw new RuntimeException($parentId->get_error_message());
    }
    update_post_meta((int) $expertParent->ID, '_sfrfr_seo_description', 'Профили экспертов сервиса «Проверка стажа»: руководитель и эксперт по доступной среде.');
    update_post_meta((int) $expertParent->ID, '_rank_math_title', 'Эксперты — Проверка стажа');
    update_post_meta((int) $expertParent->ID, '_rank_math_description', 'Профили экспертов сервиса «Проверка стажа»: руководитель и эксперт по доступной среде.');
    echo "PAGE expert={$expertParent->ID}\n";
}

// Автор / проверяющий на опубликованных экспертных постах (не situacii/analitika).
$authorName = 'Лопакова Наталия Федоровна';
$authorUrl = home_url('/expert/lopakova-nataliya/');
$reviewerName = 'Редакция сервиса «Проверка стажа»';
$reviewerUrl = home_url('/expert/');
$posts = get_posts([
    'post_type' => 'post',
    'post_status' => 'publish',
    'numberposts' => -1,
    'fields' => 'ids',
]);
$marked = 0;
foreach ($posts as $postId) {
    $postId = (int) $postId;
    if (has_category(['situacii', 'analitika'], $postId)) {
        continue;
    }
    update_post_meta($postId, '_sfrfr_author_name', $authorName);
    update_post_meta($postId, '_sfrfr_author_url', $authorUrl);
    update_post_meta($postId, '_sfrfr_reviewer_name', $reviewerName);
    update_post_meta($postId, '_sfrfr_reviewer_url', $reviewerUrl);
    $marked++;
}
echo "AUTHOR_META posts={$marked}\n";

// Обновить пункты меню Primary на отдельные URL (если меню есть).
$menu = wp_get_nav_menu_object('SFRFR Primary');
if ($menu) {
    $menuId = (int) $menu->term_id;
    $items = wp_get_nav_menu_items($menuId) ?: [];
    foreach ($items as $item) {
        $title = (string) $item->title;
        $map = [
            'Тарифы' => home_url('/tarify/'),
            'О сервисе' => home_url('/proverka-stazha/'),
            'Как это работает' => home_url('/kak-rabotaem/'),
        ];
        if (isset($map[$title])) {
            update_post_meta((int) $item->ID, '_menu_item_url', $map[$title]);
            echo "MENU {$title} -> {$map[$title]}\n";
        }
    }
    // Добавить пункты, если нет (идемпотентно).
    $titles = [];
    foreach ($items as $item) {
        $titles[(string) $item->title] = true;
    }
    $ensure = [
        'Контакты' => !empty($created['kontakty']) ? home_url('/kontakty/') : null,
        'Эксперты' => home_url('/expert/'),
        'Личный кабинет' => rtrim(
            (string) (getenv('SFRFR_CABINET_PUBLIC_URL')
                ?: getenv('CABINET_URL')
                ?: 'https://cabinet.proverkastaza.ru'),
            '/',
        ) . '/',
    ];
    foreach ($ensure as $title => $url) {
        if ($url === null || isset($titles[$title])) {
            continue;
        }
        wp_update_nav_menu_item($menuId, 0, [
            'menu-item-title' => $title,
            'menu-item-url' => $url,
            'menu-item-status' => 'publish',
            'menu-item-type' => 'custom',
        ]);
        echo "MENU {$title} added\n";
    }
}

echo "OK trust pages seeded\n";
