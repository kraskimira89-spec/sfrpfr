<?php
/**
 * Plugin Name: SFRFR SEO Meta
 * Description: Единые description, canonical, Open Graph, JSON-LD и один H1 на публичной витрине.
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * Rank Math установлен, но frontend meta не является источником истины:
 * настройки live не версионируются. Sitemap плагина при этом не затрагивается.
 */
add_action('wp', static function (): void {
    remove_all_actions('rank_math/head');
}, 0);
remove_action('wp_head', 'rel_canonical');

/**
 * Favicon для Яндекса: SVG + PNG 120×120 (рекомендация Вебмастера).
 */
add_action('wp_head', static function (): void {
    if (is_admin()) {
        return;
    }
    printf(
        "<link rel=\"icon\" href=\"%s\" type=\"image/svg+xml\" />\n",
        esc_url(home_url('/favicon.svg'))
    );
    printf(
        "<link rel=\"icon\" href=\"%s\" type=\"image/png\" sizes=\"120x120\" />\n",
        esc_url(home_url('/favicon-120.png'))
    );
}, 1);

function sfrfr_seo_is_noindex(): bool
{
    // ТЗ-18: служебные результаты поиска не индексировать
    if (is_search()) {
        return true;
    }
    if (is_category(['situacii', 'analitika'])) {
        return true;
    }
    if (!is_singular('post')) {
        return false;
    }
    $postId = get_queried_object_id();
    if ((string) get_post_meta($postId, '_sfrfr_noindex', true) === '1') {
        return true;
    }
    return has_category(['situacii', 'analitika'], $postId);
}

function sfrfr_seo_title_has_site_suffix(string $title, string $site): bool
{
    if ($site === '') {
        return false;
    }

    return (bool) preg_match(
        '/(?:\||—|–|-)\s*' . preg_quote($site, '/') . '\s*$/u',
        $title
    );
}

add_action('send_headers', static function (): void {
    if (sfrfr_seo_is_noindex() && !headers_sent()) {
        header('X-Robots-Tag: noindex, follow', true);
    }
});

/**
 * Короткие document title для ключевых страниц (подготовка к быстрым ссылкам Яндекса).
 * Rank Math / тема могут задавать title через pre_get_document_title — тогда
 * document_title_parts не вызывается; читаем те же meta, что пишет сид.
 *
 * @param array<string, string> $parts
 * @return array<string, string>
 */
add_filter('document_title_parts', static function (array $parts): array {
    $map = [
        'tarify' => 'Тарифы',
        'kak-rabotaem' => 'Как это работает',
        'otzyvy' => 'Отзывы',
        'kontakty' => 'Контакты',
        'proverka-stazha' => 'Проверка стажа, а не калькулятор пенсии',
        'stazh-do-2002' => 'Как подтвердить стаж до 2002 года',
        'partneram' => 'Партнёрам — навигация по пенсионным документам | Проверка стажа',
        'chek-list-dokumentov' => 'Чек-лист документов для проверки стажа | Проверка стажа',
        'blog' => 'Статьи',
    ];
    if (is_front_page()) {
        $parts['title'] = 'Проверка стажа';
        unset($parts['tagline'], $parts['site']);
        return $parts;
    }
    if (is_home() && !is_front_page()) {
        $parts['title'] = 'Статьи';
    } elseif (is_singular()) {
        $postId = get_queried_object_id();
        $fromMeta = '';
        foreach (['_rank_math_title', '_yoast_wpseo_title', '_sfrfr_seo_title'] as $metaKey) {
            $saved = trim(wp_check_invalid_utf8((string) get_post_meta($postId, $metaKey, true), true));
            if ($saved !== '') {
                $fromMeta = $saved;
                break;
            }
        }
        if ($fromMeta !== '') {
            $parts['title'] = $fromMeta;
        } elseif (is_page()) {
            $slug = (string) get_post_field('post_name', $postId);
            if (isset($map[$slug])) {
                $parts['title'] = $map[$slug];
            }
        }
    }
    if (!empty($parts['title']) && !empty($parts['site']) && $parts['title'] === $parts['site']) {
        unset($parts['site']);
    } elseif (
        !empty($parts['title'])
        && !empty($parts['site'])
        && sfrfr_seo_title_has_site_suffix((string) $parts['title'], (string) $parts['site'])
    ) {
        unset($parts['site']);
    }
    return $parts;
}, 20);

add_filter('pre_get_document_title', static function ($title) {
    if (is_admin() || is_front_page() || !is_singular()) {
        return is_string($title) ? $title : '';
    }
    $postId = (int) get_queried_object_id();
    $fromMeta = '';
    foreach (['_rank_math_title', '_yoast_wpseo_title', '_sfrfr_seo_title'] as $metaKey) {
        $saved = trim(wp_check_invalid_utf8((string) get_post_meta($postId, $metaKey, true), true));
        if ($saved !== '') {
            $fromMeta = $saved;
            break;
        }
    }
    if ($fromMeta === '') {
        return is_string($title) ? $title : '';
    }
    // Не режем по str_contains(site): SEO-title услуги начинается с «Проверка стажа».
    $site = trim(wp_check_invalid_utf8((string) get_bloginfo('name', 'display'), true));
    if ($site !== '' && $fromMeta !== $site) {
        if (sfrfr_seo_title_has_site_suffix($fromMeta, $site)) {
            return $fromMeta;
        }
        return $fromMeta . ' — ' . $site;
    }
    return $fromMeta;
}, 9999);

