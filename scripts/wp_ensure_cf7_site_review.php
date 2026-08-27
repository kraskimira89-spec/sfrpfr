<?php
/**
 * Contact Form 7: форма «Отзыв на сайте» → почта + очередь модерации (через MU hook).
 *
 * wp eval-file scripts/wp_ensure_cf7_site_review.php
 */
if (!class_exists('WPCF7_ContactForm')) {
    echo "0\n";
    return;
}

$title = 'Отзыв на сайте';
$contact = null;
$found = WPCF7_ContactForm::find(['posts_per_page' => 80]);
if (is_array($found)) {
    foreach ($found as $form) {
        if ($form instanceof WPCF7_ContactForm && $form->title() === $title) {
            $contact = $form;
            break;
        }
    }
}

if (!$contact instanceof WPCF7_ContactForm) {
    $contact = WPCF7_ContactForm::get_template([
        'title' => $title,
        'locale' => 'ru_RU',
    ]);
    $contact->set_title($title);
}

$form = <<<'FORM'
<div class="sfrfr-cf7-site-review-grid">
<div class="sfrfr-cf7-site-review-main">
<label>Текст отзыва *
[textarea* your-review maxlength:600 placeholder "Например: объяснили по шагам, куда подавать документы."]
</label>
</div>
<div class="sfrfr-cf7-site-review-side">
<div class="sfrfr-cf7-consent">
[acceptance acceptance-consent] <a class="sfrfr-consent-link" href="/soglasie/" target="_blank" rel="noopener noreferrer">Даю согласие на обработку персональных данных*</a> [/acceptance]
</div>
<div class="sfrfr-cf7-hp-wrap" aria-hidden="true">
<label>Сайт
[text sfrfr_hp class:sfrfr-cf7-hp tabindex:-1 autocomplete:off]
</label>
</div>
<div class="sfrfr-cf7-captcha sfrfr-cf7-site-review-captcha" aria-live="polite"></div>
[hidden smart-token]
<div class="sfrfr-cf7-submit">[submit "Отправить отзыв"]</div>
</div>
</div>
FORM;

$mailBody = <<<'BODY'
Отзыв с страницы /otzyvy/ (ожидает модерации перед публикацией на сайте).

Текст:
[your-review]

Страница: [_post_title]
URL: [_post_url]

--
Проверка стажа · форма отзыва на сайте
Не пишите СНИЛС и суммы пенсии. Рейтинг Яндекса эта форма не меняет.
BODY;

$mail = $contact->prop('mail');
if (!is_array($mail)) {
    $mail = [];
}
$mail['active'] = true;
$mail['recipient'] = 'proverkastaza@yandex.ru';
$mail['sender'] = 'Проверка стажа <proverkastaza@yandex.ru>';
$mail['subject'] = '[Проверка стажа] Отзыв на сайте (модерация)';
$mail['additional_headers'] = '';
$mail['body'] = $mailBody;
$mail['use_html'] = false;
$mail['exclude_blank'] = false;

$messages = $contact->prop('messages');
if (!is_array($messages)) {
    $messages = [];
}
$messages['mail_sent_ok'] = 'Спасибо. Отзыв принят и ждёт проверки перед публикацией на сайте.';
$messages['validation_error'] = 'Проверьте поля формы и повторите отправку.';
$messages['spam'] = 'Сообщение не отправлено. Обновите страницу и попробуйте ещё раз.';
$messages['accept_terms'] = 'Нужно согласие на обработку персональных данных.';
$messages['invalid_required'] = 'Заполните это поле.';

$contact->set_properties([
    'form' => $form,
    'mail' => $mail,
    'messages' => $messages,
    'additional_settings' => "subscribers_only: false\n",
]);

$id = $contact->save();
if (!$id) {
    echo "0\n";
    return;
}

update_option('sfrfr_cf7_site_review_id', (int) $id, false);
echo (int) $id . "\n";
