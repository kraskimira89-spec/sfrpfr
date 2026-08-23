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
        'seo_title' => 'Проверка стажа, а не калькулятор пенсии',
        'seo_description' => 'Нужен расчёт пенсии или калькулятор стажа? Сумму считает СФР. Мы сверяем ИЛС и документы и готовим план обращения — без обещания выплат.',
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
        'title' => 'Северный стаж для пенсии: сверка периодов',
        'file' => 'proverka-severnogo-stazha.html',
        'seo_title' => 'Северный стаж для пенсии и пенсия крайний север',
        'seo_description' => 'Северный стаж для пенсии: сверка в районах Крайнего Севера и приравненных местностях. Без обещания льготы — решение принимает СФР.',
    ],
    [
        'slug' => 'ne-uchli-stazh',
        'title' => 'Не учли стаж в ИЛС: что проверить',
        'file' => 'ne-uchli-stazh.html',
        'seo_title' => 'Не учли стаж в ИЛС — сверка документов',
        'seo_description' => 'Не учтён стаж или стаж не учтён в ИЛС: сверка трудовой и выписки, чек-лист и план. Без обещания перерасчёта — решение принимает СФР.',
    ],
    [
        'slug' => 'arhivnaya-spravka-stazh',
        'title' => 'Архивная справка о стаже: зачем и куда',
        'file' => 'arhivnaya-spravka-stazh.html',
        'seo_title' => 'Архивная справка о стаже для СФР',
        'seo_description' => 'Архивная справка о стаже и запрос в архив: ликвидация работодателя, что подготовить для СФР. Без обещания перерасчёта.',
    ],
    [
        'slug' => 'otkaz-sfr',
        'title' => 'Отказ в назначении пенсии: что проверить',
        'file' => 'otkaz-sfr.html',
        'seo_title' => 'Отказ СФР в назначении пенсии — сверка',
        'seo_description' => 'Отказ СФР в назначении пенсии: что проверить в документах и как готовить следующий шаг. Решение снова принимает СФР.',
    ],
    [
        'slug' => 'pomoch-rodstvenniku-proverit-stazh',
        'title' => 'Помочь родственнику проверить стаж',
        'file' => 'pomoch-rodstvenniku-proverit-stazh.html',
        'seo_title' => 'Помочь родственнику проверить стаж',
        'seo_description' => 'Как помочь родителю с проверкой стажа и ИЛС: порядок действий, согласие и безопасная загрузка документов в кабинет.',
    ],
    [
        'slug' => 'stazh-do-2002',
        'title' => 'Как подтвердить стаж до 2002 года',
        'file' => 'stazh-do-2002.html',
        'seo_title' => 'Как подтвердить стаж до 2002 года',
        'seo_description' => 'Страховой стаж до 2002: сверка ИЛС, трудовой и справок. Готовим чек-лист и план обращения — подаёте вы сами, решение принимает СФР. Это не калькулятор стажа.',
    ],
    [
        'slug' => 'tarify',
        'title' => 'Тарифы',
        'file' => 'tarify.html',
        'seo_title' => 'Тарифы',
        'seo_description' => 'Поэтапные тарифы проверки стажа: диагностика 3000 ₽, подготовка документов 5000 ₽, сопровождение до подачи 8000 ₽.',
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
        'slug' => 'otzyvy',
        'title' => 'Отзывы',
        'file' => 'otzyvy.html',
        'seo_title' => 'Отзывы',
        'seo_description' => 'Отзывы о сервисе «Проверка стажа»: форма на сайте после модерации и рейтинг на Яндекс Картах. Без обещания перерасчёта.',
    ],
    [
        'slug' => 'partneram',
        'title' => 'Партнёрам',
        'file' => 'partneram.html',
        'seo_title' => 'Партнёрам — навигация по пенсионным документам | Проверка стажа',
        'seo_description' => 'Партнёрский формат информационно-документарной помощи: выписка ИЛС, пенсионный стаж, трудовые документы, подготовка обращений в СФР.',
    ],
    [
        'slug' => 'chek-list-dokumentov',
        'title' => 'Соберите пенсионные документы без спешки и путаницы',
        'file' => 'chek-list-dokumentov.html',
        'seo_title' => 'Чек-лист документов для проверки стажа | Проверка стажа',
        'seo_description' => 'Скачайте бесплатную рабочую тетрадь: как собрать пенсионные документы, получить выписку ИЛС и отметить возможные расхождения.',
    ],
    [
        'slug' => 'chek-list-dokumentov/pechat',
        'title' => 'Чек-лист для печати',
        'file' => 'chek-list-dokumentov-pechat.html',
        'seo_title' => 'Чек-лист пенсионных документов для печати',
        'seo_description' => 'Печатная версия чек-листа: папка документов, ИЛС, сверка и карточка спорного периода. Решение о пенсии принимает СФР.',
        'noindex' => true,
    ],
    [
        'slug' => 'chek-list-dokumentov/a4',
        'title' => 'Чек-лист A4 — одна страница',
        'file' => 'chek-list-dokumentov-a4.html',
        'seo_title' => 'Чек-лист документов A4 — одна страница',
        'seo_description' => 'Компактный чек-лист на одном листе: ИЛС, трудовая, карточка спорного периода. Без обещания перерасчёта — решает СФР.',
        'noindex' => true,
    ],
    [
        'slug' => 'anketa-otzyv',
        'title' => 'Сформулировать отзыв',
        'file' => 'anketa-otzyv.html',
        'seo_title' => 'Сформулировать отзыв о сервисе',
        'seo_description' => 'Короткая анкета: соберём черновик отзыва. Публикуете вы сами на Яндекс Картах. Без обещания перерасчёта.',
        'noindex' => true,
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
    $replacements = [
        '{{MAX_BTN_URL}}' => $maxUrl,
        '{{PHONE}}' => '+7&nbsp;909&nbsp;195‑04‑08',
        '{{EMAIL}}' => 'info@proverkastaza.ru',
    ];
    return str_replace(array_keys($replacements), array_values($replacements), $html);
}