/**
 * Единый URL главной: /glavnaya/ → /.
 */
add_action('template_redirect', static function (): void {
    if (is_admin() || wp_doing_ajax() || (defined('REST_REQUEST') && REST_REQUEST)) {
        return;
    }
    $path = (string) wp_parse_url((string) ($_SERVER['REQUEST_URI'] ?? ''), PHP_URL_PATH);
    $path = untrailingslashit($path);
    if ($path === '/glavnaya') {
        wp_safe_redirect(home_url('/'), 301);
        exit;
    }
}, 1);

/**
 * Не включать тонкие ситуации/аналитику в WordPress sitemap.
 *
 * @param array<string,mixed> $args
 * @return array<string,mixed>
 */
add_filter('wp_sitemaps_posts_query_args', static function (array $args, string $postType): array {
    if ($postType !== 'post') {
        return $args;
    }
    $args['meta_query'] = [
        'relation' => 'OR',
        [
            'key' => '_sfrfr_noindex',
            'compare' => 'NOT EXISTS',
        ],
        [
            'key' => '_sfrfr_noindex',
            'value' => '1',
            'compare' => '!=',
        ],
    ];
    $excludeCats = [];
    foreach (['situacii', 'analitika'] as $slug) {
        $term = get_term_by('slug', $slug, 'category');
        if ($term instanceof WP_Term) {
            $excludeCats[] = (int) $term->term_id;
        }
    }
    if ($excludeCats) {
        $args['category__not_in'] = array_values(array_unique(array_merge(
            array_map('intval', (array) ($args['category__not_in'] ?? [])),
            $excludeCats
        )));
    }
    return $args;
}, 10, 2);

/**
 * Не включать временные архивы тонких серий в taxonomy sitemap.
 *
 * @param array<string,mixed> $args
 * @return array<string,mixed>
 */
add_filter('wp_sitemaps_taxonomies_query_args', static function (array $args, string $taxonomy): array {
    if ($taxonomy !== 'category') {
        return $args;
    }
    $exclude = [];
    foreach (['situacii', 'analitika'] as $slug) {
        $term = get_term_by('slug', $slug, 'category');
        if ($term instanceof WP_Term) {
            $exclude[] = (int) $term->term_id;
        }
    }
    if ($exclude) {
        $args['exclude'] = array_values(array_unique(array_merge(
            array_map('intval', (array) ($args['exclude'] ?? [])),
            $exclude
        )));
    }
    return $args;
}, 10, 2);

function sfrfr_seo_limit(string $value, int $limit = 165): string
{
    $value = wp_check_invalid_utf8($value, true);
    $normalized = preg_replace('/\s+/', ' ', wp_strip_all_tags(strip_shortcodes($value)));
    $value = trim(is_string($normalized) ? $normalized : $value);
    if ($value === '') {
        return '';
    }
    // Считать лимит в символах UTF-8. Никогда не резать Cyrillic через substr() по байтам —
    // иначе esc_attr() на фронте отдаёт пустой content.
    if (function_exists('mb_strlen') && function_exists('mb_substr')) {
        if (mb_strlen($value, 'UTF-8') > $limit) {
            $cut = rtrim(mb_substr($value, 0, max(1, $limit - 1), 'UTF-8'));
            return wp_check_invalid_utf8($cut, true) . '…';
        }
        return $value;
    }
    if (strlen($value) > $limit) {
        $cut = substr($value, 0, max(1, $limit - 3));
        $cut = wp_check_invalid_utf8($cut, true);
        return rtrim($cut) . '...';
    }
    return $value;
}

