# Extraction guide

Notes on where storm cost data lives in each jurisdiction, and the traps found so far.

## Florida PSC

The richest source. Utilities file a petition for a limited proceeding after each storm season, then the commission issues an order.

- Petitions arrive within weeks of the storms and contain estimates. Orders arrive 12 to 24 months later with final figures. Record both, with different stages.
- Orders break costs into eight categories per storm: regular payroll, overtime payroll, contractors, line clearing, vehicle and fuel, materials and supplies, logistics, other.
- Mutual aid is included in "contractors", not shown separately.
- "ICCA adjustments" are non-incremental costs removed under Rule 25-6.0143. Record them as `non_incremental_removed`, not `disallowed`. They are not prudence findings.
- Capitalised costs are excluded from retail recoverable amounts. Record the total expense, and note capitalised amounts in `notes`.
- Petitions sometimes break later storms down only by function (distribution, transmission), not by category. Record what exists as `total`.
- Example: FPL Docket 20240149-EI; Duke Energy Florida 20240173-EI.

### Florida category mapping by utility (added 2026-11-13)

- **FPL and Gulf Power** use the eight-line exhibit (Storm Costs By Function). Use the Total column of the "Total Storm Related Restoration Costs" block (gross, before capitalization and ICCA).
- **Duke Energy Florida petitions** (Exhibit BB-2 in 2018, JN-2 to JN-4 in 2026) use eleven lines. Mapping: Labor Burdens/Incentives and Overhead Allocations to `payroll`; Employee Expenses to `logistics` (DEF defines them as lodging for employees and contractor crews plus meals, S073 PDF p.70); Internal Fleet to `vehicles_fuel`; Uncollectible, Other and Insurance Deductible to `other`. Use the Subtotal line (line 14), which is gross.
- **Duke Energy Florida final orders** (stipulations, e.g. PSC-2024-0377-FOF-EI) list eight amounts per storm. Contractors include vegetation and line clearing. Employee expenses and logistics both map to `logistics`; "Other" holds labor burdens and overheads.
- **Tampa Electric** Exhibit RJL-1 has five lines. Use the Total column (recoverable + O&M + capital). "Logistics/Other" is combined and goes to `other`.
- **FPUC** Revised Attachment D has thirteen lines; Payroll Overhead Allocations go to `payroll`, Fuel and Equipment Rental to `vehicles_fuel`.
- DEF's 2024 per-storm events sit alongside the combined 2024 interim-charge event (E007). Don't add them together.

## California PUC (PG&E CEMA)

- PG&E's Wildfire Mitigation and Catastrophic Events applications (A.20-09-019, A.22-12-009, A.23-12-001, A.24-11-009) give one table per declared event: Contract, Labor, Materials, Other, split capital (MWC 95) and expense (MWC IF).
- The tables cover only costs in counties with a declared emergency. The text gives the systemwide figure just above each table, which can be much larger (January 2021 atmospheric river: $110M systemwide, $30M in the table). Record the table and put the systemwide figure in event notes.
- Customer counts are rare; damage counts (poles, crossarms, transformers, spans) are given for most events and are kept in event notes.
- Later applications carry only tail costs for earlier storms. The 2022-23 winter storms' main figures were not found in the A.23-12-001 testimony downloaded so far.

## Connecticut PURA

- Storm costs are reviewed in multi-year batches (Eversource 2018 to 2023).
- Only storms above a $4 million threshold count as catastrophic. Grouping smaller storms together has been rejected.
- The Attorney General and Office of Consumer Counsel briefs list the specific challenges; they are as useful as the decision itself.
- Interest (carrying charges) can dwarf other disallowances. Record it separately in `notes` so it doesn't distort operational comparisons.

## Customer counts

Filings often omit customers affected. Use, in order of preference: the filing itself, the commission's post-storm report, ORNL EAGLE-I, then the utility's own press releases. Record which one in `customers_source_id`, and state whether the count is peak customers out or total customers affected. They are not comparable.

## Older commission reports

Reports such as the North Carolina Utilities Commission's 2002 ice storm review contain clean category data but in nominal dollars of that year. Record nominal amounts and the year; inflation adjustment happens in analysis, not in the data.