function sfrfr_trust_seed_presentation(int $pageId, string $repoRoot): void
{
    if ($pageId <= 0) {
        return;
    }
    if ((int) get_post_meta($pageId, '_sfrfr_presentation_file', true) > 0) {
        echo "PRESENTATION partneram=skip (meta exists)\n";
        return;
    }

    $candidates = [
        $repoRoot . '/docs/proverkastaza_presentation_for_deputy.pptx',
        dirname(__DIR__) . '/docs/proverkastaza_presentation_for_deputy.pptx',
    ];
    $pptxPath = '';
    foreach ($candidates as $candidate) {
        if (is_readable($candidate)) {
            $pptxPath = $candidate;
            break;
        }
    }
    if ($pptxPath === '') {
        echo "PRESENTATION partneram=skip (file missing)\n";
        return;
    }

    require_once ABSPATH . 'wp-admin/includes/file.php';
    require_once ABSPATH . 'wp-admin/includes/media.php';
    require_once ABSPATH . 'wp-admin/includes/image.php';

    $filename = 'proverkastaza-presentation-for-partners.pptx';
    $tmp = wp_tempnam($filename);
    if (!$tmp || !copy($pptxPath, $tmp)) {
        echo "PRESENTATION partneram=fail (copy)\n";
        return;
    }
    $fileArray = [
        'name' => $filename,
        'tmp_name' => $tmp,
    ];
    $attachId = media_handle_sideload($fileArray, $pageId, 'Презентация сервиса для партнёров');
    if (is_wp_error($attachId)) {
        @unlink($tmp);
        echo 'PRESENTATION partneram=fail ' . $attachId->get_error_message() . "\n";
        return;
    }
    update_post_meta($pageId, '_sfrfr_presentation_file', (int) $attachId);
    echo 'PRESENTATION partneram=' . (int) $attachId . "\n";
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
    update_post_meta($id, '_sfrfr_seo_title', $args['seo_title']);
    update_post_meta($id, '_sfrfr_seo_description', $args['seo_description']);
    if (!empty($args['noindex'])) {
        update_post_meta($id, '_rank_math_robots', ['noindex']);
        update_post_meta($id, '_yoast_wpseo_meta-robots-noindex', '1');
    }
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
        'noindex' => !empty($page['noindex']),
    ]);
    $created[$page['slug']] = $id;
    echo "PAGE {$page['slug']}={$id}\n";
}