function sfrfr_seo_description(): string
{
    if (is_front_page()) {
        return 'Проверка пенсионного стажа, выписки ИЛС и документов. Находим возможные расхождения и готовим понятный план обращения в СФР.';
    }
    if (is_home()) {
        return 'Практические статьи о проверке стажа, выписке ИЛС, архивных справках, документах и обращении в СФР.';
    }
    if (is_category()) {
        $term = get_queried_object();
        $name = $term instanceof WP_Term ? (string) $term->name : 'проверке стажа';
        $name = wp_check_invalid_utf8($name, true);
        if ($name === '') {
            $name = 'проверке стажа';
        }
        return sfrfr_seo_limit("Статьи по теме «{$name}»: инструкции, документы и частые ошибки при проверке пенсионного стажа и сведений ИЛС.");
    }
    if (is_singular()) {
        $postId = get_queried_object_id();
        foreach (['_sfrfr_seo_description', '_rank_math_description', '_yoast_wpseo_metadesc'] as $metaKey) {
            $saved = (string) get_post_meta($postId, $metaKey, true);
            $saved = trim(wp_check_invalid_utf8($saved, true));
            if ($saved !== '') {
                $limited = sfrfr_seo_limit($saved);
                if ($limited !== '') {
                    return $limited;
                }
            }
        }

        $slug = (string) get_post_field('post_name', $postId);
        $pageDescriptions = [
            'oferta' => 'Условия оказания услуг сервиса «Проверка стажа»: состав сопровождения, порядок оплаты, права и обязанности сторон.',
            'politika-pdn' => 'Политика обработки персональных данных сервиса «Проверка стажа»: цели, основания, сроки и права пользователя.',
            'soglasie' => 'Согласие на обработку персональных данных при обращении в сервис «Проверка стажа».',
            'cookies' => 'Правила использования файлов браузера и аналитики на сайте сервиса «Проверка стажа».',
            'proverka-stazha' => 'Нужен расчёт пенсии или калькулятор стажа? Сумму считает СФР. Мы сверяем ИЛС и документы и готовим план обращения — без обещания выплат.',
            'chek-list-dokumentov' => 'Скачайте бесплатную рабочую тетрадь: как собрать пенсионные документы, получить выписку ИЛС и отметить возможные расхождения.',
            'stazh-do-2002' => 'Страховой стаж до 2002: сверка ИЛС, трудовой и справок. Готовим чек-лист и план обращения — подаёте вы сами, решение принимает СФР. Это не калькулятор стажа.',
            'tarify' => 'Поэтапные тарифы проверки стажа: диагностика 3000 ₽, подготовка документов 5000 ₽, сопровождение до подачи 8000 ₽.',
            'kontakty' => 'Телефон, почта, MAX, реквизиты ООО «ПОД ПРИСМОТРОМ» и ссылки на оферту и политику ПДн.',
            'otzyvy' => 'Отзывы о сервисе «Проверка стажа»: форма на сайте после модерации и рейтинг на Яндекс Картах.',
            'kak-rabotaem' => 'Порядок работы сервиса «Проверка стажа»: заявка, документы, диагностика, план и самостоятельная подача в СФР.',
            'lopakova-nataliya' => 'Лопакова Наталия Федоровна: социальный предприниматель из Ноябрьска, руководитель сервиса «Проверка стажа», проекты «Под присмотром» и публикации в СМИ.',
            'bogdanovskiy-sergey' => 'Богдановский Сергей Викторович: эксперт по доступной среде и социальной мобильности из Ноябрьска, председатель «Таганая», проектный менеджер «Под присмотром».',
            'expert' => 'Профили экспертов сервиса «Проверка стажа»: руководитель и эксперт по доступной среде.',
            'kak-proverit-stazh-v-vypiske-ils' => 'Как узнать свой пенсионный стаж и проверить стаж в выписке ИЛС: сверка периодов без калькулятора выплат. Решение по учёту — у СФР.',
            'kak-sverit-trudovuyu-knizhku-i-ils' => 'Как проверить трудовой стаж: сверка трудовой книжки с ИЛС вместо калькулятора стажа онлайн. Без расчёта суммы пенсии.',
            'chto-delat-esli-period-raboty-ne-uchten' => 'Не учли стаж в ИЛС: что делать при не учтённом стаже — сверка, документы и обращение в СФР.',
            'arhivnaya-spravka-dlya-sfr-zachem-i-kuda' => 'Архивная справка о стаже: запрос в архив, ликвидация работодателя и что подготовить для СФР.',
            'tipichnye-situacii-proverki-stazha' => 'Типичные ситуации при проверке стажа: что сверять в документах и какой следующий шаг выбрать без обещания перерасчёта.',
            'kak-pomoch-rodstvenniku-proverit-stazh' => 'Как родственнику помочь проверить стаж: согласие, документы, каналы связи и границы участия без передачи сканов в открытый чат.',
            'chto-vy-poluchite-posle-proverki-stazha' => 'Что входит в результат проверки стажа: разбор документов, план действий и границы услуги сервиса «Проверка стажа».',
            'kak-rabotat-v-max-i-lichnom-kabinete' => 'Как связаны MAX и личный кабинет на сайте: что можно обсуждать в мессенджере и куда загружать документы.',
            'chastye-voprosy-o-proverke-stazha' => 'Чем пенсионный калькулятор СФР отличается от проверки стажа: частые вопросы о документах, ИЛС и границах сервиса.',
            'kakie-dokumenty-sobrat-do-obrashcheniya-v-sfr' => 'Какие документы собрать до обращения в СФР при проверке стажа: минимальный комплект и порядок подготовки.',
            'kak-podat-zayavlenie-cherez-gosuslugi-ili-mfc' => 'Как подготовиться к подаче заявления через Госуслуги или МФЦ: комплект, порядок и типичные ошибки.',
            'otkaz-sfr-chto-proverit-v-dokumentah' => 'Отказ СФР в назначении пенсии: что проверить в документах и как готовить следующий шаг. Решение снова принимает СФР.',
            'kak-zakazat-vypisku-ils' => 'Как заказать и получить выписку ИЛС (СЗИ-ИЛС) через Госуслуги или СФР. Дата формирования и сверка с трудовой.',
            'pensiya-po-invalidnosti-i-stazh-na-chto-smotret' => 'Пенсия по инвалидности и стаж: что сверять отдельно и как не смешивать разные основания выплат.',
            'chem-otlichaetsya-diagnostika-ot-soprovozhdeniya' => 'Чем диагностика стажа отличается от сопровождения обращения: состав работ, результат и ограничения.',
            'pochemu-reshenie-prinimaet-tolko-sfr' => 'Почему решение о перерасчёте принимает только СФР: роль сервиса, границы помощи и что клиент делает самостоятельно.',
            'chek-list-pered-zapisju-v-mfc' => 'Чек-лист перед записью в МФЦ по вопросам стажа и ИЛС: документы, копии и что уточнить заранее.',
            'proverka-severnogo-stazha' => 'Северный стаж для пенсии и пенсия крайний север: сверка в районах КС и приравненных. Решение принимает СФР.',
            'ne-uchli-stazh' => 'Не учтён стаж или стаж не учтён в ИЛС: сверка трудовой и выписки, чек-лист и план. Без обещания перерасчёта — решение принимает СФР.',
            'arhivnaya-spravka-stazh' => 'Архивная справка о стаже и запрос в архив: ликвидация работодателя, что подготовить для СФР. Без обещания перерасчёта.',
            'otkaz-sfr' => 'Отказ СФР в назначении пенсии: что проверить в документах и как готовить следующий шаг. Решение снова принимает СФР.',
            'severnyy-stazh-i-rayonnyy-koefficient' => 'Северный стаж для пенсии, районы Крайнего Севера и приравненные местности: что сверить в трудовой и ИЛС.',
            'edv-i-pensiya-chto-proveryat-otdelno' => 'ЕДВ и пенсия: что относится к стажу, а что проверять отдельно, чтобы не смешивать разные решения СФР.',
            'lgotnyy-i-pedagogicheskiy-stazh' => 'Льготный стаж: что проверить в документах, если льготный или вредный стаж не учли.',
            'rashozhdeniya-fio-i-zapisi-trudovoy' => 'Расхождения ФИО и ошибки в трудовой: как сверить записи и какие подтверждения обычно нужны до обращения в СФР.',
        ];
        if (isset($pageDescriptions[$slug])) {
            return $pageDescriptions[$slug];
        }

        $excerpt = trim(wp_check_invalid_utf8((string) get_post_field('post_excerpt', $postId), true));
        if ($excerpt === '') {
            $excerpt = trim(wp_check_invalid_utf8((string) get_post_field('post_content', $postId), true));
        }
        $limited = sfrfr_seo_limit($excerpt);
        if ($limited !== '') {
            return $limited;
        }
        $title = trim(wp_check_invalid_utf8((string) get_the_title($postId), true));
        if ($title !== '') {
            return sfrfr_seo_limit("{$title}: практическая инструкция сервиса «Проверка стажа» без обещания перерасчёта.");
        }
    }
    return 'Проверка пенсионного стажа и документов: понятные инструкции и сопровождение подготовки обращения в СФР.';
}

