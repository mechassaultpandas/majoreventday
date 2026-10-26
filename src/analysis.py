"""First-pass analysis of the storm cost database.

Writes outputs/analysis.md (readable summary) and outputs/analysis.xlsx (tables).
Run src/load.py first. Every figure here is unverified until the cost lines are marked verified.
"""
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "outputs" / "storm_costs.db"
OUT_MD = ROOT / "outputs" / "analysis.md"
OUT_XLSX = ROOT / "outputs" / "analysis.xlsx"

BREAKDOWN_STAGES = ("final_approved", "reported_actual")


def q(con, sql):
    return pd.read_sql_query(sql, con)


def category_mix(con):
    """Share of each cost category, for events with a full breakdown at a final stage."""
    df = q(con, f"""
        SELECT event_id, utility, storm_name, storm_year, stage, category, amount
        FROM cost_lines_full
        WHERE stage IN {BREAKDOWN_STAGES} AND category != 'total'
    """)
    if df.empty:
        return df
    totals = df.groupby("event_id")["amount"].transform("sum")
    df["share"] = df["amount"] / totals
    mix = df.pivot_table(index=["event_id", "utility", "storm_name", "storm_year"], columns="category", values="share").reset_index()
    mix["total_usd_m"] = df.groupby("event_id")["amount"].sum().reindex(mix["event_id"]).values / 1e6
    return mix


def estimate_vs_final(con):
    """Petition estimate against final approved total, where both exist."""
    df = q(con, """
        SELECT event_id, utility, storm_name, stage, amount
        FROM cost_lines_full
        WHERE category = 'total' AND stage IN ('petition_estimate', 'final_approved')
    """)
    if df.empty:
        return df
    wide = df.pivot_table(index=["event_id", "utility", "storm_name"], columns="stage", values="amount").dropna().reset_index()
    wide["change_pct"] = (wide["final_approved"] - wide["petition_estimate"]) / wide["petition_estimate"]
    for c in ("petition_estimate", "final_approved"):
        wide[c] = wide[c] / 1e6
    return wide.rename(columns={"petition_estimate": "estimate_usd_m", "final_approved": "final_usd_m"})


def category_estimate_vs_final(con):
    """Category-level estimate vs final for events with both breakdowns."""
    df = q(con, """
        SELECT event_id, utility, storm_name, category, stage, amount
        FROM cost_lines_full
        WHERE category != 'total' AND stage IN ('petition_estimate', 'final_approved')
    """)
    if df.empty:
        return df
    wide = df.pivot_table(index=["event_id", "utility", "storm_name", "category"], columns="stage", values="amount").dropna().reset_index()
    wide["change_pct"] = (wide["final_approved"] - wide["petition_estimate"]) / wide["petition_estimate"]
    return wide


def cost_per_customer(con):
    """Total cost per customer, only within the same customer measure. Never mix measures."""
    df = q(con, f"""
        SELECT event_id, utility, storm_name, storm_year, customers_affected, customers_measure, customers_precision, amount AS total_usd
        FROM cost_lines_full
        WHERE category = 'total' AND stage IN {BREAKDOWN_STAGES} AND customers_affected IS NOT NULL
    """)
    if df.empty:
        return df
    df["usd_per_customer"] = df["total_usd"] / df["customers_affected"]
    df["caveat"] = df["customers_precision"].map({
        "lower_bound": "customer count is a lower bound, so this is an upper bound",
        "approximate": "approximate customer count",
        "exact": "",
    })
    df["comparable_with_other_years"] = df["storm_year"].apply(lambda y: "nominal dollars; adjust for inflation before comparing" if y < 2020 else "")
    return df.sort_values(["customers_measure", "usd_per_customer"])


def coverage(con):
    return q(con, """
        SELECT e.state, COUNT(DISTINCT e.event_id) AS events,
               COUNT(l.line_id) AS cost_lines,
               SUM(CASE WHEN l.verified = 'yes' THEN 1 ELSE 0 END) AS verified_lines
        FROM events e LEFT JOIN cost_lines l USING (event_id)
        GROUP BY e.state ORDER BY events DESC
    """)


def pct(x):
    return "n/r" if pd.isna(x) else f"{x:.1%}"


def main():
    con = sqlite3.connect(f"file:{DB}?immutable=1", uri=True)  # read-only; safe on synced folders
    mix, est, cat_est, cpc, cov = category_mix(con), estimate_vs_final(con), category_estimate_vs_final(con), cost_per_customer(con), coverage(con)
    con.close()

    lines = ["# Storm cost analysis", "", "All figures are unverified until cost lines are checked against source pages.", ""]

    lines += ["## Category mix (events with a full breakdown)", "", "n/r = not reported separately in the filing (often folded into another category).", ""]
    if not mix.empty:
        show = ["contractors", "line_clearing", "logistics", "payroll_regular", "payroll_overtime", "payroll", "materials", "vehicles_fuel", "other"]
        show = [c for c in show if c in mix.columns]
        lines.append("| Event | Total ($M) | " + " | ".join(show) + " |")
        lines.append("| --- | --- | " + " | ".join("---" for _ in show) + " |")
        for _, r in mix.iterrows():
            lines.append(f"| {r.utility}, {r.storm_name} ({r.storm_year}) | {r.total_usd_m:,.1f} | " + " | ".join(pct(r[c]) for c in show) + " |")
        lines.append("")

    lines += ["## Petition estimate vs final approved", ""]
    if not est.empty:
        lines += ["| Event | Estimate ($M) | Final ($M) | Change |", "| --- | --- | --- | --- |"]
        for _, r in est.iterrows():
            lines.append(f"| {r.utility}, {r.storm_name} | {r.estimate_usd_m:,.1f} | {r.final_usd_m:,.1f} | {r.change_pct:+.1%} |")
        lines.append("")
    if not cat_est.empty:
        lines += ["Category detail where both stages exist:", "", "| Event | Category | Change |", "| --- | --- | --- |"]
        for _, r in cat_est.sort_values("change_pct").iterrows():
            lines.append(f"| {r.storm_name} | {r.category} | {r.change_pct:+.1%} |")
        lines.append("")

    lines += ["## Cost per customer (within the same customer measure only)", ""]
    if not cpc.empty:
        lines += ["| Event | Measure | Customers | $ per customer | Caveat |", "| --- | --- | --- | --- | --- |"]
        for _, r in cpc.iterrows():
            cav = "; ".join(c for c in (r.caveat, r.comparable_with_other_years) if c)
            lines.append(f"| {r.utility}, {r.storm_name} | {r.customers_measure} | {r.customers_affected:,.0f} | {r.usd_per_customer:,.0f} | {cav} |")
        lines.append("")

    lines += ["## Coverage", "", "| State | Events | Cost lines | Verified |", "| --- | --- | --- | --- |"]
    for _, r in cov.iterrows():
        lines.append(f"| {r.state} | {r.events} | {r.cost_lines} | {r.verified_lines} |")

    OUT_MD.write_text("\n".join(lines) + "\n")
    with pd.ExcelWriter(OUT_XLSX) as xw:
        for name, df in (("category_mix", mix), ("estimate_vs_final", est), ("category_est_vs_final", cat_est), ("cost_per_customer", cpc), ("coverage", cov)):
            df.to_excel(xw, sheet_name=name, index=False)
    print(f"Wrote {OUT_MD.relative_to(ROOT)} and {OUT_XLSX.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
