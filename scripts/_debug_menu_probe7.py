import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
html = Path(r"C:/Users/user/AppData/Local/Temp/sfrfr-home2.html").read_text(encoding="utf-8")
css = re.search(r'<style id="wp-custom-css">(.*?)</style>', html, re.S).group(1)
i = css.find("Выпадающие меню")
print(css[i : i + 2000])
print("---")
# stylesheets after custom
pos = html.find('id="wp-custom-css"')
after = html[pos : pos + 5000]
print("AFTER_CUSTOM_HEAD", after[:500])
for href in re.findall(r'href="([^"]+\.css[^"]*)"', html[pos:]):
    print("CSS_AFTER", href)