function sfrfr_seo_canonical_url(): string
{
    if (is_front_page()) {
        return home_url('/');
    }
    if (is_home()) {
        $pageId = (int) get_option('page_for_posts');
        return $pageId > 0 ? (string) get_permalink($pageId) : home_url('/blog/');
    }
    if (is_category()) {
        $url = get_term_link(get_queried_object());
        if (!is_wp_error($url)) {
            return (string) $url;
        }
    }
    if (is_singular()) {
        return (string) get_permalink();
    }
    return home_url((string) wp_parse_url((string) ($_SERVER['REQUEST_URI'] ?? '/'), PHP_URL_PATH));
}

function sfrfr_seo_social_image(): string
{
    $logoId = (int) get_theme_mod('custom_logo');
    if ($logoId > 0) {
        $url = wp_get_attachment_image_url($logoId, 'full');
        if (is_string($url)) {
            return $url;
        }
    }
    return (string) get_site_icon_url(512);
}

/**
 * FAQ главной (видимый блок #faq) → Schema.org FAQPage.
 * Текст должен совпадать с scripts/assets/sfrfr-home.html.
 *
 * @return list<array<string, mixed>>
 */
function sfrfr_seo_home_faq_entities(): array
{
    $pairs = [
        [
            'q' => 'Вы являетесь СФР?',
            'a' => 'Нет. Мы сервис сопровождения: готовим документы и план — подаёте через СФР или Госуслуги вы сами. Решение о пенсии и перерасчёте принимает только СФР.',
        ],
        [
            'q' => 'Гарантируете перерасчёт?',
            'a' => 'Нет. Мы не гарантируем перерасчёт и конкретную сумму выплат.',
        ],
        [
            'q' => 'Чем диагностика отличается от сопровождения?',
            'a' => 'Диагностика — разбор документов и план. Сопровождение — помощь на этапах подготовки и подачи при вашем обращении в СФР.',
        ],
        [
            'q' => 'Какие документы нужны и куда их отправлять?',
            'a' => 'Обычно выписка ИЛС из Госуслуг, трудовая и справки. Точный список подскажем после диалога в MAX. Не отправляйте сканы в чат или через форму сайта. После короткого диалога документы загружаются только в защищённом личном кабинете и только после согласия.',
        ],
        [
            'q' => 'Кто подаёт заявление?',
            'a' => 'Мы готовим документы, проект обращения и понятный план. Мы расскажем по шагам, но обращение через СФР, МФЦ или Госуслуги подаёте вы сами. Решение о пенсии и перерасчёте принимает только СФР.',
        ],
        [
            'q' => 'Можно ли обратиться родственнику?',
            'a' => 'Да, при согласии доверителя.',
        ],
        [
            'q' => 'Как задать свой вопрос?',
            'a' => 'Напишите в MAX или оставьте заявку ниже — без загрузки сканов через сайт.',
        ],
        [
            'q' => 'Где подробнее?',
            'a' => 'Расширенный FAQ, статьи блога, страница «Как это работает» и контакты сервиса.',
        ],
    ];

    $entities = [];
    foreach ($pairs as $pair) {
        $entities[] = [
            '@type' => 'Question',
            'name' => $pair['q'],
            'acceptedAnswer' => [
                '@type' => 'Answer',
                'text' => $pair['a'],
            ],
        ];
    }
    return $entities;
}

