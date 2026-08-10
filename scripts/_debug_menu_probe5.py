import re
import sys
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
url = "https://proverkastaza.ru/?nocache=dbg016b5f"
req = urllib.request.Request(
    url,
    headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    },
)
html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
Path(r"C:/Users/user/AppData/Local/Temp/sfrfr-home2.html").write_text(html, encoding="utf-8")
print("len", len(html))
for s in [
    "Кому полезна",
    "Перед пенсией",
    "Все статьи",
    "Лопакова",
    "class=\"sub-menu\"",
    "class='sub-menu'",
    "children sub-menu",
    "Услуги",
    ">Главная<",
]:
    print(repr(s), html.count(s))

m = re.search(r'id="ast-hf-menu-1"[^>]*>(.*?)</ul>', html, re.S)
if m:
    print("DESKTOP_ITEMS", re.findall(r'class="menu-link">([^<]+)', m.group(1)))
    print("DESKTOP_SUB", "sub-menu" in m.group(1))
    print("DESKTOP_LEN", len(m.group(1)))

# all ul with submenu-ish
for m in re.finditer(r"<ul([^>]*)>", html):
    attrs = m.group(1)
    if "sub" in attrs or "children" in attrs:
        print("UL", attrs[:200])
        chunk = html[m.end() : m.end() + 300]
        print(" ", re.sub(r"\s+", " ", chunk)[:200])
