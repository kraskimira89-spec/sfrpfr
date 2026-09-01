<?php
/**
 * Починить пустые/битые SEO description у постов и страниц.
 * Пишет _sfrfr_seo_description и синхронизирует Rank Math / Yoast.
 *
 * wp --path=SITE eval-file scripts/wp_repair_seo_descriptions.php
 */

if (!defined('ABSPATH')) {
    fwrite(STDERR, "Run via WP-CLI eval-file\n");
    exit(1);
}

$map = [
    'kak-proverit-stazh-v-vypiske-ils' => 'Как читать выписку ИЛС, сверить периоды работы с трудовой и понять, каких подтверждений не хватает перед обращением в СФР.',
    'kak-sverit-trudovuyu-knizhku-i-ils' => 'Пошаговая сверка трудовой книжки и выписки ИЛС: как найти расхождения и что подготовить для уточнения сведений.',
    'chto-delat-esli-period-raboty-ne-uchten' => 'Не учли стаж в ИЛС: что делать при не учтённом стаже — сверка, документы и обращение в СФР.',
    'arhivnaya-spravka-dlya-sfr-zachem-i-kuda' => 'Архивная справка о стаже: запрос в архив, ликвидация работодателя и что подготовить для СФР.',
    'tipichnye-situacii-proverki-stazha' => 'Типичные ситуации при проверке стажа: что сверять в документах и какой следующий шаг выбрать без обещания перерасчёта.',
    'kak-pomoch-rodstvenniku-proverit-stazh' => 'Как родственнику помочь проверить стаж: согласие, документы, каналы связи и границы участия без передачи сканов в открытый чат.',
    'chto-vy-poluchite-posle-proverki-stazha' => 'Что входит в результат проверки стажа: разбор документов, план действий и границы услуги сервиса «Проверка стажа».',
    'kak-rabotat-v-max-i-lichnom-kabinete' => 'Как связаны MAX и личный кабинет на сайте: что можно обсуждать в мессенджере и куда загружать документы.',
    'chastye-voprosy-o-proverke-stazha' => 'Частые вопросы о проверке стажа и ИЛС: документы, сроки, каналы обращения и типичные ограничения услуги.',
    'kakie-dokumenty-sobrat-do-obrashcheniya-v-sfr' => 'Какие документы собрать до обращения в СФР при проверке стажа: минимальный комплект и порядок подготовки.',
    'kak-podat-zayavlenie-cherez-gosuslugi-ili-mfc' => 'Как выбрать способ подачи в СФР: сначала Госуслуги, затем обращение в СФР; МФЦ — только при доступности услуги в регионе.',
    'otkaz-sfr-chto-proverit-v-dokumentah' => 'Не учли стаж или получили отказ СФР: как сохранить решение, определить причину и собрать документы для следующего обращения.',
    'pensiya-po-invalidnosti-i-stazh-na-chto-smotret' => 'Пенсия по инвалидности и стаж: что сверять отдельно и как не смешивать разные основания выплат.',
    'chem-otlichaetsya-diagnostika-ot-soprovozhdeniya' => 'Чем диагностика стажа отличается от сопровождения обращения: состав работ, результат и ограничения.',
    'pochemu-reshenie-prinimaet-tolko-sfr' => 'Почему решение о перерасчёте принимает только СФР: роль сервиса, границы помощи и что клиент делает самостоятельно.',
    'chek-list-pered-zapisju-v-mfc' => 'Как проверить способ подачи на Госуслугах и в СФР, а затем подготовиться к обращению в МФЦ по вопросу стажа.',
    'severnyy-stazh-i-rayonnyy-koefficient' => 'Северный стаж для пенсии: что сверить в трудовой и ИЛС, если северный стаж не учли.',
    'edv-i-pensiya-chto-proveryat-otdelno' => 'ЕДВ и пенсия: что относится к стажу, а что проверять отдельно, чтобы не смешивать разные решения СФР.',
    'lgotnyy-i-pedagogicheskiy-stazh' => 'Льготный стаж: что проверить в документах, если льготный или вредный стаж не учли.',
    'rashozhdeniya-fio-i-zapisi-trudovoy' => 'Расхождения ФИО и ошибки в трудовой: как сверить записи и какие подтверждения обычно нужны до обращения в СФР.',
    'oferta' => 'Условия оказания услуг сервиса «Проверка стажа»: состав сопровождения, порядок оплаты, права и обязанности сторон.',
    'politika-pdn' => 'Политика обработки персональных данных сервиса «Проверка стажа»: цели, основания, сроки и права пользователя.',
    'soglasie' => 'Согласие на обработку персональных данных при обращении в сервис «Проверка стажа».',
    'cookies' => 'Правила использования файлов браузера и аналитики на сайте сервиса «Проверка стажа».',
];

function sfrfr_repair_desc_clean(string $value): string
{
    $value = wp_check_invalid_utf8($value, true);
    $normalized = preg_replace('/\s+/', ' ', wp_strip_all_tags(strip_shortcodes($value)));
    return trim(is_string($normalized) ? $normalized : $value);
}

$ids = get_posts([
    'post_type' => ['post', 'page'],
    'post_status' => ['publish', 'draft', 'pending'],
    'numberposts' => -1,
    'fields' => 'ids',
]);

$fixed = 0;
foreach ($ids as $postId) {
    $postId = (int) $postId;
    $slug = (string) get_post_field('post_name', $postId);
    $current = sfrfr_repair_desc_clean((string) get_post_meta($postId, '_sfrfr_seo_description', true));
    if ($current === '') {
        $current = sfrfr_repair_desc_clean((string) get_post_meta($postId, '_rank_math_description', true));
    }
    if ($current === '') {
        $current = sfrfr_repair_desc_clean((string) get_post_meta($postId, '_yoast_wpseo_metadesc', true));
    }
    if ($current === '' && isset($map[$slug])) {
        $current = $map[$slug];
    }
    if ($current === '') {
        $excerpt = sfrfr_repair_desc_clean((string) get_post_field('post_excerpt', $postId));
        if ($excerpt === '') {
            $excerpt = sfrfr_repair_desc_clean((string) get_post_field('post_content', $postId));
        }
        if ($excerpt !== '') {
            if (function_exists('mb_substr')) {
                $current = rtrim(mb_substr($excerpt, 0, 160, 'UTF-8'));
            } else {
                $current = rtrim(substr($excerpt, 0, 160));
            }
        }
    }
    if ($current === '') {
        continue;
    }
    update_post_meta($postId, '_sfrfr_seo_description', $current);
    update_post_meta($postId, '_rank_math_description', $current);
    update_post_meta($postId, '_yoast_wpseo_metadesc', $current);
    $fixed++;
    echo "DESC {$slug}={$postId}\n";
}

$termFixed = 0;
foreach (get_terms(['taxonomy' => 'category', 'hide_empty' => false]) as $term) {
    if (!$term instanceof WP_Term) {
        continue;
    }
    if (in_array($term->slug, ['situacii', 'analitika'], true)) {
        continue;
    }
    $desc = sfrfr_repair_desc_clean((string) $term->description);
    if ($desc === '') {
        $desc = "Статьи по теме «{$term->name}»: инструкции, документы и частые ошибки при проверке пенсионного стажа и сведений ИЛС.";
        wp_update_term((int) $term->term_id, 'category', ['description' => $desc]);
        $termFixed++;
        echo "TERM {$term->slug}\n";
    }
}

echo "REPAIR posts_pages={$fixed} terms={$termFixed}\n";