/**
 * Хлебные крошки: [['name'=>…,'url'=>…], …]. Минимум 2 пункта для схемы.
 *
 * @return list<array{name:string,url:string}>
 */
function sfrfr_seo_breadcrumb_trail(): array
{
    $home = home_url('/');
    $trail = [
        ['name' => 'Главная', 'url' => $home],
    ];

    if (is_front_page()) {
        return $trail;
    }

    if (is_home()) {
        $trail[] = ['name' => 'Статьи', 'url' => home_url('/blog/')];
        return $trail;
    }

    if (is_category()) {
        $trail[] = ['name' => 'Статьи', 'url' => home_url('/blog/')];
        $term = get_queried_object();
        if ($term instanceof WP_Term) {
            $trail[] = [
                'name' => (string) $term->name,
                'url' => (string) get_term_link($term),
            ];
        }
        return $trail;
    }

    if (is_singular('post')) {
        $trail[] = ['name' => 'Статьи', 'url' => home_url('/blog/')];
        $postId = get_queried_object_id();
        $cats = get_the_category($postId);
        if (is_array($cats) && $cats !== []) {
            $cat = $cats[0];
            if ($cat instanceof WP_Term && !in_array($cat->slug, ['situacii', 'analitika'], true)) {
                $link = get_term_link($cat);
                if (!is_wp_error($link)) {
                    $trail[] = [
                        'name' => (string) $cat->name,
                        'url' => (string) $link,
                    ];
                }
            }
        }
        $trail[] = [
            'name' => get_the_title($postId),
            'url' => get_permalink($postId) ?: sfrfr_seo_canonical_url(),
        ];
        return $trail;
    }

    if (is_page()) {
        $pageId = get_queried_object_id();
        $ancestors = array_reverse(get_post_ancestors($pageId));
        foreach ($ancestors as $ancestorId) {
            $trail[] = [
                'name' => get_the_title((int) $ancestorId),
                'url' => get_permalink((int) $ancestorId) ?: '',
            ];
        }
        $short = [
            'tarify' => 'Тарифы',
            'kak-rabotaem' => 'Как это работает',
            'otzyvy' => 'Отзывы',
            'kontakty' => 'Контакты',
            'proverka-stazha' => 'Проверка стажа',
            'chek-list-dokumentov' => 'Папка документов',
            'pechat' => 'Печать',
            'blog' => 'Статьи',
            'oferta' => 'Оферта',
            'politika-pdn' => 'Политика ПДн',
            'soglasie' => 'Согласие',
            'cookies' => 'Файлы браузера',
            'expert' => 'Эксперты',
            'lopakova-nataliya' => 'Лопакова Н. Ф.',
            'bogdanovskiy-sergey' => 'Богдановский С. В.',
        ];
        $slug = (string) get_post_field('post_name', $pageId);
        $name = $short[$slug] ?? get_the_title($pageId);
        $trail[] = [
            'name' => $name,
            'url' => get_permalink($pageId) ?: sfrfr_seo_canonical_url(),
        ];
        return $trail;
    }

    return $trail;
}

/**
 * @param list<array{name:string,url:string}> $trail
 * @return array<string, mixed>|null
 */
function sfrfr_seo_breadcrumb_schema(array $trail, string $canonical): ?array
{
    if (count($trail) < 2) {
        return null;
    }
    $elements = [];
    foreach ($trail as $i => $crumb) {
        $url = $crumb['url'] !== '' ? $crumb['url'] : $canonical;
        // Формат Google/Яндекс без предупреждений: item = {@id, name}.
        $elements[] = [
            '@type' => 'ListItem',
            'position' => $i + 1,
            'item' => [
                '@id' => $url,
                'name' => $crumb['name'],
            ],
        ];
    }
    return [
        '@type' => 'BreadcrumbList',
        '@id' => $canonical . '#breadcrumbs',
        'itemListElement' => $elements,
    ];
}

