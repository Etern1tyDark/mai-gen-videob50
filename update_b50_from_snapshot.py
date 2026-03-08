import json
import unicodedata
from pathlib import Path

DEFAULT_ROOT = Path(r"C:\Data\games\RGs\maimai\mai-gen-videob50-release_v06_5_bugfix\mai-gen-videob50-release_v06_5_bugfix")
root = DEFAULT_ROOT if DEFAULT_ROOT.exists() else Path(__file__).resolve().parent

snapshot_path = root / "snapshot-x-mzJm4kcKGWVagF5wY9N.json"
config_path = root / "b50_datas" / "Twi" / "20260307_205627" / "b50_config.json"
raw_path = root / "b50_datas" / "Twi" / "20260307_205627" / "b50_raw.json"

snapshot = json.loads(snapshot_path.read_text(encoding="utf-8-sig"))
config = json.loads(config_path.read_text(encoding="utf-8-sig"))
raw = json.loads(raw_path.read_text(encoding="utf-8-sig"))

FC_MAP = {
    "": "",
    "none": "",
    "fc": "fc",
    "fc+": "fcp",
    "fcp": "fcp",
    "ap": "ap",
    "ap+": "app",
    "app": "app",
}

FS_MAP = {
    "": "",
    "none": "",
    "sync": "sync",
    "fs": "fs",
    "fs+": "fsp",
    "fsp": "fsp",
    "fdx": "fsd",
    "fsd": "fsd",
    "fdx+": "fsdp",
    "fsd+": "fsdp",
    "fsdp": "fsdp",
}


def normalize_type(value: str) -> str:
    v = (value or "").strip().lower()
    if v == "dx":
        return "dx"
    if v in {"sd", "std"}:
        return "std"
    return v


def normalize_diff(value: str) -> str:
    return (value or "").strip().lower()


def normalize_level(value: str) -> str:
    return (value or "").strip()


def normalize_fc(value: str) -> str:
    return FC_MAP.get((value or "").strip().lower(), "")


def normalize_fs(value: str) -> str:
    return FS_MAP.get((value or "").strip().lower(), "")


def normalize_title(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u3000", " ")
    text = " ".join(text.split())
    return text


def parse_achievement(raw_value) -> float:
    try:
        val = float(raw_value)
    except (TypeError, ValueError):
        return 0.0
    if val >= 1000:
        return val / 10000
    return val


def build_lookup(songs):
    full = {}
    by_title = {}
    by_title_diff = {}
    by_title_diff_type = {}
    for s in songs:
        name = normalize_title(s.get("songName"))
        if not name:
            continue
        diff = normalize_diff(s.get("difficulty"))
        typ = normalize_type(s.get("type"))
        level = normalize_level(s.get("level"))
        entry = {
            "dxScore": s.get("dxScore"),
            "fc": normalize_fc(s.get("fc")),
            "fs": normalize_fs(s.get("fs")),
            "achievement": parse_achievement(s.get("achievement")),
            "levelPrecise": s.get("levelPrecise"),
            "rating": s.get("rating"),
        }
        full_key = (name, diff, typ, level)
        full[full_key] = entry
        by_title.setdefault(name, []).append(entry)
        by_title_diff.setdefault((name, diff), []).append(entry)
        by_title_diff_type.setdefault((name, diff, typ), []).append(entry)
    return full, by_title, by_title_diff, by_title_diff_type


def pick_best(entries):
    if not entries:
        return None
    if len(entries) == 1:
        return entries[0]
    return max(entries, key=lambda e: e.get("achievement", 0.0))


def get_entry(name, diff, typ, level, full, by_title, by_title_diff, by_title_diff_type):
    full_key = (name, diff, typ, level)
    if full_key in full:
        return full[full_key]
    entries = by_title_diff_type.get((name, diff, typ), [])
    if entries:
        return pick_best(entries)
    entries = by_title_diff.get((name, diff), [])
    if entries:
        return pick_best(entries)
    entries = by_title.get(name, [])
    return pick_best(entries)


def update_record(rec, full, by_title, by_title_diff, by_title_diff_type):
    name = normalize_title(rec.get("title"))
    if not name:
        return False
    diff = normalize_diff(rec.get("level_label"))
    typ = normalize_type(rec.get("type"))
    level = normalize_level(rec.get("level"))
    entry = get_entry(name, diff, typ, level, full, by_title, by_title_diff, by_title_diff_type)
    if not entry:
        return False

    changed = False
    if rec.get("dxScore", 0) in (0, None) and entry.get("dxScore") not in (None, 0):
        rec["dxScore"] = int(entry["dxScore"])
        changed = True
    if not (rec.get("fc") or "").strip() and entry.get("fc"):
        rec["fc"] = entry["fc"]
        changed = True
    if not (rec.get("fs") or "").strip() and entry.get("fs"):
        rec["fs"] = entry["fs"]
        changed = True
    level_precise = entry.get("levelPrecise")
    if level_precise is not None:
        try:
            ds = float(level_precise) / 10.0
        except (TypeError, ValueError):
            ds = None
        if ds is not None and rec.get("ds") != ds:
            rec["ds"] = ds
            changed = True
    rating = entry.get("rating")
    if rating is not None:
        try:
            ra = int(rating)
        except (TypeError, ValueError):
            ra = None
        if ra is not None and rec.get("ra") != ra:
            rec["ra"] = ra
            changed = True
    return changed


full, by_title, by_title_diff, by_title_diff_type = build_lookup(snapshot.get("songs", []))

changed = 0
for rec in config.get("records", []):
    if update_record(rec, full, by_title, by_title_diff, by_title_diff_type):
        changed += 1

for rec in raw.get("charts", {}).get("dx", []):
    if update_record(rec, full, by_title, by_title_diff, by_title_diff_type):
        changed += 1

for rec in raw.get("charts", {}).get("sd", []):
    if update_record(rec, full, by_title, by_title_diff, by_title_diff_type):
        changed += 1

snapshot_rating = snapshot.get("rating")
if snapshot_rating is None and isinstance(snapshot.get("metadata"), dict):
    snapshot_rating = snapshot["metadata"].get("rating")
if snapshot_rating is not None:
    try:
        rating_value = int(snapshot_rating)
    except (TypeError, ValueError):
        rating_value = None
    if rating_value is not None:
        config["rating"] = rating_value
        raw["rating"] = rating_value

config_path.write_text(json.dumps(config, ensure_ascii=False, indent=4), encoding="utf-8")
raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=4), encoding="utf-8")

print(f"Updated records: {changed}")
