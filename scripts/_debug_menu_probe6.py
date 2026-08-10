import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
html = Path(r"C:/Users/user/AppData/Local/Temp/sfrfr-home2.html").read_text(
    encoding="utf-8"
)


def strip(t: str) -> str:
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\s+", " ", t).strip()


# Desktop menu top-level titles
m = re.search(r'id="ast-hf-menu-1"[^>]*>(.*?)</nav>', html, re.S)
block = m.group(1) if m else ""
# top-level li only: match li then a until first sub-menu
tops = re.findall(
    r'<li[^>]*id="(menu-item-\d+)"[^>]*class="([^"]*)"[^>]*>\s*<a[^>]*class="menu-link"[^>]*>(.*?)</a>',
    block,
    re.S,
)
print("TOPS:")
for mid, cls, t in tops:
    print("-", mid, strip(t), "children" if "has-children" in cls else "")

# First submenu full HTML snippet
sm = re.search(r'<ul class="sub-menu">(.*?)</ul>', block, re.S)
if sm:
    print("FIRST_SUBMENU_ITEMS:")
    for t in re.findall(r'class="menu-link"[^>]*>(.*?)</a>', sm.group(1), re.S):
        print(" *", strip(t))
    Path("scripts/_debug_first_submenu.html").write_text(sm.group(0)[:4000], encoding="utf-8")

# Extract wp-custom-css and check for conflicting older submenu rules
css_m = re.search(r'<style id="wp-custom-css">(.*?)</style>', html, re.S)
css = css_m.group(1) if css_m else ""
print("custom_css_len", len(css))
print("inset_count", css.count("inset -3px"))
print("border-right: 4px in custom (any)", len(re.findall(r"border-right:\s*4px", css)))
# submenu-related border-right 4px near menu
for m in re.finditer(r".{0,80}sub-menu.{0,200}", css):
    s = re.sub(r"\s+", " ", m.group(0))
    if "border-right" in s or "background" in s or "#046" in s or "primary" in s:
        if "main-header" in s or "sub-menu" in s:
            print("CTX", s[:280])

# Astra inline after custom?
pos_custom = html.find('id="wp-custom-css"')
pos_astra = html.find("astra-theme-css-inline-css")
print("order: astra_inline", pos_astra, "custom", pos_custom, "custom_after_astra", pos_custom > pos_astra)

# External stylesheets after custom css?
after = html[pos_custom:]
for href in re.findall(r'<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"', after):
    print("STYLESHEET_AFTER_CUSTOM", href)

# Check if submenu links color could come from astra color-1 on hover of parent
print("ast-global-0", re.search(r"--ast-global-color-0:([^;]+);", html).group(1))