/**
 * Реальные офферы тарифов (без фейковых рейтингов).
 *
 * @return list<array<string, mixed>>
 */
function sfrfr_seo_tariff_offers(): array
{
    $tarify = home_url('/tarify/');
    return [
        [
            '@type' => 'Offer',
            'name' => 'Шаг 1. Диагностика проверки стажа',
            'price' => '3000',
            'priceCurrency' => 'RUB',
            'url' => $tarify,
            'availability' => 'https://schema.org/InStock',
        ],
        [
            '@type' => 'Offer',
            'name' => 'Шаг 2. Подготовка документов',
            'price' => '5000',
            'priceCurrency' => 'RUB',
            'url' => $tarify,
            'availability' => 'https://schema.org/InStock',
        ],
        [
            '@type' => 'Offer',
            'name' => 'Шаг 3. Сопровождение до подачи',
            'price' => '8000',
            'priceCurrency' => 'RUB',
            'url' => $tarify,
            'availability' => 'https://schema.org/InStock',
        ],
    ];
}

/**
 * Видимая навигационная цепочка (дублирует JSON-LD для робота и людей).
 */
function sfrfr_seo_render_breadcrumbs_html(): void
{
    if (is_admin() || is_front_page() || is_search()) {
        return;
    }
    if (!is_singular() && !is_home() && !is_category()) {
        return;
    }
    $trail = sfrfr_seo_breadcrumb_trail();
    if (count($trail) < 2) {
        return;
    }
    echo '<nav class="sfrfr-breadcrumbs" aria-label="Навигационная цепочка"><div class="sfrfr-wrap"><ol class="sfrfr-breadcrumbs__list">';
    $last = count($trail) - 1;
    foreach ($trail as $i => $crumb) {
        $name = esc_html($crumb['name']);
        echo '<li class="sfrfr-breadcrumbs__item">';
        if ($i < $last && $crumb['url'] !== '') {
            printf(
                '<a class="sfrfr-breadcrumbs__link" href="%s">%s</a>',
                esc_url($crumb['url']),
                $name
            );
        } else {
            echo '<span class="sfrfr-breadcrumbs__current" aria-current="page">' . $name . '</span>';
        }
        echo '</li>';
    }
    echo '</ol></div></nav>';
}

/**
 * @return array<int, array<string, mixed>>
 */
