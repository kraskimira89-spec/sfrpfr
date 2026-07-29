from scripts.seo_production_audit import (
    audit_html,
    normalize_url,
    parse_sitemap,
)

VALID_HTML = """
<!doctype html>
<html lang="ru">
<head>
  <meta name="description" content="Проверка стажа и документов." />
  <link rel="canonical" href="https://proverkastaza.ru/blog/test/" />
  <meta property="og:title" content="Тест" />
  <meta property="og:description" content="Описание" />
  <meta property="og:url" content="https://proverkastaza.ru/blog/test/" />
  <script type="application/ld+json">
    {"@context":"https://schema.org","@graph":[{"@type":"Article"}]}
  </script>
</head>
<body><h1>Тест</h1></body>
</html>
"""


def test_audit_html_accepts_complete_page() -> None:
    result = audit_html("https://proverkastaza.ru/blog/test/", 200, VALID_HTML)
    assert result.issues == ()


def test_audit_html_reports_structural_regressions() -> None:
    description = '<meta name="description" content="Проверка стажа и документов." />'
    broken = VALID_HTML.replace(description, "")
    broken = broken.replace("<h1>Тест</h1>", "<h1>Один</h1><h1>Два</h1>")
    result = audit_html("https://proverkastaza.ru/blog/test/", 200, broken)
    assert "description:0" in result.issues
    assert "h1:2" in result.issues


def test_normalize_url_drops_query_and_normalizes_slash() -> None:
    assert normalize_url("HTTPS://PROVERKASTAZA.RU/blog/test?x=1") == (
        "https://proverkastaza.ru/blog/test/"
    )


def test_parse_sitemap_reads_locations() -> None:
    xml = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://proverkastaza.ru/</loc></url>
      <url><loc>https://proverkastaza.ru/blog/</loc></url>
    </urlset>
    """
    assert parse_sitemap(xml) == [
        "https://proverkastaza.ru/",
        "https://proverkastaza.ru/blog/",
    ]
