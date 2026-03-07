import json
from pathlib import Path

root = Path(r"C:\Data\games\RGs\maimai\mai-gen-videob50-release_v06_5_bugfix\mai-gen-videob50-release_v06_5_bugfix")
old_path = root / "b50_datas" / "Eter" / "20251009_114716" / "video_configs.json"
new_path = root / "b50_datas" / "Eter" / "20260126_181704" / "video_configs.json"

old_cfg = json.loads(old_path.read_text(encoding="utf-8-sig"))
new_cfg = json.loads(new_path.read_text(encoding="utf-8-sig"))

fields = ["duration", "start", "end", "text"]

old_map = {}
for item in old_cfg.get("main", []):
    title = (item.get("achievement_title") or "").strip()
    if title and title not in old_map:
        old_map[title] = {k: item.get(k) for k in fields}

updated = 0
for item in new_cfg.get("main", []):
    title = (item.get("achievement_title") or "").strip()
    if not title:
        continue
    if title in old_map:
        src = old_map[title]
        for k in fields:
            if k in src:
                item[k] = src[k]
        updated += 1

new_path.write_text(json.dumps(new_cfg, ensure_ascii=False, indent=4), encoding="utf-8")
print(f"Updated {updated} items")
