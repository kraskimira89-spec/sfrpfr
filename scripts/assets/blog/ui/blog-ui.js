(function () {
  "use strict";

  function slugify(text) {
    return String(text || "")
      .trim()
      .toLowerCase()
      .replace(/[^\w\u0400-\u04FF]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 64);
  }

  function ensureHeadingIds(root) {
    var heads = root.querySelectorAll("h2, h3");
    var used = {};
    heads.forEach(function (h) {
      if (!h.id) {
        var base = slugify(h.textContent) || "section";
        var id = base;
        var n = 2;
        while (used[id] || document.getElementById(id)) {
          id = base + "-" + n;
          n += 1;
        }
        h.id = id;
      }
      used[h.id] = true;
    });
    return heads;
  }

  function buildToc() {
    var article =
      document.querySelector(".sfrfr-blog-article-body") ||
      document.querySelector("article .entry-content") ||
      document.querySelector(".entry-content");
    if (!article) return;

    var heads = ensureHeadingIds(article);
    if (heads.length < 2) return;

    var existing = document.querySelector(".sfrfr-blog-toc");
    if (existing) return;

    var wrap = document.createElement("nav");
    wrap.className = "sfrfr-blog-toc";
    wrap.setAttribute("aria-label", "Содержание");

    var isNarrow = window.matchMedia("(max-width: 899px)").matches;
    var list = document.createElement("ol");
    heads.forEach(function (h) {
      var li = document.createElement("li");
      if (h.tagName === "H3") li.style.marginLeft = "0.75rem";
      var a = document.createElement("a");
      a.href = "#" + h.id;
      a.textContent = h.textContent.trim();
      li.appendChild(a);
      list.appendChild(li);
    });

    if (isNarrow) {
      var details = document.createElement("details");
      var summary = document.createElement("summary");
      summary.textContent = "Содержание";
      details.appendChild(summary);
      details.appendChild(list);
      wrap.appendChild(details);
    } else {
      var title = document.createElement("div");
      title.className = "sfrfr-blog-toc__title";
      title.textContent = "Содержание";
      wrap.appendChild(title);
      wrap.appendChild(list);
      wrap.classList.add("sfrfr-blog-toc--desktop");
    }

    article.insertBefore(wrap, article.firstChild);
  }

  function insertMidCta() {
    if (document.querySelector(".sfrfr-blog-cta--mid")) return;
    var article =
      document.querySelector(".sfrfr-blog-article-body") ||
      document.querySelector("article .entry-content") ||
      document.querySelector(".entry-content");
    if (!article) return;

    var h2s = article.querySelectorAll("h2");
    var anchor = h2s.length >= 2 ? h2s[1] : null;
    var cta = document.createElement("aside");
    var cfg = window.sfrfrBlogUi || {};
    var maxUrl = cfg.maxUrl || "https://max.ru/id8905998693_1_bot";
    var formUrl = cfg.formUrl || "/#zayavka";
    cta.className = "sfrfr-blog-cta sfrfr-blog-cta--mid";
    cta.innerHTML =
      '<p class="sfrfr-blog-cta__title">Начать проверку</p>' +
      '<p class="sfrfr-blog-cta__text">Начните в личном чате MAX или оставьте заявку — без загрузки сканов на этот сайт.</p>' +
      '<a class="sfrfr-blog-cta__btn" href="' +
      maxUrl +
      '" target="_blank" rel="noopener noreferrer">Начать проверку в MAX</a> ' +
      '<a class="sfrfr-blog-cta__btn sfrfr-blog-cta__btn--ghost" href="' +
      formUrl +
      '">Оставить заявку</a>';

    if (anchor && anchor.parentNode === article) {
      article.insertBefore(cta, anchor);
    } else {
      var kids = article.children;
      var mid = Math.floor(kids.length / 2);
      if (kids[mid]) article.insertBefore(cta, kids[mid]);
      else article.appendChild(cta);
    }

    // Не вкладывать CTA внутрь списков/блоков с overflow
    if (cta.parentElement && cta.parentElement !== article) {
      article.insertBefore(cta, cta.parentElement);
    }
  }

  if (document.body.classList.contains("single-post") || document.body.classList.contains("sfrfr-blog-single")) {
    buildToc();
    insertMidCta();
  }
})();
