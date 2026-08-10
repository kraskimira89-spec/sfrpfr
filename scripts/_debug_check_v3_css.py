import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
req = urllib.request.Request(
    "https://proverkastaza.ru/?nocache=v3e",
    headers={"User-Agent": "Mozilla/5.0"},
)
html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
css = re.search(r'<style id="wp-custom-css">(.*?)</style>', html, re.S).group(1)
i = css.find("sfrfr-nav-dropdown-v3")
print("v3 idx", i)
print(css[i : i + 1400])
print("f3f7f4 count", css.count("#f3f7f4"))
