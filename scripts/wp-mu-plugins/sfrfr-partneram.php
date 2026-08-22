<?php
/**
 * Plugin Name: SFRFR Partneram Page
 * Description: Презентация PPTX для страницы /partneram/ — metabox и CTA в контенте.
 */

if (!defined('ABSPATH')) {
    exit;
}

const SFRFR_PARTNERAM_META_FILE = '_sfrfr_presentation_file';
const SFRFR_PARTNERAM_CTA_MARKER = '<!-- SFRFR_PRESENTATION_CTA -->';
const SFRFR_PARTNER_FORM_MARKER = '<!-- SFRFR_PARTNER_FORM -->';
const SFRFR_PARTNER_FORM_TITLE = 'Партнёрство';

function sfrfr_partneram_page_id(): int
{
    static $id = null;
    if ($id !== null) {
        return $id;
    }
    $page = get_page_by_path('partneram');
    $id = $page instanceof WP_Post ? (int) $page->ID : 0;
    return $id;
}

function sfrfr_partneram_attachment_id(int $pageId = 0): int
{
    if ($pageId <= 0) {
        $pageId = sfrfr_partneram_page_id();
    }
    if ($pageId <= 0) {
        return 0;
    }
    return max(0, (int) get_post_meta($pageId, SFRFR_PARTNERAM_META_FILE, true));
}

function sfrfr_partneram_cta_html(int $pageId = 0): string
{
    $attachId = sfrfr_partneram_attachment_id($pageId);
    if ($attachId <= 0) {
        return '<span class="sfrfr-partneram-presentation-fallback">Презентация предоставляется по запросу</span>';
    }

    $url = wp_get_attachment_url($attachId);
    if (!is_string($url) || $url === '') {
        return '<span class="sfrfr-partneram-presentation-fallback">Презентация предоставляется по запросу</span>';
    }

    $path = get_attached_file($attachId);
    $sizeLabel = '';
    if (is_string($path) && $path !== '' && is_readable($path)) {
        $bytes = filesize($path);
        if (is_int($bytes) && $bytes > 0) {
            $sizeLabel = size_format($bytes, 1);
        }
    }

    $modified = get_post_modified_time('d.m.Y', false, $attachId, true);
    $metaParts = array_filter([$sizeLabel, $modified !== false ? 'обновлено ' . $modified : '']);
    $meta = $metaParts ? '<span class="sfrfr-partneram-presentation-meta">' . esc_html(implode(' · ', $metaParts)) . '</span>' : '';

    return sprintf(
        '<a class="sfrfr-btn sfrfr-btn--primary" href="%s" download data-sfrfr-goal="partner_pptx_download">%s</a>%s',
        esc_url($url),
        esc_html('Скачать презентацию'),
        $meta
    );
}

function sfrfr_partner_form_id(): int
{
    static $id = null;
    if ($id !== null) {
        return $id;
    }
    $id = 0;
    if (!function_exists('wpforms')) {
        return 0;
    }
    $forms = wpforms()->form->get('', ['post_type' => 'wpforms']);
    if (!is_array($forms)) {
        return 0;
    }
    foreach ($forms as $form) {
        if (isset($form->post_title) && (string) $form->post_title === SFRFR_PARTNER_FORM_TITLE) {
            $id = (int) $form->ID;
            break;
        }
    }
    return $id;
}

function sfrfr_partner_form_html(): string
{
    $formId = sfrfr_partner_form_id();
    if ($formId <= 0) {
        return '<p class="sfrfr-note sfrfr-partner-form-fallback">Форма партнёрского обращения временно недоступна. Напишите на <a href="mailto:info@proverkastaza.ru">info@proverkastaza.ru</a>.</p>';
    }
    return '<div class="sfrfr-partner-form">' . do_shortcode('[wpforms id="' . $formId . '"]') . '</div>';
}

add_filter('the_content', static function (string $content): string {
    if (!is_page('partneram')) {
        return $content;
    }
    if (str_contains($content, SFRFR_PARTNERAM_CTA_MARKER)) {
        $cta = sfrfr_partneram_cta_html((int) get_the_ID());
        $content = str_replace(SFRFR_PARTNERAM_CTA_MARKER, $cta, $content);
    }
    if (str_contains($content, SFRFR_PARTNER_FORM_MARKER)) {
        $content = str_replace(SFRFR_PARTNER_FORM_MARKER, sfrfr_partner_form_html(), $content);
    }
    return $content;
}, 20);

