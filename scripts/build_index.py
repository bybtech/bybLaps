#!/usr/bin/env python3
import json, sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LAPS = REPO / "laps"

# Cap the per-entry preview route so index.json stays small even with many laps
# (the .bybLap's own gpsRoutePreview is <=300 pts; a thumbnail needs far fewer).
MAX_PREVIEW_ROUTE_PTS = 48


def name(slug):
    return " ".join(w[:1].upper() + w[1:] for w in slug.replace("_", "-").split("-") if w)


def _r6(v):
    return round(float(v), 6)


def _coord(c):
    return {"lat": _r6(c["lat"]), "lon": _r6(c["lon"])}


def preview(d):
    """A lightweight thumbnail payload the app can draw WITHOUT downloading the
    .bybLap: the gate lines (always) + a downsampled GPS route (only when the
    file embeds one). Shape matches the app's LapMiniature geometry
    ({gates:[{type,p1,p2}], route:[[lat,lon],...]}); the entry's own `centroid`
    completes it."""
    gates = []
    for g in (d.get("gates") or []):
        p1, p2 = g.get("lineP1"), g.get("lineP2")
        if not (isinstance(p1, dict) and isinstance(p2, dict)):
            continue
        if "lat" not in p1 or "lon" not in p1 or "lat" not in p2 or "lon" not in p2:
            continue
        gates.append({"type": g.get("type", ""), "p1": _coord(p1), "p2": _coord(p2)})

    out = {"gates": gates}

    rp = d.get("gpsRoutePreview")
    coords = rp.get("coords") if isinstance(rp, dict) else None
    if isinstance(coords, list) and len(coords) >= 2:
        n = len(coords)
        stride = max(1, (n + MAX_PREVIEW_ROUTE_PTS - 1) // MAX_PREVIEW_ROUTE_PTS)
        route = [[_r6(c[0]), _r6(c[1])]
                 for c in coords[::stride]
                 if isinstance(c, list) and len(c) >= 2]
        last = coords[-1]
        if isinstance(last, list) and len(last) >= 2:
            ll = [_r6(last[0]), _r6(last[1])]
            if not route or route[-1] != ll:
                route.append(ll)      # never clip the track end
        if route:
            out["route"] = route

    return out


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
        "preview": preview(d),
    }


files = sorted(p for p in LAPS.rglob("*") if p.is_file() and p.suffix.lower() == ".byblap") if LAPS.exists() else []
splits, bad = [], []
for p in files:
    try:
        splits.append(entry(p))
    except (json.JSONDecodeError, OSError, ValueError, KeyError, TypeError) as e:
        bad.append(f"{p.relative_to(REPO).as_posix()}: {e}")

if bad:
    sys.exit("malformed .bybLap:\n" + "\n".join(bad))

splits.sort(key=lambda e: (e["venue"].lower(), e["name"].lower()))
(REPO / "index.json").write_text(
    json.dumps({"schemaVersion": 2,
                "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "splits": splits}, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8")
print(f"wrote {len(splits)} split(s)")
