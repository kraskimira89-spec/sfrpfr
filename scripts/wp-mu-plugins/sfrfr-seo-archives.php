<?php
/**
 * Plugin Name: SFRFR SEO Archives
 * Description: Title и description рубрик блога /blog/rubrika/* с лексикой поисковых запросов.
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * @return array<string, array{title: string, description: string}>
 */
function sfrfr_seo_category_meta(): array
{
    return [
        'ils' => [
            'title' => 'Выписка ИЛС: как заказать, прочитать и проверить стаж',
            'description' => 'Как заказать выписку ИЛС (СЗИ-ИЛС) на Госуслугах, проверить стаж в выписке и найти пропущенные периоды. Без калькулятора, решение принимает СФР.',
        ],
        'stazh' => [
            'title' => 'Северный и льготный стаж для пенсии: что проверить',
            'description' => 'Северный и льготный стаж, стаж при пенсии по инвалидности и ЕДВ: что сверить в трудовой и ИЛС, если стаж не учли. Решение об учёте принимает СФР.',
        ],
        'dokumenty' => [
            'title' => 'Документы для стажа: трудовая, архивная справка, ФИО',
            'description' => 'Какие документы собрать для подтверждения стажа: трудовая книжка, архивная справка о стаже, расхождения ФИО. Чек-листы до обращения в СФР.',
        ],
        'podacha' => [
            'title' => 'Не учли стаж или отказ СФР: как подать через Госуслуги',
            'description' => 'Как подать заявление в СФР через Госуслуги или МФЦ и что делать после отказа СФР, если не учли стаж. Подаёте вы сами, решение принимает СФР.',
        ],
        'rodstvenniki' => [
            'title' => 'Помочь родственнику с пенсией: проверить стаж и документы',
            'description' => 'Как помочь маме или папе проверить пенсионный стаж: согласие, выписка ИЛС, документы и безопасная передача файлов без публичных чатов.',
        ],
        'usluga' => [
            'title' => 'Проверка стажа: диагностика, сопровождение, частые вопросы',
            'description' => 'Как устроена проверка стажа: диагностика 3 000 ₽, подготовка документов 5 000 ₽, сопровождение 8 000 ₽, частые вопросы и границы услуги.',
        ],
    ];
}

function sfrfr_seo_current_category_meta(): ?array
{
    if (!is_category()) {
        return null;
    }
    $term = get_queried_object();
    if (!$term instanceof WP_Term) {
        return null;
    }
    $map = sfrfr_seo_category_meta();
    return $map[$term->slug] ?? null;
}

add_filter('document_title_parts', static function (array $parts): array {
    $meta = sfrfr_seo_current_category_meta();
    if ($meta !== null) {
        $parts['title'] = $meta['title'];
        unset($parts['site'], $parts['tagline']);
    }
    return $parts;
}, 30);

add_filter('sfrfr_seo_category_description', static function ($description, $term = null) {
    $meta = sfrfr_seo_current_category_meta();
    return $meta !== null ? $meta['description'] : $description;
}, 10, 2);