if (!empty($created['partneram'])) {
    $repoRoot = getenv('SFRFR_REPO_ROOT') ?: dirname(__DIR__);
    sfrfr_trust_seed_presentation((int) $created['partneram'], $repoRoot);
    $partnerFormScript = dirname(__DIR__) . '/wp_ensure_partner_form.php';
    if (is_readable($partnerFormScript)) {
        require $partnerFormScript;
        echo "PARTNER_FORM ensured\n";
    }
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
    // Якорные пункты под «Главная» (/#tarify и т.п.) не переписываем на отдельные URL.
    foreach ($items as $item) {
        $title = (string) $item->title;
        $parentId = (int) ($item->menu_item_parent ?? 0);
        $url = (string) ($item->url ?? '');
        $isHomeAnchor = $parentId > 0 && str_contains($url, '/#');
        $map = [
            'О сервисе' => home_url('/proverka-stazha/'),
        ];
        if ($isHomeAnchor) {
            continue;
        }
        if (isset($map[$title])) {
            update_post_meta((int) $item->ID, '_menu_item_url', $map[$title]);
            echo "MENU {$title} -> {$map[$title]}\n";
        }
    }
    // Добавить верхнеуровневые пункты, если нет (идемпотентно).
    // Подменю «Эксперты» / «Услуги» / «Статьи» собирает wp_apply_landing_vps.sh.
    $titles = [];
    $expertParentId = 0;
    foreach ($items as $item) {
        $titles[(string) $item->title] = true;
        if ((string) $item->title === 'Эксперты' && (int) ($item->menu_item_parent ?? 0) === 0) {
            $expertParentId = (int) $item->ID;
        }
    }
    $ensure = [
        'Отзывы' => !empty($created['otzyvy']) ? home_url('/otzyvy/') : home_url('/otzyvy/'),
        'Партнёрам' => home_url('/partneram/'),
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
            // Обновить URL существующего пункта «Отзывы», если ведёт не туда.
            if ($title === 'Отзывы' && isset($titles[$title])) {
                foreach ($items as $item) {
                    if ((string) $item->title !== 'Отзывы') {
                        continue;
                    }
                    $cur = (string) ($item->url ?? '');
                    if (!str_contains($cur, '/otzyvy')) {
                        update_post_meta((int) $item->ID, '_menu_item_url', home_url('/otzyvy/'));
                        echo "MENU Отзывы URL -> /otzyvy/\n";
                    }
                }
            }
            continue;
        }
        $newId = wp_update_nav_menu_item($menuId, 0, [
            'menu-item-title' => $title,
            'menu-item-url' => $url,
            'menu-item-status' => 'publish',
            'menu-item-type' => 'custom',
        ]);
        echo "MENU {$title} added\n";
        if ($title === 'Эксперты' && is_int($newId) && $newId > 0) {
            $expertParentId = $newId;
        }
    }
    if ($expertParentId > 0) {
        $expertChildren = [
            'Все эксперты' => home_url('/expert/'),
            'Лопакова Н. Ф.' => home_url('/expert/lopakova-nataliya/'),
            'Богдановский С. В.' => home_url('/expert/bogdanovskiy-sergey/'),
        ];
        foreach ($expertChildren as $title => $url) {
            if (isset($titles[$title])) {
                continue;
            }
            wp_update_nav_menu_item($menuId, 0, [
                'menu-item-title' => $title,
                'menu-item-url' => $url,
                'menu-item-status' => 'publish',
                'menu-item-type' => 'custom',
                'menu-item-parent-id' => $expertParentId,
            ]);
            echo "MENU {$title} under Эксперты\n";
        }
    }

    $uslugiParentId = 0;
    foreach ($items as $item) {
        if ((string) $item->title === 'Услуги' && (int) ($item->menu_item_parent ?? 0) === 0) {
            $uslugiParentId = (int) $item->ID;
            break;
        }
    }
    $uslugiChildren = [
        'Стаж до 2002' => home_url('/stazh-do-2002/'),
        'Чек-лист документов' => home_url('/chek-list-dokumentov/'),
    ];
    if ($uslugiParentId > 0) {
        foreach ($uslugiChildren as $title => $url) {
            if (isset($titles[$title])) {
                continue;
            }
            wp_update_nav_menu_item($menuId, 0, [
                'menu-item-title' => $title,
                'menu-item-url' => $url,
                'menu-item-status' => 'publish',
                'menu-item-type' => 'custom',
                'menu-item-parent-id' => $uslugiParentId,
            ]);
            echo "MENU {$title} under Услуги\n";
        }
    }

    // Порядок верхнего уровня: … Услуги → Отзывы → Статьи → …
    $items = wp_get_nav_menu_items($menuId) ?: [];
    $otzyvyId = 0;
    $statiOrder = null;
    foreach ($items as $item) {
        if ((int) ($item->menu_item_parent ?? 0) !== 0) {
            continue;
        }
        if ((string) $item->title === 'Отзывы') {
            $otzyvyId = (int) $item->ID;
        }
        if ((string) $item->title === 'Статьи') {
            $statiOrder = (int) $item->menu_order;
        }
    }
    if ($otzyvyId > 0 && $statiOrder !== null) {
        wp_update_post([
            'ID' => $otzyvyId,
            'menu_order' => max(0, $statiOrder - 1),
        ]);
        echo "MENU Отзывы order before Статьи\n";
    }

    $items = wp_get_nav_menu_items($menuId) ?: [];
    $partneramId = 0;
    $kontaktyOrder = null;
    foreach ($items as $item) {
        if ((int) ($item->menu_item_parent ?? 0) !== 0) {
            continue;
        }
        if ((string) $item->title === 'Партнёрам') {
            $partneramId = (int) $item->ID;
        }
        if ((string) $item->title === 'Контакты') {
            $kontaktyOrder = (int) $item->menu_order;
        }
    }
    if ($partneramId > 0 && $kontaktyOrder !== null) {
        require __DIR__ . '/wp_fix_partneram_menu_order.php';
    }
}

echo "OK trust pages seeded\n";