function sfrfr_seo_schema_graph(string $description, string $canonical): array
{
    $site = home_url('/');
    $orgId = $site . '#organization';
    $websiteId = $site . '#website';
    $logo = sfrfr_seo_social_image();
    $graph = [
        [
            // LocalBusiness: address/telephone/priceRange — поддерживается Яндекс.Справочником.
            '@type' => 'LocalBusiness',
            '@id' => $orgId,
            'name' => 'ООО «ПОД ПРИСМОТРОМ»',
            'alternateName' => 'Проверка стажа',
            'description' => 'Сервис проверки пенсионного стажа и документов. Подготовка плана обращения в СФР.',
            'url' => $site,
            'priceRange' => '₽3000–₽8000',
            'telephone' => '+7-909-195-04-08',
            'email' => 'info@proverkastaza.ru',
            'address' => [
                '@type' => 'PostalAddress',
                'streetAddress' => 'ул. Рабочая, д. 109Б, кв. 4',
                'addressLocality' => 'Ноябрьск',
                'addressRegion' => 'ЯНАО',
                'postalCode' => '629804',
                'addressCountry' => 'RU',
            ],
            'contactPoint' => [
                '@type' => 'ContactPoint',
                'telephone' => '+7-909-195-04-08',
                'email' => 'info@proverkastaza.ru',
                'contactType' => 'customer service',
                'availableLanguage' => ['Russian'],
            ],
        ],
        [
            '@type' => 'WebSite',
            '@id' => $websiteId,
            'url' => $site,
            'name' => 'Проверка стажа',
            'description' => 'Сервис проверки пенсионного стажа и документов: сверка ИЛС, план обращения в СФР.',
            'inLanguage' => 'ru-RU',
            'publisher' => ['@id' => $orgId],
        ],
    ];
    if ($logo !== '') {
        $graph[0]['logo'] = [
            '@type' => 'ImageObject',
            'url' => $logo,
        ];
        $graph[0]['image'] = $logo;
    }

    $personId = $site . 'expert/lopakova-nataliya/#person';
    $lopakovaPhoto = $site . 'wp-content/uploads/sfrfr/expert-lopakova.jpg';
    $bogdanPhoto = $site . 'wp-content/uploads/sfrfr/expert-bogdanovskiy.jpg';
    $graph[] = [
        '@type' => 'Person',
        '@id' => $personId,
        'name' => 'Лопакова Наталия Федоровна',
        'jobTitle' => 'Генеральный директор',
        'url' => $site . 'expert/lopakova-nataliya/',
        'image' => $lopakovaPhoto,
        'worksFor' => ['@id' => $orgId],
    ];

    $expertBogdanId = $site . 'expert/bogdanovskiy-sergey/#person';
    if (is_page('bogdanovskiy-sergey') || is_page('expert')) {
        $graph[] = [
            '@type' => 'Person',
            '@id' => $expertBogdanId,
            'name' => 'Богдановский Сергей Викторович',
            'jobTitle' => 'Эксперт по доступной среде',
            'url' => $site . 'expert/bogdanovskiy-sergey/',
            'image' => $bogdanPhoto,
            'worksFor' => ['@id' => $orgId],
        ];
    }

    $serviceBase = [
        '@type' => 'Service',
        'provider' => ['@id' => $orgId],
        'areaServed' => ['@type' => 'Country', 'name' => 'Россия'],
        'offers' => sfrfr_seo_tariff_offers(),
    ];

    if (is_front_page()) {
        $graph[] = array_merge($serviceBase, [
            '@id' => $site . '#service',
            'name' => 'Проверка пенсионного стажа и документов',
            'description' => $description,
            'url' => $canonical,
        ]);
        $faq = sfrfr_seo_home_faq_entities();
        if ($faq !== []) {
            $graph[] = [
                '@type' => 'FAQPage',
                '@id' => $site . '#faq',
                'url' => $canonical,
                'name' => 'Вопросы о проверке стажа',
                'description' => 'Ответы на частые вопросы о сервисе проверки пенсионного стажа и границах ответственности СФР.',
                'mainEntity' => $faq,
            ];
        }
    }

    if (is_page('proverka-stazha') || is_page('tarify')) {
        $serviceName = is_page('tarify')
            ? 'Тарифы на проверку пенсионного стажа'
            : 'Проверка пенсионного стажа и документов';
        $graph[] = array_merge($serviceBase, [
            '@id' => $canonical . '#service',
            'name' => $serviceName,
            'description' => $description,
            'url' => $canonical,
        ]);
    }

    if (is_page('lopakova-nataliya')) {
        $graph[] = [
            '@type' => 'ProfilePage',
            '@id' => $canonical . '#profile',
            'url' => $canonical,
            'mainEntity' => ['@id' => $personId],
        ];
    }

    if (is_page('bogdanovskiy-sergey')) {
        $graph[] = [
            '@type' => 'ProfilePage',
            '@id' => $canonical . '#profile',
            'url' => $canonical,
            'mainEntity' => ['@id' => $expertBogdanId],
        ];
    }

    if (is_singular('post')) {
        $postId = get_queried_object_id();
        $authorName = trim((string) get_post_meta($postId, '_sfrfr_author_name', true));
        $author = $authorName !== ''
            ? ['@id' => $personId]
            : ['@id' => $orgId];
        $article = [
            '@type' => 'Article',
            '@id' => $canonical . '#article',
            'mainEntityOfPage' => $canonical,
            'headline' => get_the_title($postId),
            'description' => $description,
            'datePublished' => get_the_date(DATE_W3C, $postId),
            'dateModified' => get_the_modified_date(DATE_W3C, $postId),
            'inLanguage' => 'ru-RU',
            'author' => $author,
            'publisher' => ['@id' => $orgId],
        ];
        if ($logo !== '') {
            $article['image'] = $logo;
        }
        $graph[] = $article;
    }

    $crumbs = sfrfr_seo_breadcrumb_schema(sfrfr_seo_breadcrumb_trail(), $canonical);
    if ($crumbs !== null) {
        $graph[] = $crumbs;
        $pageName = html_entity_decode(wp_get_document_title(), ENT_QUOTES | ENT_HTML5, 'UTF-8');
        $graph[] = [
            '@type' => 'WebPage',
            '@id' => $canonical . '#webpage',
            'url' => $canonical,
            'name' => $pageName,
            'description' => $description !== '' ? $description : $pageName,
            'isPartOf' => ['@id' => $websiteId],
            'about' => ['@id' => $orgId],
            'breadcrumb' => ['@id' => $canonical . '#breadcrumbs'],
            'inLanguage' => 'ru-RU',
            'primaryImageOfPage' => $logo !== '' ? ['@type' => 'ImageObject', 'url' => $logo] : null,
        ];
        // Убрать null-поля из WebPage.
        $graph[array_key_last($graph)] = array_filter(
            $graph[array_key_last($graph)],
            static fn ($v) => $v !== null
        );
    }

    return $graph;
}

