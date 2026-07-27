const fs = require("fs");
const path = require("path");
const root = "C:/Users/user/Documents/Cursor/SFRFR";

// --- home: insert #stati before #faq ---
const homePath = path.join(root, "scripts/assets/sfrfr-home.html");
let home = fs.readFileSync(homePath, "utf8");
if (!home.includes('id="stati"')) {
  const block = `  <section class="sfrfr-section" id="stati">
    <div class="sfrfr-wrap">
      <h2>Полезные статьи</h2>
      <p class="sfrfr-section__lead">Короткие справочники по ИЛС и документам — без обещаний результата.</p>
      <div class="sfrfr-cards sfrfr-cards--row sfrfr-cards--3 sfrfr-blog-teaser" style="margin-top:1.25rem">
        <article class="sfrfr-card sfrfr-blog-card">
          <h3><a href="/blog/kak-proverit-stazh-v-vypiske-ils/">Как проверить стаж в выписке ИЛС</a></h3>
          <p>Что смотреть в выписке и как найти «пробелы» в учёте.</p>
        </article>
        <article class="sfrfr-card sfrfr-blog-card">
          <h3><a href="/blog/kak-sverit-trudovuyu-knizhku-i-ils/">Как сверить трудовую и ИЛС</a></h3>
          <p>Таблица сверки записей и типичные расхождения.</p>
        </article>
        <article class="sfrfr-card sfrfr-blog-card">
          <h3><a href="/blog/arhivnaya-spravka-dlya-sfr-zachem-i-kuda/">Архивная справка для СФР</a></h3>
          <p>Зачем нужна, куда запрашивать и как приложить к обращению.</p>
        </article>
      </div>
      <p style="margin-top:1rem"><a class="sfrfr-btn sfrfr-btn--ghost" href="/blog/">Все статьи</a></p>
    </div>
  </section>

`;
  const faqRe = /  <section class="sfrfr-section(?: sfrfr-section--alt)?" id="faq">/;
  if (!faqRe.test(home)) throw new Error("faq section not found");
  home = home.replace(faqRe, block + '  <section class="sfrfr-section sfrfr-section--alt" id="faq">');
  // zayavka should not be alt if faq is alt
  home = home.replace(
    '<section class="sfrfr-section sfrfr-section--alt" id="zayavka">',
    '<section class="sfrfr-section" id="zayavka">'
  );
  fs.writeFileSync(homePath, home);
  console.log("home updated");
} else {
  console.log("home already has stati");
}

// --- copy seed from generated content file ---
const seedSrc = path.join(root, "scripts/_seed_tz11_new.php");
const seedDst = path.join(root, "scripts/wp_seed_blog_tz11.php");
if (!fs.existsSync(seedSrc)) {
  console.error("missing", seedSrc);
  process.exit(1);
}
fs.copyFileSync(seedSrc, seedDst);
console.log("seed copied", fs.statSync(seedDst).size);
