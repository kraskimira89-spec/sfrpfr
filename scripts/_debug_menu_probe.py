from pathlib import Path
import re
import json

html = Path(r"C:/Users/user/AppData/Local/Temp/sfrfr-home.html").read_text(
    encoding="utf-8", errors="replace"
)
print("len", len(html))
print("has_inset", "inset -3px 0 0" in html)
print("has_white_bg", "background: #ffffff !important" in html)
print("has_ink_color", "var(--sfrfr-ink, #1a2330) !important" in html)

for title in ["Главная", "Услуги", "Статьи", "Эксперты"]:
    print("title", title, "idx", html.find(title))


def strip(t: str) -> str:
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\s+", " ", t).strip()


links = re.findall(
    r'<a[^>]*class="[^"]*menu-link[^"]*"[^>]*>(.*?)</a>', html, re.S
)
texts = [strip(x) for x in links]
print("menu_links", texts[:50])

# parent items with children
parents = re.findall(
    r'<li[^>]*class="([^"]*menu-item-has-children[^"]*)"[^>]*>\s*<a[^>]*>(.*?)</a>',
    html,
    re.S,
)
print("parents", [(c[:120], strip(t)) for c, t in parents[:10]])

for i, m in enumerate(re.finditer(r'<ul class="sub-menu">', html)):
    start = m.start()
    chunk = html[start : start + 3000]
    items = [strip(x) for x in re.findall(r"<a[^>]*>(.*?)</a>", chunk, re.S)]
    # look back for parent title
    back = html[max(0, start - 500) : start]
    parent_titles = [strip(x) for x in re.findall(r"<a[^>]*>(.*?)</a>", back, re.S)]
    parent = parent_titles[-1] if parent_titles else "?"
    print(f"submenu[{i}] parent={parent!r} items={items[:12]}")
    if i >= 5:
        break

# Astra dynamic CSS touching submenu
ast = re.findall(r"[^{};\n]*sub-menu[^{]*\{[^}]+\}", html)
print("ast_submenu_rules", len(ast))
interesting = []
for r in ast:
    if any(k in r for k in ("background", "color", "border", "box-shadow")):
        interesting.append(re.sub(r"\s+", " ", r)[:350])
for r in interesting[:30]:
    print("RULE", r)

# Also check style tag order: custom css id
for mid in re.findall(r'id="(wp-custom-css|astra-[^"]*|[^"]*custom[^"]*)"', html):
    print("style_or_link_id", mid)

# find which stylesheet/style contains our rule and what comes after
pos = html.find("inset -3px 0 0")
print("inset_pos", pos)
if pos >= 0:
    # find enclosing style id
    style_start = html.rfind("<style", 0, pos)
    style_end = html.find("</style>", pos)
    head = html[style_start : style_start + 120]
    print("style_head", head)
    # any later rules after our block that set sub-menu color/background
    after = html[pos : pos + 8000]
    later = re.findall(r"[^{]*sub-menu[^{]*\{[^}]+\}", after)
    print("later_submenu_in_same_or_after", len(later))
    for r in later[:15]:
        print("LATER", re.sub(r"\s+", " ", r)[:300])
