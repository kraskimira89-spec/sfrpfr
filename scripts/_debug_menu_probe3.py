import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
html = Path(r"C:/Users/user/AppData/Local/Temp/sfrfr-home.html").read_text(
    encoding="utf-8", errors="replace"
)

# Dump all occurrences of menu-item-has-children with context
for i, m in enumerate(re.finditer(r"menu-item-has-children", html)):
    ctx = html[max(0, m.start() - 100) : m.start() + 500]
    text = re.sub(r"\s+", " ", ctx)
    print(f"==== has-children[{i}] ====")
    print(text[:700])
    print()

print("count has-children", len(re.findall("menu-item-has-children", html)))
print("count sub-menu", len(re.findall(r'class="sub-menu"', html)))

# Find text Главная around
idx = html.find("Главная")
print("glavnaya_idx", idx)
if idx >= 0:
    print(re.sub(r"\s+", " ", html[idx - 200 : idx + 400]))

# Save nav-ish region around first Главная
if idx >= 0:
    Path("scripts/_debug_nav_chunk.html").write_text(
        html[max(0, idx - 1500) : idx + 8000], encoding="utf-8"
    )
    print("wrote scripts/_debug_nav_chunk.html")

# Look for astra menu color link rules
for sel, body in re.findall(
    r"([^{}]*ast-builder-menu-1[^{}]*)\{([^}]*)\}", html
):
    if any(k in body for k in ("color:", "background")):
        print("ASTRA", re.sub(r"\s+", " ", sel.strip())[:200])
        print(" ", re.sub(r"\s+", " ", body.strip())[:250])
