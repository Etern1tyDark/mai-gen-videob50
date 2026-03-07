import json
from pathlib import Path

root = Path(r"C:\Data\games\RGs\maimai\mai-gen-videob50-release_v06_5_bugfix\mai-gen-videob50-release_v06_5_bugfix")

config_path = root / "b50_datas" / "Eter" / "20260126_181704" / "b50_config.json"
raw_path = root / "b50_datas" / "Eter" / "20260126_181704" / "b50_raw.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")


def clear_dxscore(record):
    if isinstance(record, dict) and "dxScore" in record:
        record["dxScore"] = 0
        return 1
    return 0


config = load_json(config_path)
raw = load_json(raw_path)

changed = 0
for rec in config.get("records", []):
    changed += clear_dxscore(rec)

for rec in raw.get("charts", {}).get("dx", []):
    changed += clear_dxscore(rec)

for rec in raw.get("charts", {}).get("sd", []):
    changed += clear_dxscore(rec)

save_json(config_path, config)
save_json(raw_path, raw)

print(f"Cleared dxScore in {changed} records")
