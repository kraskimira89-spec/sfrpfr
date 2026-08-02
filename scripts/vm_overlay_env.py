from pathlib import Path
overlay = {}
for line in Path("/tmp/supabase-staging.env").read_text().splitlines():
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    overlay[k] = v
p = Path("/opt/sfrfr-supabase/supabase/docker/.env")
p.parent.mkdir(parents=True, exist_ok=True)
ex = Path("/opt/sfrfr-supabase/supabase/docker/.env.example")
if not p.exists() and ex.exists():
    p.write_text(ex.read_text())
elif not p.exists():
    p.write_text("")
lines = []
seen = set()
for ln in p.read_text().splitlines():
    if "=" in ln and not ln.strip().startswith("#"):
        k = ln.split("=", 1)[0]
        if k in overlay:
            lines.append(f"{k}={overlay[k]}")
            seen.add(k)
            continue
    lines.append(ln)
for k, v in overlay.items():
    if k not in seen:
        lines.append(f"{k}={v}")
p.write_text("\n".join(lines) + "\n")
print("overlay_ok", len(overlay))
