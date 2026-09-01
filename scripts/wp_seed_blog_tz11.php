<?php
/**
 * ТЗ-11: рубрики, /blog/, статьи P0 + доп., permalink, SEO, без комментариев.
 * Запуск: wp --path=SITE eval-file scripts/wp_seed_blog_tz11.php
 */

if (!defined('ABSPATH')) {
    fwrite(STDERR, "Run via WP-CLI eval-file\n");
    exit(1);
}

$assets = getenv('SFRFR_BLOG_ASSETS') ?: (__DIR__ . '/assets/blog');
$homeUrl = home_url('/');

$disclaimer = '<p class="sfrfr-article-disclaimer"><em>Не являемся СФР. Решение о перерасчёте принимает СФР. Материал носит справочный характер.</em></p>';

// CTA mid/end добавляет MU sfrfr-blog-ui (+ blog-ui.js). В контент сидера не дублируем.

// Миграция старого slug рубрики до создания категорий.
$oldRelatives = get_term_by('slug', 'dlya-rodstvennikov', 'category');
if ($oldRelatives && !is_wp_error($oldRelatives)) {
    $target = get_term_by('slug', 'rodstvenniki', 'category');
    if ($target && !is_wp_error($target) && (int) $target->term_id !== (int) $oldRelatives->term_id) {
        $posts = get_posts([
            'post_type' => 'post',
            'post_status' => 'any',
            'numberposts' => -1,
            'fields' => 'ids',
            'category' => (int) $oldRelatives->term_id,
        ]);
        foreach ($posts as $pid) {
            wp_set_post_categories((int) $pid, [(int) $target->term_id], true);
            wp_remove_object_terms((int) $pid, [(int) $oldRelatives->term_id], 'category');
        }
        wp_delete_term((int) $oldRelatives->term_id, 'category');
        echo "MIGRATE category dlya-rodstvennikov -> rodstvenniki (merged)\n";
    } else {
        $renamed = wp_update_term((int) $oldRelatives->term_id, 'category', [
            'slug' => 'rodstvenniki',
            'name' => 'Для родственников',
        ]);
        if (is_wp_error($renamed)) {
            throw new RuntimeException($renamed->get_error_message());
        }
        echo "MIGRATE category dlya-rodstvennikov -> rodstvenniki\n";
    }
}

$categories = [
    'ils' => 'ИЛС',
    'stazh' => 'Стаж',
    'dokumenty' => 'Документы',
    'podacha' => 'Подача',
    'rodstvenniki' => 'Для родственников',
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
        'comment_status' => 'closed',
        'ping_status' => 'closed',
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
    update_post_meta($id, '_sfrfr_seo_title', $args['seo_title']);
    update_post_meta($id, '_sfrfr_seo_description', $args['seo_description']);
    delete_post_meta($id, '_sfrfr_noindex');
    return $id;
}

