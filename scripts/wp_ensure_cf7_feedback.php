<?php
/**
 * Contact Form 7: одна форма «Обратная связь» с темой-списком.
 *
 * wp eval-file scripts/wp_ensure_cf7_feedback.php
 */
if (!class_exists('WPCF7_ContactForm')) {
    echo "0\n";
    return;
}

$title = 'Обратная связь';
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
<div class="sfrfr-cf7-grid">
<div class="sfrfr-cf7-card">
<div class="sfrfr-cf7-field">
<label>Тема обращения *
[select* topic include_blank "Проверка стажа" "Северный стаж" "Стаж до 2002" "Перед пенсией" "Помочь родственнику" "Тарифы" "Не учли стаж" "Архивная справка" "Отказ СФР" "Как работаем" "Отзыв / качество сервиса" "Другой вопрос"]
</label>
</div>
<div class="sfrfr-cf7-field">
<label>ФИО *
[text* your-name autocomplete:name]
</label>
</div>
<div class="sfrfr-cf7-field">
<label>Электронная почта *
[email* your-email autocomplete:email]
</label>
</div>
<div class="sfrfr-cf7-field">
<label>Телефон *
[tel* your-phone autocomplete:tel]
</label>
</div>
</div>
<div class="sfrfr-cf7-card">
<div class="sfrfr-cf7-field sfrfr-cf7-field--message">
<label>Сообщение *
[textarea* your-message]
</label>
</div>
<div class="sfrfr-cf7-consent">
[acceptance acceptance-consent] <a class="sfrfr-consent-link" href="/soglasie/" target="_blank" rel="noopener noreferrer">Даю согласие на обработку персональных данных*</a> [/acceptance]
</div>
<div class="sfrfr-cf7-hp-wrap" aria-hidden="true">
<label>Сайт
[text sfrfr_hp class:sfrfr-cf7-hp tabindex:-1 autocomplete:off]
</label>
</div>
<div class="sfrfr-cf7-captcha" aria-live="polite"></div>
[hidden smart-token]
[hidden page-url]
<div class="sfrfr-cf7-submit">[submit "Отправить"]</div>
</div>
</div>
FORM;

$mailBody = <<<'BODY'
Тема: [topic]
Страница: [_post_title]
URL: [_post_url]
Страница (браузер): [page-url]

ФИО: [your-name]
Почта: [your-email]
Телефон: [your-phone]

Сообщение:
[your-message]

--
Проверка стажа · форма обратной связи
Документы и сканы через эту форму не принимаем.
BODY;

$mail = $contact->prop('mail');
if (!is_array($mail)) {
    $mail = [];
}
$mail['active'] = true;
$mail['recipient'] = 'info@proverkastaza.ru';
$mail['sender'] = 'Проверка стажа <info@proverkastaza.ru>';
$mail['subject'] = '[Проверка стажа] Обратная связь: [topic]';
$mail['additional_headers'] = 'Reply-To: [your-email]';
$mail['body'] = $mailBody;
$mail['use_html'] = false;
$mail['exclude_blank'] = false;

$messages = $contact->prop('messages');
if (!is_array($messages)) {
    $messages = [];
}
$messages['mail_sent_ok'] = 'Спасибо! Сообщение получено. Ответим по указанным контактам.';
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

update_option('sfrfr_cf7_feedback_id', (int) $id, false);
echo (int) $id . "\n";
