#!/usr/bin/env python3
import json, sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LAPS = REPO / "laps"


def name(slug):
    return " ".join(w[:1].upper() + w[1:] for w in slug.replace("_", "-").split("-") if w)


def entry(p):
    d = json.loads(p.read_text(encoding="utf-8"))
    c = d.get("centroid")
    rel = p.relative_to(LAPS)
    return {
        "id": rel.with_suffix("").as_posix(),
        "name": name(p.stem),
        "venue": "" if p.parent == LAPS else name(p.parent.name),
        "path": p.relative_to(REPO).as_posix(),
        "centroid": c if isinstance(c, dict) and "lat" in c and "lon" in c else None,
        "isClosedLap": bool(d.get("isClosedLap", False)),
        "splitCount": sum(1 for g in (d.get("gates") or []) if g.get("type") == "split"),
        "savedAt": d.get("savedAt", ""),
        "sizeBytes": p.stat().st_size,
    }


files = sorted(p for p in LAPS.rglob("*") if p.is_file() and p.suffix.lower() == ".byblap") if LAPS.exists() else []
splits, bad = [], []
for p in files:
    try:
        splits.append(entry(p))
    except (json.JSONDecodeError, OSError, ValueError) as e:
        bad.append(f"{p.relative_to(REPO).as_posix()}: {e}")

if bad:
    sys.exit("malformed .bybLap:\n" + "\n".join(bad))

splits.sort(key=lambda e: (e["venue"].lower(), e["name"].lower()))
(REPO / "index.json").write_text(
    json.dumps({"schemaVersion": 1,
                "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "splits": splits}, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8")
print(f"wrote {len(splits)} split(s)")