$articles = [
    [
        'file' => '01-ils-stazh.html',
        'slug' => 'kak-proverit-stazh-v-vypiske-ils',
        'title' => 'Как проверить стаж в выписке ИЛС',
        'category' => 'ils',
        'excerpt' => 'Как узнать пенсионный стаж и проверить стаж в выписке ИЛС: периоды, расхождения, план без калькулятора выплат.',
        'seo_title' => 'Как проверить стаж в выписке ИЛС',
        'seo_description' => 'Как узнать свой пенсионный стаж и проверить стаж в выписке ИЛС: сверка периодов без калькулятора выплат. Решение по учёту — у СФР.',
        'related' => [
            'kak-zakazat-vypisku-ils',
            'kak-sverit-trudovuyu-knizhku-i-ils',
            'chto-delat-esli-period-raboty-ne-uchten',
        ],
    ],
    [
        'file' => '21-zakazat-vypisku-ils.html',
        'slug' => 'kak-zakazat-vypisku-ils',
        'title' => 'Как заказать и получить выписку ИЛС (СЗИ-ИЛС)',
        'category' => 'ils',
        'excerpt' => 'Как заказать и получить выписку ИЛС (СЗИ-ИЛС) через Госуслуги: дата формирования и следующий шаг сверки.',
        'seo_title' => 'Как заказать и получить выписку ИЛС (СЗИ-ИЛС)',
        'seo_description' => 'Как заказать и получить выписку ИЛС (СЗИ-ИЛС) через Госуслуги или СФР. Дата формирования и сверка с трудовой.',
        'related' => [
            'kak-proverit-stazh-v-vypiske-ils',
            'kak-sverit-trudovuyu-knizhku-i-ils',
            'kakie-dokumenty-sobrat-do-obrashcheniya-v-sfr',
        ],
    ],
    [
        'file' => '02-trudovaya-ils.html',
        'slug' => 'kak-sverit-trudovuyu-knizhku-i-ils',
        'title' => 'Как сверить трудовую книжку и ИЛС',
        'category' => 'stazh',
        'excerpt' => 'Проверить трудовой стаж: таблица сверки трудовая ↔ ИЛС. Почему калькулятор стажа онлайн не заменяет документы.',
        'seo_title' => 'Как сверить трудовую книжку и ИЛС',
        'seo_description' => 'Как проверить трудовой стаж: сверка трудовой книжки с ИЛС вместо калькулятора стажа онлайн. Без расчёта суммы пенсии.',
        'related' => [
            'kak-zakazat-vypisku-ils',
            'kak-proverit-stazh-v-vypiske-ils',
            'chto-delat-esli-period-raboty-ne-uchten',
        ],
    ],
    [
        'file' => '03-period-ne-uchten.html',
        'slug' => 'chto-delat-esli-period-raboty-ne-uchten',
        'title' => 'Не учли стаж в ИЛС: что делать',
        'category' => 'stazh',
        'excerpt' => 'Если не учтён стаж или стаж не учтён в ИЛС: сверка, документы, архив и обращение в СФР.',
        'seo_title' => 'Не учли стаж в ИЛС: что делать',
        'seo_description' => 'Не учтён стаж, не засчитали стаж или стаж не учтён в ИЛС: план сверки, документы и обращение в СФР. Без обещания перерасчёта.',
        'related' => [
            'arhivnaya-spravka-dlya-sfr-zachem-i-kuda',
            'kakie-dokumenty-sobrat-do-obrashcheniya-v-sfr',
            'kak-sverit-trudovuyu-knizhku-i-ils',
        ],
    ],
    [
        'file' => '04-arhivnaya-spravka.html',
        'slug' => 'arhivnaya-spravka-dlya-sfr-zachem-i-kuda',
        'title' => 'Архивная справка о стаже: зачем и куда',
        'category' => 'dokumenty',
        'excerpt' => 'Архивная справка о стаже и запрос в архив: когда нужна, куда обращаться, что указать в запросе.',
        'seo_title' => 'Архивная справка о стаже: зачем и куда',
        'seo_description' => 'Архивная справка о стаже (трудовом стаже): запрос в архив, ликвидация работодателя, что подготовить для СФР. Без обещания перерасчёта.',
        'related' => [
            'chto-delat-esli-period-raboty-ne-uchten',
            'kakie-dokumenty-sobrat-do-obrashcheniya-v-sfr',
            'chek-list-pered-zapisju-v-mfc',
        ],
    ],
    [
        'file' => '10-dokumenty-do-sfr.html',
        'slug' => 'kakie-dokumenty-sobrat-do-obrashcheniya-v-sfr',
        'title' => 'Какие документы собрать до обращения в СФР',
        'category' => 'dokumenty',
        'excerpt' => 'Список документов до обращения в СФР: ИЛС, трудовая, справки и что подготовить заранее.',
        'seo_title' => 'Какие документы собрать до обращения в СФР',
        'seo_description' => 'Чек-лист документов перед обращением в СФР: выписка ИЛС, трудовая, архивные справки.',
        'related' => [
            'arhivnaya-spravka-dlya-sfr-zachem-i-kuda',
            'kak-podat-zayavlenie-cherez-gosuslugi-ili-mfc',
            'chek-list-pered-zapisju-v-mfc',
        ],
    ],
    [
        'file' => '11-podacha-gosuslugi-mfc.html',
        'slug' => 'kak-podat-zayavlenie-cherez-gosuslugi-ili-mfc',
        'title' => 'Как подать заявление: Госуслуги, сайт СФР и МФЦ',
        'category' => 'podacha',
        'excerpt' => 'Электронная услуга, приёмная и клиентская служба СФР: как выбрать способ подачи; МФЦ — запасной канал.',
        'seo_title' => 'Как подать заявление в СФР: Госуслуги и сайт СФР',
        'seo_description' => 'Как выбрать способ подачи в СФР: электронная услуга, интернет-обращение или клиентская служба. Госуслуги — основной дистанционный маршрут, МФЦ — запасной канал.',
        'related' => [
            'kakie-dokumenty-sobrat-do-obrashcheniya-v-sfr',
            'chek-list-pered-zapisju-v-mfc',
            'otkaz-sfr-chto-proverit-v-dokumentah',
        ],
    ],
    [
        'file' => '12-otkaz-sfr.html',
        'slug' => 'otkaz-sfr-chto-proverit-v-dokumentah',
        'title' => 'Не учли стаж: что проверить после отказа СФР',
        'category' => 'podacha',
        'excerpt' => 'Что сохранить после отказа СФР, как найти спорный период и собрать недостающие подтверждения без повторной подачи того же пакета.',
        'seo_title' => 'Не учли стаж: что проверить после отказа СФР',
        'seo_description' => 'Не учли стаж или получили отказ СФР: как сохранить решение, определить причину и собрать документы для следующего обращения.',
        'related' => [
            'kakie-dokumenty-sobrat-do-obrashcheniya-v-sfr',
            'chto-delat-esli-period-raboty-ne-uchten',
            'pochemu-reshenie-prinimaet-tolko-sfr',
        ],
    ],
    [
        'file' => '13-invalidnost-i-stazh.html',
        'slug' => 'pensiya-po-invalidnosti-i-stazh-na-chto-smotret',
        'title' => 'Пенсия по инвалидности и стаж: на что смотреть',
        'category' => 'stazh',
        'excerpt' => 'Что сверять при пенсии по инвалидности: учёт трудового стажа и границы нашей услуги.',
        'seo_title' => 'Пенсия по инвалидности и стаж — на что смотреть',
        'seo_description' => 'Как отделить вопросы выплат по инвалидности от учёта трудового стажа в ИЛС.',
        'related' => [
            'kak-proverit-stazh-v-vypiske-ils',
            'kak-sverit-trudovuyu-knizhku-i-ils',
            'tipichnye-situacii-proverki-stazha',
        ],
    ],
    [
        'file' => '06-dlya-rodstvennikov.html',
        'slug' => 'kak-pomoch-rodstvenniku-proverit-stazh',
        'title' => 'Как помочь родственнику проверить пенсионный стаж',
        'category' => 'rodstvenniki',
        'excerpt' => 'Как детям и родственникам собрать документы и сопровождать дело при согласии пенсионера.',
        'seo_title' => 'Помочь родственнику проверить стаж — по шагам',
        'seo_description' => 'Заявка, список документов и план действий для родственников пенсионера.',
        'related' => [
            'kakie-dokumenty-sobrat-do-obrashcheniya-v-sfr',
            'kak-rabotat-v-max-i-lichnom-kabinete',
            'chto-vy-poluchite-posle-proverki-stazha',
        ],
    ],
    [
        'file' => '14-diagnostika-vs-soprovozhdenie.html',
        'slug' => 'chem-otlichaetsya-diagnostika-ot-soprovozhdeniya',
        'title' => 'Чем отличается диагностика от сопровождения',
        'category' => 'usluga',
        'excerpt' => 'Диагностика даёт план; сопровождение помогает довести подготовку документов до подачи.',
        'seo_title' => 'Диагностика и сопровождение — в чём разница',
        'seo_description' => 'Чем диагностика пенсионного дела отличается от сопровождения и какой формат выбрать.',
        'related' => [
            'chto-vy-poluchite-posle-proverki-stazha',
            'pochemu-reshenie-prinimaet-tolko-sfr',
            'tipichnye-situacii-proverki-stazha',
        ],
    ],
    [
        'file' => '15-pochemu-reshenie-sfr.html',
        'slug' => 'pochemu-reshenie-prinimaet-tolko-sfr',
        'title' => 'Почему решение принимает только СФР',
        'category' => 'usluga',
        'excerpt' => 'Почему сервис не заменяет СФР и не обещает перерасчёт: границы роли и ответственности.',
        'seo_title' => 'Почему решение о перерасчёте принимает только СФР',
        'seo_description' => 'Кто принимает решение о перерасчёте пенсии и чем занимается сервис сопровождения.',
        'related' => [
            'chem-otlichaetsya-diagnostika-ot-soprovozhdeniya',
            'chastye-voprosy-o-proverke-stazha',
            'otkaz-sfr-chto-proverit-v-dokumentah',
        ],
    ],
    [
        'file' => '16-chek-list-mfc.html',
        'slug' => 'chek-list-pered-zapisju-v-mfc',
        'title' => 'Чек-лист перед записью в МФЦ',
        'category' => 'podacha',
        'excerpt' => 'Что проверить на Госуслугах и в СФР до визита; МФЦ — запасной канал по вопросам стажа и документов.',
        'seo_title' => 'МФЦ как запасной канал: чек-лист по стажу',
        'seo_description' => 'Как проверить способ подачи на Госуслугах и в СФР, а затем подготовиться к обращению в МФЦ по вопросу стажа.',
        'related' => [
            'kak-podat-zayavlenie-cherez-gosuslugi-ili-mfc',
            'kakie-dokumenty-sobrat-do-obrashcheniya-v-sfr',
            'arhivnaya-spravka-dlya-sfr-zachem-i-kuda',
        ],
    ],
    [
        'file' => '05-tipichnye-situacii.html',
        'slug' => 'tipichnye-situacii-proverki-stazha',
        'title' => 'Типичные ситуации, когда стоит проверить пенсионное дело',
        'category' => 'usluga',
        'excerpt' => 'Сомнения в стаже, архивы, отказ СФР и другие типичные поводы для сверки документов.',
        'seo_title' => 'Типичные ситуации проверки пенсионного стажа',
        'seo_description' => 'Когда стоит сверить ИЛС и трудовую: пробелы в стаже, архивы, отказ и помощь родственникам.',
        'related' => [
            'kak-zakazat-vypisku-ils',
            'kak-proverit-stazh-v-vypiske-ils',
            'otkaz-sfr-chto-proverit-v-dokumentah',
        ],
    ],
    [
        'file' => '07-chto-vy-poluchite.html',
        'slug' => 'chto-vy-poluchite-posle-proverki-stazha',
        'title' => 'Что вы получите после проверки пенсионного дела',
        'category' => 'usluga',
        'excerpt' => 'Отчёт, чек-лист, черновики и инструкция подачи — без гарантии перерасчёта.',
        'seo_title' => 'Что входит в проверку пенсионного дела',
        'seo_description' => 'Какие материалы получает клиент после диагностики и сопровождения пенсионного дела.',
        'related' => [
            'chem-otlichaetsya-diagnostika-ot-soprovozhdeniya',
            'kak-rabotat-v-max-i-lichnom-kabinete',
            'pochemu-reshenie-prinimaet-tolko-sfr',
        ],
    ],
    [
        'file' => '08-max-i-kabinet.html',
        'slug' => 'kak-rabotat-v-max-i-lichnom-kabinete',
        'title' => 'Как работать в MAX и личном кабинете',
        'category' => 'usluga',
        'excerpt' => 'MAX — основной канал; кабинет — тот же аккаунт. Документы не загружают через сайт.',
        'seo_title' => 'MAX и личный кабинет — как работать',
        'seo_description' => 'Как пользоваться MAX и веб-кабинетом для проверки стажа без загрузки файлов на сайт.',
        'related' => [
            'chto-vy-poluchite-posle-proverki-stazha',
            'kak-pomoch-rodstvenniku-proverit-stazh',
            'chastye-voprosy-o-proverke-stazha',
        ],
    ],
    [
        'file' => '09-faq-rasshirennyy.html',
        'slug' => 'chastye-voprosy-o-proverke-stazha',
        'title' => 'Частые вопросы о проверке стажа — расширенный разбор',
        'category' => 'usluga',
        'excerpt' => 'Документы, оплата, родственники, статус дела и границы обещаний — подробно.',
        'seo_title' => 'FAQ: расчёт пенсии, калькулятор стажа и проверка ИЛС',
        'seo_description' => 'Чем пенсионный калькулятор СФР отличается от проверки стажа: частые вопросы о документах, ИЛС и границах сервиса.',
        'related' => [
            'pochemu-reshenie-prinimaet-tolko-sfr',
            'kakie-dokumenty-sobrat-do-obrashcheniya-v-sfr',
            'chem-otlichaetsya-diagnostika-ot-soprovozhdeniya',
        ],
    ],
    [
        'file' => '17-severnyy-stazh.html',
        'slug' => 'severnyy-stazh-i-rayonnyy-koefficient',
        'title' => 'Северный стаж для пенсии: что сверить',
        'category' => 'stazh',
        'excerpt' => 'Северный стаж для пенсии, Крайний Север и приравненные местности: сверка, если северный стаж не учли.',
        'seo_title' => 'Северный стаж для пенсии: что сверить',
        'seo_description' => 'Северный стаж для пенсии и пенсия в районах, приравненных к крайнему северу: что сверить в ИЛС. Без обещания перерасчёта.',
        'related' => [
            'kak-proverit-stazh-v-vypiske-ils',
            'chto-delat-esli-period-raboty-ne-uchten',
            'lgotnyy-i-pedagogicheskiy-stazh',
        ],
    ],
    [
        'file' => '18-edv-i-pensiya.html',
        'slug' => 'edv-i-pensiya-chto-proveryat-otdelno',
        'title' => 'ЕДВ и пенсия: что проверять отдельно',
        'category' => 'stazh',
        'excerpt' => 'Как отделить вопросы стажа и ИЛС от вопросов выплат и ЕДВ.',
        'seo_title' => 'ЕДВ и пенсия: что проверять отдельно',
        'seo_description' => 'ЕДВ и пенсия: что относится к стажу, а что проверять отдельно, чтобы не смешивать разные решения СФР.',
        'related' => [
            'kak-proverit-stazh-v-vypiske-ils',
            'otkaz-sfr-chto-proverit-v-dokumentah',
            'kakie-dokumenty-sobrat-do-obrashcheniya-v-sfr',
        ],
    ],
    [
        'file' => '19-lgotnyy-stazh.html',
        'slug' => 'lgotnyy-i-pedagogicheskiy-stazh',
        'title' => 'Льготный стаж: что проверить в документах',
        'category' => 'stazh',
        'excerpt' => 'Льготный и педагогический стаж: что проверить, если льготный стаж не учли в ИЛС.',
        'seo_title' => 'Льготный стаж: что проверить в документах',
        'seo_description' => 'Льготный стаж: что проверить в документах и ИЛС, если льготный или вредный стаж не учли. Без обещания досрочной пенсии.',
        'related' => [
            'severnyy-stazh-i-rayonnyy-koefficient',
            'kak-sverit-trudovuyu-knizhku-i-ils',
            'chto-delat-esli-period-raboty-ne-uchten',
        ],
    ],
    [
        'file' => '20-fio-trudovaya.html',
        'slug' => 'rashozhdeniya-fio-i-zapisi-trudovoy',
        'title' => 'Расхождения ФИО и ошибки в трудовой',
        'category' => 'dokumenty',
        'excerpt' => 'Что делать при опечатке, смене фамилии или несовпадении записи в трудовой и ИЛС.',
        'seo_title' => 'Расхождения ФИО и ошибки в трудовой',
        'seo_description' => 'Расхождения ФИО и ошибки в трудовой: как сверить записи и какие подтверждения обычно нужны до обращения в СФР.',
        'related' => [
            'kak-sverit-trudovuyu-knizhku-i-ils',
            'kakie-dokumenty-sobrat-do-obrashcheniya-v-sfr',
            'otkaz-sfr-chto-proverit-v-dokumentah',
        ],
    ],
];

