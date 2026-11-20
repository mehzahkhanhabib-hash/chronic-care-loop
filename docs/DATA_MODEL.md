# Chronic Care Loop · data model

There are 21 tables in five groups. The schema is `backend/schema.sql` (SQLite). The PostgreSQL version with sample rows is `docs/schema.sql`. `dist/database.html` shows every table and every read and write, step by step.

```
 extract ─▶ member_feature ─▶ cohort (builder rules) ─▶ campaign ─▶ assessment + signal ─▶ care_plan_need ◀─1:1─▶ action
                ▲                                                                                       │
                └───────────────────── nightly run ◀── outcome ◀── contact (call + consent) ◀───────────┘
```

| Group | Tables | Written by |
|-------|--------|------------|
| Ingest & reference | `ingest_run`, `src_member_row`, `data_issue`, `trigger_def` | Extract load; rulebook |
| Population | `member`, `feature`, `member_feature` | Extract load (consent: the portal) |
| Targeting | `cohort`, `cohort_rule`, `cohort_member`, `campaign`, `campaign_cohort` | Studio · builder; nightly run (`cohort_member`) |
| Care intelligence | `assessment`, `signal`, `care_plan`, `care_plan_need` | Nightly run |
| Care operations | `care_team_user`, `action`, `contact`, `outcome`, `event_log` | Nightly run (actions); portal (contacts, outcomes) |

## How the rulebook maps onto the tables

| Rulebook | Where |
|----------|-------|
| §2 Cohort filters use raw inputs only. Risk, triggers and persona are outputs. | `feature.cohort_selectable = 0` for the Risk score, Trigger and Persona categories. The builder never offers them. |
| §2 R = C + M + K + U + A, tiers 0–3 / 4–7 / 8–12 / 13+ | `assessment`: the parts come from the extract's score columns, and the tier is recomputed. |
| Safety flag (DKA, hypoglycaemia) → priority clinical review | `assessment.priority_review`, which turns the alert RED |
| Alert RED / AMBER / YELLOW / GREEN → P1 same day, P2 next working day, P3 in 3 days, P4 digital nudge | `assessment.alert`, `assessment.contact_priority`. The worklist `action.due_date` follows from them. |
| §3 Trigger → action → owner → done when | `trigger_def`. A trigger that fires becomes a `signal`, then a `care_plan_need`. |
| Needs ordered safety → acute → uncontrolled → barrier → gap → goal. Current = top 3, Next = 4–6. | `care_plan_need.class`, `care_plan_need.slot` |
| One care-plan need = one action | Unique index `action_one_per_need` |
| Write-back: done promotes the next need, declined holds 90 days, not reached retries (max 3) | `outcome` rows, applied by `engine.process_outcomes()` |
| Consent gate; 10% holdout | `member.consent_status`; `cohort_member.holdout` (a stable hash, so a member stays in the control group run after run) |
| Exclusions (cancer, palliative care, dialysis and the others) | Members with `Exclusion = 1` in the extract are never in a campaign |

## Keys worth knowing

- `member_feature (member_id, feature_key)`: `feature_key` is `x:<extract column>` or `d:<derived>`. For example, `d:pdc_min_pct` is the lower of the diabetes and blood-pressure adherence.
- `care_plan_need.need_key` is a rulebook trigger code (`Trig1` … `Trig13`, `BPU`). The portal shows it with its own signal code (for example, Trig3 → `HYPO`). The mapping is `PORTAL_CODE` in `backend/reference.py`.
- `action.source`: `care_plan` (one per Current need), `worklist` (the outreach call), `call` (retries).
- `outcome.processed_at` stays empty until the outcome has been applied.

## How the artefacts exchange data

When the Studio and the portal are served by `backend/server.py`, both read and write through `/api` (see README). When the portal runs inside the Studio (screen 3), they also talk over `postMessage`:

| Message | Direction | Payload |
|---------|-----------|---------|
| `ccl:ready` | portal → studio | none |
| `ccl:sync` | studio → portal | `queued` (member masks on the call list), `focus`, `campaign` |
| `ccl:writeback` | portal → studio | `id` (mask), name, response, actions, open tasks. In live mode the Studio then reloads its list from the database. |
