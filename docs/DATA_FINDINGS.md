# What the loader found in the extract

The checks below run on every load (`backend/ingest.py`) and are stored in `data_issue`. You can read them at `GET /api/data-quality`. The counts are from the 24-row sample in `data/raw/`. Load the full 167-row file to get the full counts.

## File structure

- The extract is tab-separated: one row per member and 341 columns. The header is in the same order as the glossary (341 rows), and every column is described.
- Values: 111 flags (0/1), 87 numbers, 27 shares (0–1), dates as `m/d/yyyy`, money as spreadsheet text, and free text. `NULL` is written literally.
- The as-of date is 31 Oct 2026. Dates are stored as ISO text, plus the number of days before the as-of date, so a rule such as "no HbA1c in 180 days" becomes `value_num > 180`.

## Values that are set to empty and logged (errors)

| Member | Column | Raw value | Why |
|--------|--------|-----------|-----|
| m44 | systolic BP, diastolic BP, BMI | `999` | Placeholder for "no value" |
| m75, m147 | systolic and diastolic BP | `1` / `1` | Not a possible reading |

None of these reach a rule. If BP is missing for a member with hypertension, the backend raises a `cannot_tell` signal and does not guess.

## Differences from the rulebook (handled in the backend)

| Finding | What the backend does |
|---------|----------------------|
| `Trig1_HbA1c_above_target` fires at HbA1c ≥ 6.5%. The rulebook's goal is around 8%, individualised. 7 of the 17 members where it fires have HbA1c below 8%. | Uses the flag as delivered and logs each case as `info`. **Decision needed:** keep 6.5%, or apply a goal (for example 8%) in the nightly run. |
| `Risk_tier` is numbered the opposite way from the rulebook: "1. Very High" … "4. Low". | `assessment.tier` uses the rulebook's numbering: 1 Low … 4 Very high. |
| The glossary spells the allocation `PREVHEATH`. The data says `PREVHEALTH`. | Uses `PREVHEALTH`. |
| `rank_PURECS_per_payable` is empty in every row. The sample is all PREVHEALTH, so the PURECS ranking never applies. | Not used. |
| `Last_HbA1c_Date` (result date) and `last_hba1c_date2` (billed test date) differ for 8 members. | Trig6 ("HbA1c due") uses the billed test date, as the glossary says. Each case is logged. |
| Money columns are formatted text, such as `" 7,268.55 "`, with `" -   "` for zero. | Parsed to numbers. `-` becomes 0. |

## Consistency checks that passed

- `Total_risk_Score` equals the sum of its five parts for every row.
- `# of triggers` equals the number of main Trig flags set (the a/b/c sub-triggers are not counted).
- `Risk_tier` agrees with the total score once the reverse numbering is allowed for.

## Not in the extract

The builder reports these rules as unanswerable instead of silently dropping them:

- LDL values
- Region
- PURA app users
- Wearable readings
- Vaccinations

The portal shows "No wearable feed in the claims extract" where the synthetic version showed device data. Member names are pseudonyms generated from `mask_id`.