add_action('wp_footer', static function (): void {
    if (!is_page('partneram')) {
        return;
    }
    $formId = sfrfr_partner_form_id();
    ?>
<script>
(function () {
  if (typeof window.sfrfrMetrikaGoal !== "function") return;
  window.sfrfrMetrikaGoal("partner_page_view");
  var partnerFormId = <?php echo (int) $formId; ?>;
  document.addEventListener("wpformsAjaxSubmitSuccess", function (ev) {
    var detail = ev && ev.detail ? ev.detail : {};
    var fid = detail.formId || (detail.form && detail.form.id);
    if (partnerFormId > 0 && String(fid) === String(partnerFormId)) {
      window.sfrfrMetrikaGoal("partner_lead_ok");
    }
  });
})();
</script>
    <?php
}, 30);

add_action('add_meta_boxes', static function (): void {
    $pageId = sfrfr_partneram_page_id();
    if ($pageId <= 0) {
        return;
    }
    add_meta_box(
        'sfrfr-partneram-presentation',
        'Презентация для партнёров (PPTX)',
        static function (WP_Post $post): void {
            wp_nonce_field('sfrfr_partneram_presentation', 'sfrfr_partneram_presentation_nonce');
            $attachId = sfrfr_partneram_attachment_id((int) $post->ID);
            $url = $attachId > 0 ? wp_get_attachment_url($attachId) : '';
            ?>
            <p>
              <input type="hidden" id="sfrfr_presentation_file" name="sfrfr_presentation_file" value="<?php echo esc_attr((string) $attachId); ?>">
              <button type="button" class="button" id="sfrfr_presentation_pick">Выбрать файл</button>
              <button type="button" class="button" id="sfrfr_presentation_clear">Убрать</button>
            </p>
            <p id="sfrfr_presentation_label">
              <?php
                if (is_string($url) && $url !== '') {
                    echo esc_html(basename($url));
                } else {
                    echo 'Файл не выбран — на странице будет текст «Презентация предоставляется по запросу».';
                }
                ?>
            </p>
            <script>
            (function () {
              if (typeof wp === 'undefined' || !wp.media) return;
              var frame;
              var input = document.getElementById('sfrfr_presentation_file');
              var label = document.getElementById('sfrfr_presentation_label');
              document.getElementById('sfrfr_presentation_pick').addEventListener('click', function (e) {
                e.preventDefault();
                if (frame) { frame.open(); return; }
                frame = wp.media({
                  title: 'Презентация PPTX',
                  button: { text: 'Использовать' },
                  library: { type: ['application/vnd.openxmlformats-officedocument.presentationml.presentation', 'application/vnd.ms-powerpoint'] },
                  multiple: false
                });
                frame.on('select', function () {
                  var file = frame.state().get('selection').first().toJSON();
                  input.value = file.id;
                  label.textContent = file.filename || file.title || 'Файл выбран';
                });
                frame.open();
              });
              document.getElementById('sfrfr_presentation_clear').addEventListener('click', function (e) {
                e.preventDefault();
                input.value = '0';
                label.textContent = 'Файл не выбран — на странице будет текст «Презентация предоставляется по запросу».';
              });
            })();
            </script>
            <?php
        },
        'page',
        'side',
        'default'
    );
});

add_action('save_post_page', static function (int $postId): void {
    if (!isset($_POST['sfrfr_partneram_presentation_nonce'])
        || !wp_verify_nonce((string) $_POST['sfrfr_partneram_presentation_nonce'], 'sfrfr_partneram_presentation')) {
        return;
    }
    if (defined('DOING_AUTOSAVE') && DOING_AUTOSAVE) {
        return;
    }
    if (!current_user_can('edit_page', $postId)) {
        return;
    }
    $page = get_post($postId);
    if (!$page instanceof WP_Post || $page->post_name !== 'partneram') {
        return;
    }
    $attachId = isset($_POST['sfrfr_presentation_file']) ? (int) $_POST['sfrfr_presentation_file'] : 0;
    if ($attachId > 0) {
        update_post_meta($postId, SFRFR_PARTNERAM_META_FILE, $attachId);
    } else {
        delete_post_meta($postId, SFRFR_PARTNERAM_META_FILE);
    }
}, 10, 1);
