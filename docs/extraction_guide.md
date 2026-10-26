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

## Connecticut PURA

- Storm costs are reviewed in multi-year batches (Eversource 2018 to 2023).
- Only storms above a $4 million threshold count as catastrophic. Grouping smaller storms together has been rejected.
- The Attorney General and Office of Consumer Counsel briefs list the specific challenges; they are as useful as the decision itself.
- Interest (carrying charges) can dwarf other disallowances. Record it separately in `notes` so it doesn't distort operational comparisons.

## Customer counts

Filings often omit customers affected. Use, in order of preference: the filing itself, the commission's post-storm report, ORNL EAGLE-I, then the utility's own press releases. Record which one in `customers_source_id`, and state whether the count is peak customers out or total customers affected. They are not comparable.

## Older commission reports

Reports such as the North Carolina Utilities Commission's 2002 ice storm review contain clean category data but in nominal dollars of that year. Record nominal amounts and the year; inflation adjustment happens in analysis, not in the data.