$bySlug = [];
foreach ($articles as $a) {
    $bySlug[$a['slug']] = $a;
}

$relatedFooter = function (array $article) use ($bySlug, $homeUrl): string {
    $links = [];
    $related = array_slice($article['related'] ?? [], 0, 3);
    foreach ($related as $slug) {
        if (empty($bySlug[$slug])) {
            continue;
        }
        $links[] = sprintf(
            '<li><a href="%s">%s</a></li>',
            esc_url(home_url('/blog/' . $slug . '/')),
            esc_html($bySlug[$slug]['title'])
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
    $content = $body . "\n" . $relatedFooter($a) . "\n" . $disclaimer;
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

// Закрыть комментарии у всех опубликованных записей.
$allPosts = get_posts([
    'post_type' => 'post',
    'post_status' => 'publish',
    'numberposts' => -1,
    'fields' => 'ids',
]);
foreach ($allPosts as $pid) {
    wp_update_post([
        'ID' => (int) $pid,
        'comment_status' => 'closed',
        'ping_status' => 'closed',
    ]);
}
echo "COMMENTS_CLOSED posts=" . count($allPosts) . "\n";

// Страница записей /blog/
$blogPage = get_page_by_path('blog');
if (!$blogPage) {
    $blogId = wp_insert_post([
        'post_title' => 'Статьи',
        'post_name' => 'blog',
        'post_status' => 'publish',
        'post_type' => 'page',
        'post_content' => '<p>Справочник по проверке стажа: выписка ИЛС, трудовая книжка, документы и подача в СФР.</p>',
        'comment_status' => 'closed',
        'ping_status' => 'closed',
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
        'comment_status' => 'closed',
        'ping_status' => 'closed',
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
update_option('default_comment_status', 'closed');
update_option('default_ping_status', 'closed');

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
