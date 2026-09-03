<?php require_once __DIR__ . '/i18n.php'; ?>
<footer class="site-footer">
    <p><?= htmlspecialchars(piratebox_t('footer.offline_notice')) ?></p>
    <p><?= htmlspecialchars(piratebox_t('footer.trouble_connecting')) ?> <span class="footer-url">http://piratebox/</span> <?= htmlspecialchars(piratebox_t('footer.trouble_connecting_or')) ?> <span class="footer-url">http://10.0.0.1/</span> <?= htmlspecialchars(piratebox_t('footer.trouble_connecting_fallback')) ?> <a href="/help.php"><?= htmlspecialchars(piratebox_t('footer.help_link')) ?></a>.</p>
    <p class="footer-trust"><a href="/help.php#trust"><strong><?= htmlspecialchars(piratebox_t('footer.trust_statement')) ?></strong> <?= htmlspecialchars(piratebox_t('footer.trust_statement_sub')) ?></a></p>
</footer>
