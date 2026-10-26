"""Validate the CSVs in data/ and build outputs/storm_costs.db.

Errors stop the build. Warnings are printed but do not stop it.
Run from the repository root: python3 src/load.py
"""
import csv
import shutil
import sqlite3
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB = ROOT / "outputs" / "storm_costs.db"

# A category breakdown may differ from its stated total by rounding in the filing.
TOTAL_TOLERANCE = 0.001  # 0.1%

PRECISIONS = {"exact", "approximate", "lower_bound", "upper_bound"}
OWNERSHIP = {"IOU", "municipal", "cooperative", "federal", "other"}
CUSTOMER_MEASURES = {"peak_out", "total_affected", "service_points_interrupted"}


def read(name):
    with open(DATA / name, newline="") as f:
        return list(csv.DictReader(f))


def validate(categories, stages, sources, events, lines):
    errors, warnings = [], []
    cat_codes = {c["code"] for c in categories}
    stage_codes = {s["code"] for s in stages}
    source_ids = {s["source_id"] for s in sources}
    event_ids = {e["event_id"] for e in events}

    for table, key, rows in (("sources", "source_id", sources), ("events", "event_id", events), ("cost_lines", "line_id", lines)):
        seen = set()
        for r in rows:
            if r[key] in seen:
                errors.append(f"{table}: duplicate {key} {r[key]}")
            seen.add(r[key])

    for s in sources:
        if not s["url"]:
            warnings.append(f"{s['source_id']}: no URL")
        if not s["date"]:
            warnings.append(f"{s['source_id']}: no date")

    for e in events:
        if e["ownership"] not in OWNERSHIP:
            errors.append(f"{e['event_id']}: unknown ownership '{e['ownership']}'")
        if e["customers_affected"]:
            if e["customers_measure"] not in CUSTOMER_MEASURES:
                errors.append(f"{e['event_id']}: customers_affected needs a valid customers_measure")
            if e["customers_source_id"] not in source_ids:
                errors.append(f"{e['event_id']}: customers_source_id '{e['customers_source_id']}' not in sources")
            if e["customers_precision"] not in PRECISIONS:
                errors.append(f"{e['event_id']}: customers_precision must be one of {sorted(PRECISIONS)}")

    for l in lines:
        lid = l["line_id"]
        if l["event_id"] not in event_ids:
            errors.append(f"{lid}: event_id '{l['event_id']}' not in events")
        if l["category"] not in cat_codes:
            errors.append(f"{lid}: category '{l['category']}' not in categories")
        if l["stage"] not in stage_codes:
            errors.append(f"{lid}: stage '{l['stage']}' not in stages")
        if l["source_id"] not in source_ids:
            errors.append(f"{lid}: source_id '{l['source_id']}' not in sources")
        if l["precision"] not in PRECISIONS:
            errors.append(f"{lid}: precision '{l['precision']}' invalid")
        if l["verified"] not in {"yes", "no"}:
            errors.append(f"{lid}: verified must be yes or no")
        try:
            if float(l["amount_usd"]) < 0:
                errors.append(f"{lid}: negative amount")
        except ValueError:
            errors.append(f"{lid}: amount_usd '{l['amount_usd']}' is not a number")

    # Category breakdowns must add up to the stated total for the same event, stage and source.
    groups = defaultdict(lambda: {"parts": 0.0, "n": 0, "total": None})
    for l in lines:
        try:
            amt = float(l["amount_usd"])
        except ValueError:
            continue
        g = groups[(l["event_id"], l["stage"], l["source_id"])]
        if l["category"] == "total":
            g["total"] = amt
        else:
            g["parts"] += amt
            g["n"] += 1
    for (ev, stage, src), g in groups.items():
        if g["total"] and g["n"]:
            gap = abs(g["parts"] - g["total"]) / g["total"]
            if gap > TOTAL_TOLERANCE:
                errors.append(f"{ev} {stage} {src}: categories sum to {g['parts']:,.0f} but total is {g['total']:,.0f} ({gap:.2%} apart)")

    unverified = sum(1 for l in lines if l["verified"] != "yes")
    if unverified:
        warnings.append(f"{unverified} of {len(lines)} cost lines are not yet verified against the source page")
    no_page = sum(1 for l in lines if not l["page"])
    if no_page:
        warnings.append(f"{no_page} cost lines have no page number")
    return errors, warnings


def build(categories, stages, sources, events, lines):
    # Build in a local temp folder, then copy: SQLite can fail on synced or mounted folders.
    DB.parent.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp()) / DB.name
    con = sqlite3.connect(tmp)
    for name, rows in (("categories", categories), ("stages", stages), ("sources", sources), ("events", events), ("cost_lines", lines)):
        cols = list(rows[0].keys())
        con.execute(f"CREATE TABLE {name} ({', '.join(cols)})")
        con.executemany(f"INSERT INTO {name} VALUES ({', '.join('?' for _ in cols)})", [[r[c] if r[c] != "" else None for c in cols] for r in rows])
    con.execute("""
        CREATE VIEW cost_lines_full AS
        SELECT l.*, CAST(l.amount_usd AS REAL) AS amount,
               e.utility, e.state, e.ownership, e.storm_name, e.storm_type, CAST(e.storm_year AS INTEGER) AS storm_year,
               CAST(e.customers_affected AS REAL) AS customers_affected, e.customers_measure, e.customers_precision,
               s.publisher, s.title AS source_title, s.url AS source_url
        FROM cost_lines l
        JOIN events e USING (event_id)
        JOIN sources s USING (source_id)
    """)
    con.commit()
    con.close()
    shutil.copyfile(tmp, DB)


def main():
    tables = [read(n) for n in ("categories.csv", "stages.csv", "sources.csv", "events.csv", "cost_lines.csv")]
    errors, warnings = validate(*tables)
    for w in warnings:
        print(f"warning: {w}")
    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        print(f"\n{len(errors)} error(s). Database not built.")
        sys.exit(1)
    build(*tables)
    print(f"Built {DB.relative_to(ROOT)}: {len(tables[2])} sources, {len(tables[3])} events, {len(tables[4])} cost lines.")


if __name__ == "__main__":
    main()
