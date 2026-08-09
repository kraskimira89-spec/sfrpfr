# -*- coding: utf-8 -*-
from pathlib import Path
import json
import re
import subprocess

subprocess.check_call(["python", "scripts/build_awards_gallery.py"])
home = Path("scripts/assets/sfrfr-home.html")
text = home.read_text(encoding="utf-8")
data = Path("scripts/assets/awards/home-data.json").read_text(encoding="utf-8").strip()
assert "белозерцева 2" not in data.lower()
items = json.loads(data)
print("items", len(items))
pat = re.compile(
    r'(<script type="application/json" id="sfrfr-awards-data">)(\[.*?\])(</script>)',
    re.S,
)
new_text, n = pat.subn(rf"\g<1>{data}\g<3>", text, count=1)
assert n == 1
home.write_text(new_text, encoding="utf-8")
print("home patched")
