import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
html = Path(r"C:/Users/user/AppData/Local/Temp/sfrfr-home.html").read_text(
    encoding="utf-8", errors="replace"
)


def strip(t: str) -> str:
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\s+", " ", t).strip()


# Find primary nav UL
nav = re.search(
    r'<div[^>]*id="primary-site-navigation-desktop".*?</div>\s*</div>\s*</div>',
    html,
    re.S,
)
block = nav.group(0) if nav else ""
print("nav_block_len", len(block))

# Fallback: main-header-menu
if len(block) < 200:
    m = re.search(
        r'<ul[^>]*class="[^"]*main-header-menu[^"]*"[^>]*>.*?</ul>\s*</div>',
        html,
        re.S,
    )
    block = m.group(0) if m else html
    print("fallback_block_len", len(block))

# Top-level items
for m in re.finditer(
    r'<li[^>]*id="(menu-item-\d+|page-item-\d+)"[^>]*class="([^"]*)"[^>]*>\s*<a([^>]*)>(.*?)</a>',
    block,
    re.S,
):
    mid, cls, aattrs, title = m.group(1), m.group(2), m.group(3), strip(m.group(4))
    href = re.search(r'href="([^"]*)"', aattrs)
    print(
        "TOP",
        mid,
        "has_children" if "menu-item-has-children" in cls else "-",
        title,
        href.group(1) if href else "",
        "CLS",
        cls[:160],
    )

# All submenus with parent title from preceding <a>
for i, m in enumerate(re.finditer(r'<ul class="sub-menu"[^>]*>', html)):
    start = m.start()
    end = html.find("</ul>", start)
    chunk = html[start:end]
    back = html[max(0, start - 800) : start]
    parent_as = re.findall(r"<a[^>]*>(.*?)</a>", back, re.S)
    parent = strip(parent_as[-1]) if parent_as else "?"
    items = []
    for am in re.finditer(r"<li([^>]*)>\s*<a([^>]*)>(.*?)</a>", chunk, re.S):
        li_attr, a_attr, t = am.group(1), am.group(2), strip(am.group(3))
        href = re.search(r'href="([^"]*)"', a_attr)
        cls = re.search(r'class="([^"]*)"', li_attr)
        items.append(
            {
                "t": t,
                "href": href.group(1) if href else "",
                "cls": (cls.group(1) if cls else "")[:120],
            }
        )
    print(f"SUB[{i}] parent={parent!r} n={len(items)}")
    for it in items[:15]:
        print("  ", it)

# Astra CSS variables related to menu
for name in [
    "--ast-global-color-0",
    "--ast-global-color-1",
    "--ast-global-color-2",
    "--ast-global-color-3",
    "--ast-global-color-4",
    "--ast-global-color-5",
]:
    mm = re.search(rf"{re.escape(name)}:([^;]+);", html)
    print("VAR", name, mm.group(1) if mm else "MISSING")

# All color/background rules mentioning sub-menu OR menu-link inside builder-menu
rules = re.findall(
    r"([^{}]*?(?:sub-menu|menu-link)[^{}]*)\{([^}]*)\}",
    html,
)
print("total_menuish_rules", len(rules))
for sel, body in rules:
    if "sub-menu" not in sel and ".sub-menu" not in sel:
        continue
    if not any(k in body for k in ("color", "background", "border", "box-shadow")):
        continue
    print("SEL", re.sub(r"\s+", " ", sel.strip())[:220])
    print("BODY", re.sub(r"\s+", " ", body.strip())[:300])
    print("---")
