<?php
/**
 * ТЗ-11: рубрики, страница /blog/, 4 статьи P0, permalink, SEO meta.
 * Запуск: wp --path=SITE eval-file scripts/wp_seed_blog_tz11.php
 */

if (!defined('ABSPATH')) {
    fwrite(STDERR, "Run via WP-CLI eval-file\n");
    exit(1);
}

$assets = getenv('SFRFR_BLOG_ASSETS') ?: (__DIR__ . '/assets/blog');
$homeUrl = home_url('/');

$disclaimer = '<p class="sfrfr-article-disclaimer"><em>Не являемся СФР. Решение о перерасчёте принимает СФР. Материал носит справочный характер.</em></p>';

$ctaBlock = <<<HTML
<div class="sfrfr-article-cta">
  <p><strong>Готовы проверить своё дело?</strong></p>
  <p><a class="sfrfr-btn sfrfr-btn--primary" href="{$homeUrl}#kak-rabotat">Начать проверку</a>
  <a class="sfrfr-btn sfrfr-btn--ghost" href="{$homeUrl}#tarify">Услуги и тарифы</a>
  <a class="sfrfr-btn sfrfr-btn--ghost" href="{$homeUrl}#faq">Читать FAQ</a></p>
</div>
HTML;

$categories = [
    'ils' => 'ИЛС',
    'stazh' => 'Стаж',
    'dokumenty' => 'Документы',
    'podacha' => 'Подача',
    'dlya-rodstvennikov' => 'Для родственников',
    'usluga' => 'Услуга',
];

$catIds = [];
foreach ($categories as $slug => $name) {
    $term = get_term_by('slug', $slug, 'category');
    if ($term && !is_wp_error($term)) {
        $catIds[$slug] = (int) $term->term_id;
        continue;
    }
    $created = wp_insert_term($name, 'category', [
        'slug' => $slug,
        'description' => $name,
    ]);
    if (is_wp_error($created)) {
        // возможно конфликт с Uncategorized rename
        $term = get_term_by('name', $name, 'category');
        if ($term) {
            $catIds[$slug] = (int) $term->term_id;
            wp_update_term($term->term_id, 'category', ['slug' => $slug]);
        }
        continue;
    }
    $catIds[$slug] = (int) $created['term_id'];
}

function sfrfr_blog_load_body(string $assets, string $file): string
{
    $path = rtrim($assets, '/\\') . DIRECTORY_SEPARATOR . $file;
    if (!is_readable($path)) {
        throw new RuntimeException("Missing article file: {$path}");
    }
    return (string) file_get_contents($path);
}

function sfrfr_blog_upsert_post(array $args): int
{
    $existing = get_posts([
        'name' => $args['slug'],
        'post_type' => 'post',
        'post_status' => ['publish', 'draft', 'pending'],
        'numberposts' => 1,
        'fields' => 'ids',
    ]);
    $postarr = [
        'post_title' => $args['title'],
        'post_name' => $args['slug'],
        'post_status' => 'publish',
        'post_type' => 'post',
        'post_content' => $args['content'],
        'post_excerpt' => $args['excerpt'],
        'post_author' => 1,
    ];
    if ($existing) {
        $postarr['ID'] = (int) $existing[0];
        $id = wp_update_post($postarr, true);
    } else {
        $id = wp_insert_post($postarr, true);
    }
    if (is_wp_error($id)) {
        throw new RuntimeException($id->get_error_message());
    }
    $id = (int) $id;
    wp_set_post_categories($id, [$args['category_id']]);
    update_post_meta($id, '_rank_math_title', $args['seo_title']);
    update_post_meta($id, '_rank_math_description', $args['seo_description']);
    update_post_meta($id, '_yoast_wpseo_title', $args['seo_title']);
    update_post_meta($id, '_yoast_wpseo_metadesc', $args['seo_description']);
    return $id;
}

