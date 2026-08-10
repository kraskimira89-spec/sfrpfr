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


# Find all main-header-menu blocks
for i, m in enumerate(re.finditer(r'class="([^"]*main-header-menu[^"]*)"', html)):
    print(f"MHM[{i}]", m.group(1), "at", m.start())

# Extract site-header HTML only
hs = html.find('<header')
he = html.find("</header>")
header = html[hs:he] if hs >= 0 and he > hs else ""
print("header_len", len(header))
Path("scripts/_debug_header.html").write_text(header, encoding="utf-8")

# All anchors in header
links = re.findall(r"<a([^>]*)>(.*?)</a>", header, re.S)
print("header_links", len(links))
for aattrs, t in links:
    href = re.search(r'href="([^"]*)"', aattrs)
    cls = re.search(r'class="([^"]*)"', aattrs)
    print("-", strip(t)[:80], "|", href.group(1) if href else "", "|", (cls.group(1) if cls else "")[:60])

# Search for children ul variants
for pat in [
    r'class="sub-menu"',
    r"class='sub-menu'",
    r"sub-menu menu",
    r'class="children"',
    r"astra-full-megamenu",
    r"dropdown",
]:
    print(pat, html.count(pat), "in_header", header.count(pat))

# Is Главная only in CSS?
print("Главная count", html.count("Главная"))
print("Кому полезна", html.count("Кому полезна"))
print("Перед пенсией", html.count("Перед пенсией"))
print("Услуги count", html.count("Услуги"))
print("Статьи count", html.count("Статьи"))
