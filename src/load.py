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


def validate(categories, stages, total_roles, sources, events, lines):
    errors, warnings = [], []
    cat_codes = {c["code"] for c in categories}
    stage_codes = {s["code"] for s in stages}
    role_codes = {r["code"] for r in total_roles}
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
        if l["category"] == "total" and l["total_role"] not in role_codes:
            errors.append(f"{lid}: total line needs a total_role from total_roles.csv")
        if l["category"] != "total" and l["total_role"]:
            errors.append(f"{lid}: total_role is only for total lines")
        if l["source_id"] not in source_ids:
            errors.append(f"{lid}: source_id '{l['source_id']}' not in sources")
        if l["precision"] not in PRECISIONS:
            errors.append(f"{lid}: precision '{l['precision']}' invalid")
        if l["verified"] not in {"yes", "no"}:
            errors.append(f"{lid}: verified must be yes or no")
        try:
            # Credits within a breakdown (e.g. external billings) may be negative; totals may not.
            if float(l["amount_usd"]) < 0 and (l["category"] == "total" or "credit" not in l["notes"].lower()):
                errors.append(f"{lid}: negative amount (only allowed on a component line noted as a credit)")
        except ValueError:
            errors.append(f"{lid}: amount_usd '{l['amount_usd']}' is not a number")

    # Category breakdowns must add up to the stated gross total for the same event, stage and source.
    # Where a filing gives separate gross totals (e.g. distribution and transmission), they are summed.
    groups = defaultdict(lambda: {"parts": 0.0, "n": 0, "total": None})
    for l in lines:
        try:
            amt = float(l["amount_usd"])
        except ValueError:
            continue
        g = groups[(l["event_id"], l["stage"], l["source_id"])]
        if l["category"] == "total":
            if l["total_role"] == "gross_total":
                g["total"] = (g["total"] or 0) + amt
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


def validate_storm_response(rows, events, sources):
    """Storm response facts (pre-staging, crews, trouble spots): one optional row per event."""
    errors = []
    event_ids = {e["event_id"] for e in events}
    source_ids = {s["source_id"] for s in sources}
    seen = set()
    for r in rows:
        ev = r["event_id"]
        if ev in seen:
            errors.append(f"storm_response: duplicate event_id {ev}")
        seen.add(ev)
        if ev not in event_ids:
            errors.append(f"storm_response: event_id '{ev}' not in events")
        if r["source_id"] not in source_ids:
            errors.append(f"storm_response {ev}: source_id '{r['source_id']}' not in sources")
        if r["prestage_notice"] not in {"yes", "no"} or (r["prestage_notice"] == "yes") != bool(r["prestage_notice_date"]):
            errors.append(f"storm_response {ev}: prestage_notice must be yes with a date, or no without one")
        if r["filing_says_underperformed"] not in {"yes", ""}:
            errors.append(f"storm_response {ev}: filing_says_underperformed must be yes or blank")
        if r["verified"] not in {"yes", "no"}:
            errors.append(f"storm_response {ev}: verified must be yes or no")
        for k in ("erp_level_initial", "erp_level_highest", "outage_events", "non_outage_events", "customers_affected", "line_resources", "cost_per_event_usd"):
            if r[k] and not r[k].isdigit():
                errors.append(f"storm_response {ev}: {k} '{r[k]}' is not a whole number")
    return errors


def build(categories, stages, total_roles, sources, events, lines, storm_response):
    # Build in a local temp folder, then copy: SQLite can fail on synced or mounted folders.
    DB.parent.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp()) / DB.name
    con = sqlite3.connect(tmp)
    for name, rows in (("categories", categories), ("stages", stages), ("total_roles", total_roles), ("sources", sources), ("events", events), ("cost_lines", lines), ("storm_response", storm_response)):
        cols = list(rows[0].keys())
        con.execute(f"CREATE TABLE {name} ({', '.join(cols)})")
        con.executemany(f"INSERT INTO {name} VALUES ({', '.join('?' for _ in cols)})", [[r[c] if r[c] != "" else None for c in cols] for r in rows])
    con.execute("""
        CREATE VIEW cost_lines_full AS
        SELECT l.*, CAST(l.amount_usd AS REAL) AS amount, c.bucket,
               e.utility, e.state, e.ownership, e.storm_name, e.storm_type, CAST(e.storm_year AS INTEGER) AS storm_year,
               CAST(e.customers_affected AS REAL) AS customers_affected, e.customers_measure, e.customers_precision,
               s.publisher, s.title AS source_title, s.url AS source_url
        FROM cost_lines l
        JOIN events e USING (event_id)
        JOIN sources s USING (source_id)
        LEFT JOIN categories c ON c.code = l.category
    """)
    con.commit()
    con.close()
    shutil.copyfile(tmp, DB)


def main():
    tables = [read(n) for n in ("categories.csv", "stages.csv", "total_roles.csv", "sources.csv", "events.csv", "cost_lines.csv")]
    storm_response = read("storm_response.csv")
    errors, warnings = validate(*tables)
    errors += validate_storm_response(storm_response, tables[4], tables[3])
    for w in warnings:
        print(f"warning: {w}")
    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        print(f"\n{len(errors)} error(s). Database not built.")
        sys.exit(1)
    build(*tables, storm_response)
    print(f"Built {DB.relative_to(ROOT)}: {len(tables[3])} sources, {len(tables[4])} events, {len(tables[5])} cost lines.")


if __name__ == "__main__":
    main()
