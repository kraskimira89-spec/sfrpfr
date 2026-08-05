<?php
/**
 * Публичное имя автора статей (вместо логина sfrfr_admin).
 * wp eval-file scripts/wp_apply_author_display.php
 */
$login = getenv('SFRFR_AUTHOR_LOGIN') ?: 'sfrfr_admin';
$display = getenv('SFRFR_AUTHOR_DISPLAY') ?: 'Сергей В.Б.';

$user = get_user_by('login', $login);
if (!$user) {
    // fallback: первый администратор / автор постов
    $users = get_users([
        'role__in' => ['administrator', 'editor', 'author'],
        'number' => 1,
        'orderby' => 'ID',
        'order' => 'ASC',
    ]);
    $user = $users[0] ?? null;
}
if (!$user) {
    fwrite(STDERR, "author user not found\n");
    echo "0\n";
    return;
}

wp_update_user([
    'ID' => (int) $user->ID,
    'display_name' => $display,
    'nickname' => $display,
    'first_name' => 'Сергей',
    'last_name' => 'В.Б.',
]);

echo (string) (int) $user->ID . "\n";