$articles = [
    [
        'file' => '01-ils-stazh.html',
        'slug' => 'kak-proverit-stazh-v-vypiske-ils',
        'title' => 'Как проверить стаж в выписке ИЛС',
        'category' => 'ils',
        'excerpt' => 'Коротко: что смотреть в выписке индивидуального лицевого счёта и какие периоды часто «теряются».',
        'seo_title' => 'Как проверить стаж в выписке ИЛС — справочник',
        'seo_description' => 'Пошагово: как читать выписку ИЛС, сверить периоды работы и понять, чего не хватает в учёте стажа.',
    ],
    [
        'file' => '02-trudovaya-ils.html',
        'slug' => 'kak-sverit-trudovuyu-knizhku-i-ils',
        'title' => 'Как сверить трудовую книжку и ИЛС',
        'category' => 'stazh',
        'excerpt' => 'Таблица сверки: запись в трудовой ↔ строка в ИЛС. Что делать при расхождении.',
        'seo_title' => 'Сверка трудовой книжки и ИЛС — по шагам',
        'seo_description' => 'Как сравнить трудовую книжку с выпиской ИЛС и что подготовить, если период не совпадает.',
    ],
    [
        'file' => '03-period-ne-uchten.html',
        'slug' => 'chto-delat-esli-period-raboty-ne-uchten',
        'title' => 'Что делать, если период работы не учтён',
        'category' => 'stazh',
        'excerpt' => 'План действий, если в ИЛС нет периода из трудовой: справки, архив, обращение в СФР.',
        'seo_title' => 'Период работы не учтён в ИЛС — что делать',
        'seo_description' => 'Если в выписке ИЛС нет периода работы: какие документы собрать и куда обращаться.',
    ],
    [
        'file' => '04-arhivnaya-spravka.html',
        'slug' => 'arhivnaya-spravka-dlya-sfr-zachem-i-kuda',
        'title' => 'Архивная справка для СФР: зачем и куда',
        'category' => 'dokumenty',
        'excerpt' => 'Зачем нужна архивная справка, куда за ней идти и как она помогает подтвердить стаж.',
        'seo_title' => 'Архивная справка для СФР: зачем нужна и куда обращаться',
        'seo_description' => 'Когда запрашивать архивную справку для подтверждения стажа и как подготовить обращение.',
    ],
    [
        'file' => '05-tipichnye-situacii.html',
        'slug' => 'tipichnye-situacii-proverki-stazha',
        'title' => 'Типичные ситуации, когда стоит проверить пенсионное дело',
        'category' => 'usluga',
        'excerpt' => 'Сомнения в стаже, архивы, отказ СФР и другие типичные поводы для сверки документов.',
        'seo_title' => 'Типичные ситуации проверки пенсионного стажа',
        'seo_description' => 'Когда стоит сверить ИЛС и трудовую: пробелы в стаже, архивы, отказ и помощь родственникам.',
    ],
    [
        'file' => '06-dlya-rodstvennikov.html',
        'slug' => 'kak-pomoch-rodstvenniku-proverit-stazh',
        'title' => 'Как помочь родственнику проверить пенсионный стаж',
        'category' => 'dlya-rodstvennikov',
        'excerpt' => 'Как детям и родственникам собрать документы и сопровождать дело при согласии пенсионера.',
        'seo_title' => 'Помочь родственнику проверить стаж — по шагам',
        'seo_description' => 'Заявка, список документов и план действий для родственников пенсионера.',
    ],
    [
        'file' => '07-chto-vy-poluchite.html',
        'slug' => 'chto-vy-poluchite-posle-proverki-stazha',
        'title' => 'Что вы получите после проверки пенсионного дела',
        'category' => 'usluga',
        'excerpt' => 'Отчёт, чек-лист, черновики и инструкция подачи — без гарантии перерасчёта.',
        'seo_title' => 'Что входит в проверку пенсионного дела',
        'seo_description' => 'Какие материалы получает клиент после диагностики и сопровождения пенсионного дела.',
    ],
    [
        'file' => '08-max-i-kabinet.html',
        'slug' => 'kak-rabotat-v-max-i-lichnom-kabinete',
        'title' => 'Как работать в MAX и личном кабинете',
        'category' => 'usluga',
        'excerpt' => 'MAX — основной канал; кабинет — тот же аккаунт. Документы не загружают через сайт.',
        'seo_title' => 'MAX и личный кабинет — как работать',
        'seo_description' => 'Как пользоваться MAX и веб-кабинетом для проверки стажа без загрузки файлов на сайт.',
    ],
    [
        'file' => '09-faq-rasshirennyy.html',
        'slug' => 'chastye-voprosy-o-proverke-stazha',
        'title' => 'Частые вопросы о проверке стажа — расширенный разбор',
        'category' => 'usluga',
        'excerpt' => 'Документы, оплата, родственники, статус дела и границы обещаний — подробно.',
        'seo_title' => 'FAQ: проверка пенсионного стажа',
        'seo_description' => 'Ответы на частые вопросы о проверке стажа, документах, MAX и оплате за результат.',
    ],
];

