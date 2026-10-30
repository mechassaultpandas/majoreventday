# Major Event Day: storm cost dataset

A benchmark of electric utility storm restoration costs, built from public sources. Every number traces to a source document and page.

## How the data is organised

Four CSV files in `data/` are the system of record. The database in `outputs/` is rebuilt from them and is never edited by hand.

| File | One row per | Purpose |
| --- | --- | --- |
| `data/sources.csv` | Source document | Docket filings, orders, reports and articles, with URL and date |
| `data/events.csv` | Utility per storm | Who, which storm, scale of outage, regulatory status |
| `data/cost_lines.csv` | Cost figure | One amount for one category at one stage, with its source and page |
| `data/categories.csv` | Standard category | Maps each utility's own category names to the standard set, and each category to a comparison bucket |
| `data/stages.csv`, `data/total_roles.csv` | Code | Allowed values for `stage` and `total_role` |
| `data/storm_response.csv` | Utility per storm (optional) | How the utility prepared and what it faced: pre-staging notice, ERP level, line resources, trouble spots, cost per trouble spot |

Costs sit in long format (one row per figure) because every state and utility reports different categories and different stages. The `stage` field separates a petition estimate from a final approved figure, so estimate-versus-actual comparisons fall out naturally.

## Standard cost categories

| Code | Meaning |
| --- | --- |
| `payroll_regular` | Utility regular-time payroll |
| `payroll_overtime` | Utility overtime payroll |
| `contractors` | Line contractors and mutual aid utilities |
| `line_clearing` | Vegetation and line clearing contractors |
| `logistics` | Lodging, meals, staging sites, base camps |
| `materials` | Materials and supplies |
| `vehicles_fuel` | Vehicles, fleet and fuel |
| `other` | Anything else, including affiliate payroll |
| `estimate_unallocated` | Estimated costs not yet booked to a cost type (left out of shares) |
| `total` | Total restoration cost when no breakdown exists |

If a filing uses a category that does not fit cleanly, record it under its closest code and copy the filing's own wording into `category_as_filed`.

## Comparison buckets

Filers split costs differently, so each category also belongs to one of five buckets (the `bucket` column of `categories.csv`): `labor`, `contractors_incl_veg`, `materials`, `vehicles_fuel` and `logistics_other`. Compare storms across utilities at bucket level. Vegetation sits with contractors because CT and TX don't report it separately.

## Total roles

A single event often has several `total` lines: the gross cost, an approved amount, a disallowance, a deferred O&M figure. `total_role` (in `cost_lines.csv`, blank on category lines) says which is which, so they don't get added together. The codes are in `data/total_roles.csv`. For cross-storm comparisons, use `gross_total`. `load.py` checks that category lines add up to the `gross_total` for the same event, stage and source.

## Stages

`petition_estimate`, `testimony_update`, `requested`, `interim_charge_approved`, `final_approved`, `reported_actual`, `disallowed`, `non_incremental_removed`, `transferred`.

`transferred` is for costs a settlement or order moves to another proceeding (for example a later rate case). They are neither approved nor denied, so don't record them as `disallowed`.

## Storm response

`storm_response.csv` holds the operational side of a storm, one row per event, where a filing reports it. It is separate from costs so cost lines stay one figure per row.

- `prestage_notice` / `prestage_notice_date`: whether the utility formally notified the regulator that it was pre-staging crews, and when.
- `erp_level_initial` / `erp_level_highest`: the emergency response plan level declared at the start and the most severe level reached. In Eversource's plan, 5 is the least severe and 1 the most.
- `outage_events` / `non_outage_events`: trouble spots with and without customer outages. `line_resources`: line crews or line workers as the filing counts them.
- `cost_per_event_usd`: the utility's own cost per trouble spot, as filed.
- `filing_says_underperformed`: `yes` only where the filing itself says the storm or its damage fell short of the forecast. Never inferred.

So far it covers the 43 Connecticut storms in PURA Docket 25-12-13 (S013, Appendix C).

## Verification

Every cost line has a `verified` flag. Set it to `yes` only after a person has checked the figure against the source page. Lines extracted by Claude start as `no`. Nothing unverified should be published.

## Running it

```
python3 src/load.py      # validates the CSVs and builds outputs/storm_costs.db
python3 src/analysis.py  # writes outputs/analysis.md and outputs/analysis.xlsx
```

`load.py` stops with a list of problems if any row breaks the rules: unknown source, unknown category, category totals that do not match a stated total, and so on.

## Adding a storm

1. Save the PDF in `sources/pdfs/` named `<state>_<docket>_<document>.pdf`, and add a row to `sources.csv`.
2. Add one row per utility per storm to `events.csv`.
3. Add one row per figure to `cost_lines.csv`, with the page number.
4. Run `load.py`, fix anything it flags, then verify against the PDF.
5. Log anything interesting in `insights/insight_log.md`.

See `docs/extraction_guide.md` for state-specific notes.