add_action('wp_head', static function (): void {
    if (is_admin() || is_feed() || is_robots() || is_trackback()) {
        return;
    }
    if (!is_front_page() && !is_home() && !is_category() && !is_singular()) {
        return;
    }

    $description = sfrfr_seo_description();
    $canonical = sfrfr_seo_canonical_url();
    $title = wp_get_document_title();
    $image = sfrfr_seo_social_image();
    $type = is_singular('post') ? 'article' : 'website';

    echo "\n<!-- SFRFR SEO Meta -->\n";
    if (sfrfr_seo_is_noindex()) {
        echo "<meta name=\"robots\" content=\"noindex, follow\" />\n";
    }
    printf("<meta name=\"description\" content=\"%s\" />\n", esc_attr($description));
    printf("<link rel=\"canonical\" href=\"%s\" />\n", esc_url($canonical));
    printf("<meta property=\"og:locale\" content=\"ru_RU\" />\n");
    printf("<meta property=\"og:type\" content=\"%s\" />\n", esc_attr($type));
    printf("<meta property=\"og:site_name\" content=\"Проверка стажа\" />\n");
    printf("<meta property=\"og:title\" content=\"%s\" />\n", esc_attr($title));
    printf("<meta property=\"og:description\" content=\"%s\" />\n", esc_attr($description));
    printf("<meta property=\"og:url\" content=\"%s\" />\n", esc_url($canonical));
    if ($image !== '') {
        printf("<meta property=\"og:image\" content=\"%s\" />\n", esc_url($image));
        printf("<meta name=\"twitter:card\" content=\"summary_large_image\" />\n");
    } else {
        printf("<meta name=\"twitter:card\" content=\"summary\" />\n");
    }
    if (is_singular('post')) {
        printf("<meta property=\"article:published_time\" content=\"%s\" />\n", esc_attr(get_the_date(DATE_W3C)));
        printf("<meta property=\"article:modified_time\" content=\"%s\" />\n", esc_attr(get_the_modified_date(DATE_W3C)));
    }

    $schema = [
        '@context' => 'https://schema.org',
        '@graph' => sfrfr_seo_schema_graph($description, $canonical),
    ];
    echo '<script type="application/ld+json">'
        . wp_json_encode($schema, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES)
        . "</script>\n";
}, 2);

/**
 * Видимые хлебные крошки под шапкой (навигационная цепочка для Яндекса).
 */
$sfrfrPrintCrumbs = static function (): void {
    if (!empty($GLOBALS['sfrfr_breadcrumbs_printed'])) {
        return;
    }
    $GLOBALS['sfrfr_breadcrumbs_printed'] = true;
    sfrfr_seo_render_breadcrumbs_html();
};
add_action('astra_content_before', $sfrfrPrintCrumbs, 5);
add_action('astra_content_top', $sfrfrPrintCrumbs, 5);
add_action('astra_header_after', $sfrfrPrintCrumbs, 20);

/**
 * Astra уже выводит post_title как H1. Убираем только первый H1 из тела записи,
 * оставляя исходные HTML-ассеты пригодными для чтения и повторного сида.
 * Добавляем byline автора/проверяющего на экспертных статьях.
 */
add_filter('the_content', static function (string $content): string {
    if ((!is_singular('post') && !is_page()) || !in_the_loop() || !is_main_query()) {
        return $content;
    }
    // Astra уже выводит title как H1 — убираем дубль из тела.
    $updated = preg_replace('/^\s*(?:<!--.*?-->\s*)*<h1\b[^>]*>.*?<\/h1>\s*/isu', '', $content, 1);
    $content = is_string($updated) ? $updated : $content;

    if (!is_singular('post')) {
        return $content;
    }

    $postId = get_the_ID();
    if (!$postId || has_category(['situacii', 'analitika'], $postId)) {
        return $content;
    }
    if (str_contains($content, 'sfrfr-article-byline')) {
        return $content;
    }
    $author = trim((string) get_post_meta($postId, '_sfrfr_author_name', true));
    $authorUrl = trim((string) get_post_meta($postId, '_sfrfr_author_url', true));
    $reviewer = trim((string) get_post_meta($postId, '_sfrfr_reviewer_name', true));
    $reviewerUrl = trim((string) get_post_meta($postId, '_sfrfr_reviewer_url', true));
    if ($author === '' && $reviewer === '') {
        return $content;
    }
    $authorHtml = $author !== ''
        ? (
            $authorUrl !== ''
                ? '<a href="' . esc_url($authorUrl) . '">' . esc_html($author) . '</a>'
                : esc_html($author)
        )
        : '';
    $parts = [];
    if ($authorHtml !== '') {
        $parts[] = 'Автор: ' . $authorHtml;
        if ($authorUrl !== '') {
            $parts[] = '<a class="sfrfr-article-byline__about" href="' . esc_url($authorUrl) . '">Об авторе</a>';
        }
    }
    if ($reviewer !== '') {
        $parts[] = 'Проверка: ' . (
            $reviewerUrl !== ''
                ? '<a href="' . esc_url($reviewerUrl) . '">' . esc_html($reviewer) . '</a>'
                : esc_html($reviewer)
        );
    }
    $modifiedTs = (int) get_post_modified_time('U', true, $postId);
    if ($modifiedTs > 0) {
        $months = [
            1 => 'января', 2 => 'февраля', 3 => 'марта', 4 => 'апреля',
            5 => 'мая', 6 => 'июня', 7 => 'июля', 8 => 'августа',
            9 => 'сентября', 10 => 'октября', 11 => 'ноября', 12 => 'декабря',
        ];
        $d = (int) wp_date('j', $modifiedTs);
        $m = (int) wp_date('n', $modifiedTs);
        $y = (int) wp_date('Y', $modifiedTs);
        $parts[] = 'Обновлено: ' . $d . ' ' . ($months[$m] ?? '') . ' ' . $y;
    }
    $byline = '<p class="sfrfr-article-byline"><em>' . implode(' · ', $parts) . '</em></p>';
    return $byline . $content;
}, 5);