$relatedFooter = function (string $currentSlug) use ($articles, $homeUrl): string {
    $links = [];
    foreach ($articles as $a) {
        if ($a['slug'] === $currentSlug) {
            continue;
        }
        $links[] = sprintf(
            '<li><a href="%s">%s</a></li>',
            esc_url(home_url('/blog/' . $a['slug'] . '/')),
            esc_html($a['title'])
        );
    }
    $list = implode("\n", $links);
    return <<<HTML
<h2>Связанные статьи</h2>
<ul>
{$list}
</ul>
<p><a href="{$homeUrl}#faq">Частые вопросы на главной</a> · <a href="{$homeUrl}blog/">Все статьи</a></p>
HTML;
};

$created = [];
foreach ($articles as $a) {
    $body = sfrfr_blog_load_body($assets, $a['file']);
    $content = $body . "\n" . $ctaBlock . "\n" . $relatedFooter($a['slug']) . "\n" . $disclaimer;
    $catId = $catIds[$a['category']] ?? 0;
    if (!$catId) {
        throw new RuntimeException('Category missing: ' . $a['category']);
    }
    $id = sfrfr_blog_upsert_post([
        'slug' => $a['slug'],
        'title' => $a['title'],
        'content' => $content,
        'excerpt' => $a['excerpt'],
        'category_id' => $catId,
        'seo_title' => $a['seo_title'],
        'seo_description' => $a['seo_description'],
    ]);
    $created[$a['slug']] = $id;
    echo "POST {$a['slug']}={$id}\n";
}

// Страница записей /blog/
$blogPage = get_page_by_path('blog');
if (!$blogPage) {
    $blogId = wp_insert_post([
        'post_title' => 'Статьи',
        'post_name' => 'blog',
        'post_status' => 'publish',
        'post_type' => 'page',
        'post_content' => '<p>Справочник по проверке стажа: выписка ИЛС, трудовая книжка, документы и подача в СФР.</p>',
    ], true);
    if (is_wp_error($blogId)) {
        throw new RuntimeException($blogId->get_error_message());
    }
    $blogId = (int) $blogId;
} else {
    $blogId = (int) $blogPage->ID;
    wp_update_post([
        'ID' => $blogId,
        'post_title' => 'Статьи',
        'post_status' => 'publish',
    ]);
}
echo "BLOG_PAGE={$blogId}\n";

$frontId = (int) get_option('page_on_front');
update_option('show_on_front', 'page');
if ($frontId > 0) {
    update_option('page_on_front', $frontId);
}
update_option('page_for_posts', $blogId);
// Не ставить category_base=blog: конфликт с /blog/%postname%/ → 404 у статей.
// Рубрики: /blog/rubrika/{slug}/ ; статьи: /blog/{slug}/ ; архив: /blog/
update_option('category_base', 'blog/rubrika');
update_option('posts_per_page', 9);

// Permalink /blog/%postname%/
update_option('permalink_structure', '/blog/%postname%/');
flush_rewrite_rules(false);

// Меню: пункт «Статьи»
$menus = wp_get_nav_menus();
foreach ($menus as $menu) {
    if ($menu->name !== 'SFRFR Primary' && $menu->name !== 'SFRFR Footer') {
        continue;
    }
    $items = wp_get_nav_menu_items($menu->term_id, ['post_status' => 'any']) ?: [];
    $hasBlog = false;
    foreach ($items as $item) {
        if (($item->url && strpos($item->url, '/blog') !== false) || $item->title === 'Статьи') {
            $hasBlog = true;
            break;
        }
    }
    if ($hasBlog) {
        continue;
    }
    wp_update_nav_menu_item($menu->term_id, 0, [
        'menu-item-title' => 'Статьи',
        'menu-item-object' => 'page',
        'menu-item-object-id' => $blogId,
        'menu-item-type' => 'post_type',
        'menu-item-status' => 'publish',
    ]);
    echo "MENU_ITEM blog -> {$menu->name}\n";
}

echo "OK TZ11 blog seeded\n";
