<?php
/**
 * Публичная почта сервиса + уведомления WPForms → info@proverkastaza.ru
 * wp eval-file scripts/wp_set_public_email.php
 */
$email = getenv('SFRFR_PUBLIC_EMAIL') ?: 'info@proverkastaza.ru';
$email = trim((string) $email);
if ($email === '' || !is_email($email)) {
    fwrite(STDERR, "invalid email\n");
    echo "0\n";
    return;
}

delete_option('adminhash');
delete_option('new_admin_email');
update_option('admin_email', $email);

$patched = 0;
if (function_exists('wpforms') && function_exists('wpforms_decode') && function_exists('wpforms_encode')) {
    $forms = wpforms()->form->get('', ['post_type' => 'wpforms']);
    if (is_array($forms)) {
        foreach ($forms as $form) {
            $data = wpforms_decode($form->post_content);
            if (!is_array($data)) {
                continue;
            }
            $changed = false;
            if (!empty($data['settings']['notifications']) && is_array($data['settings']['notifications'])) {
                foreach ($data['settings']['notifications'] as $nid => $note) {
                    if (!is_array($note)) {
                        continue;
                    }
                    $data['settings']['notifications'][$nid]['email'] = $email;
                    $data['settings']['notifications'][$nid]['sender_address'] = $email;
                    $changed = true;
                }
            }
            if ($changed) {
                wp_update_post([
                    'ID' => (int) $form->ID,
                    'post_content' => wpforms_encode($data),
                ]);
                $patched++;
            }
        }
    }
}

echo "admin_email={$email}; wpforms_patched={$patched}\n";
