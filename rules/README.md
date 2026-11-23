# Rule database

The CCC Rulebook (T2D and hypertension, 20 Nov 2026), written as data. The engine reads every threshold, trigger, action, slot, alert, priority and write-back from these tables. No rule is hard-coded.

| File | What it is |
|------|------------|
| `rule_*.csv` | **The source of truth.** One file per table. Edit in Excel or any text editor. |
| `rules.db` | The same tables as a SQLite database. Open it with any SQLite viewer. |
| `rules.sql` | The same tables as SQL (PostgreSQL or SQLite): DDL plus every row. |

Rebuild `rules.db` and `rules.sql` after editing a CSV:

```bash
python3 -m backend.rules
```

The server reloads the CSVs into its own database each time it starts. To apply a change, restart the server and run the nightly. The extract columns that rules read are described in `data/raw/glossary.tsv`.

## The chain

```
raw extract column ──rule_condition──▶ rule_trigger ──class──▶ rule_need_class ──rank──▶ rule_slot (CURRENT / NEXT / FUTURE)
                                            │                                                  │
                                            └──1:1──▶ rule_action (owner, done when, evidence) ◀┘ one action per CURRENT need
                                                              │
                         outcome (done, declined, not reached …) ──rule_writeback──▶ need status · action status · rule_gap_state
member values ──rule_condition (alert)──▶ rule_alert ──▶ rule_contact_priority (P1–P4, SLA) ──▶ rule_queue_order
R = C+M+K+U+A (rule_risk_band) ──▶ rule_tier (cadence)
```

| # | Table | Rows | What it decides |
|---|-------|------|-----------------|
| 1 | `rule_condition` | 100 | Raw extract column → test → fires a trigger, a "cannot tell", or an alert colour. Groups (`group_no`) are OR-ed; rows inside a group are AND-ed. |
| 2 | `rule_trigger` | 14 | The 13 rulebook triggers plus BP urgent: class, pathway, the extract flag, and `use_variant`. |
| 3 | `rule_action` | 14 | One next best action per trigger: owner, channel, done-when (verified in claims), evidence, prerequisite. |
| 4 | `rule_need_class` | 6 | Care-plan order (safety → acute → uncontrolled → barrier → gap → goal) and the due days for each class. |
| 5 | `rule_slot` | 4 | CURRENT = ranks 1–3, NEXT = 4–6, FUTURE = the rest, CLOSED. |
| 6 | `rule_risk_band` | 32 | The points in R = C + M + K + U + A, with the extract column that already holds each part. |
| 7 | `rule_tier` | 4 | Tiers 1–4 from R, and the contact cadence for each. |
| 8 | `rule_alert` | 4 | RED / AMBER / YELLOW / GREEN and the response each needs. The conditions are in `rule_condition`. |
| 9 | `rule_contact_priority` | 5 | Alert (plus trigger) → P1–P4, the SLA in days and the channel. |
| 10 | `rule_queue_order` | 4 | Worklist order: safety or RED, then tier, then campaign priority, then time past SLA. |
| 11 | `rule_writeback` | 9 | What each outcome does: need status, slot, action status, gap state, hold days, attempts, promotion. |
| 12 | `rule_gap_state` | 5 | Potential → Verified → Scheduled → Reported → Closed. Only claims close a gap. |
| 13 | `rule_guardrail` | 12 | G0–G10 and where each is enforced in the code. |
| 14 | `rule_decision_step` | 10 | The nurse's decision tree, A–J. |

## Two condition sets per trigger: `use_variant`

Each trigger has two condition sets in `rule_condition`:

- **`extract`**: the extract already computes the trigger as a `Trig…` flag column. This is the default.
- **`rulebook`**: the rulebook's own thresholds, written against raw columns.

To change which set a trigger uses, set `rule_trigger.use_variant` to `extract` or `rulebook`. BP urgent has no extract flag, so it always uses `rulebook`.

**Decision needed.** The extract flag for Trig1 fires at HbA1c ≥ 6.5%. The rulebook says ≥ the individual goal (about 8%). In the 24-row sample, 7 of the 17 members flagged are below 8%. To follow the rulebook, set `Trig1` to `rulebook`.

Every trigger carries `status = Draft: needs clinical sign-off`, as rulebook §8 requires. Clear it as each rule is approved.

## How to track it

Care plans and actions are stitched by key:

- `care_plan_need.need_key` = `rule_trigger.trigger_code`
- `action.action_code` = `rule_action.action_code`
- `action.need_id` = `care_plan_need.need_id` (a unique index allows one care-plan action per need)

Two views in the main database show progress:

- **`v_need_tracking`**: one row per need. It shows:
  - the trigger and its class
  - the slot and the need's status
  - the gap state
  - the action: owner, done-when, assignee and status
  - the last outcome
  - two flags, `overdue` and `missing_action`
- **`v_loop_kpis`**: totals for the whole loop:
  - open needs and CURRENT needs
  - CURRENT needs with no action (should always be 0)
  - overdue needs
  - needs "Reported" by a nurse but not yet seen in claims
  - needs closed in claims
  - needs declined and on hold
  - calls, members reached, and members who consented

The same data is available from the API:

```
GET /api/tracking            # KPIs and every need
GET /api/tracking?member=m133
GET /api/rules               # every rule table
```

Read gap states this way: a nurse's "done" moves a gap to **Reported**. It becomes **Closed** only when the next extract no longer fires the trigger, meaning the lab, visit or refill appeared in claims. A run with many Reported needs and few Closed ones is not yet evidence of impact (rulebook §7).

## The rulebook as 27 tables

`CCC_Rulebook_Tables.xlsx` is the whole rulebook as one workbook, one sheet per table, with an Index sheet that says which rulebook section each table comes from and which kit table it feeds. `rulebook_tables.sql` is the same 27 tables as plain SQL (all text columns, so it loads unchanged on SingleStore, MySQL, PostgreSQL and SQLite). Both are generated from the CSVs by `python3 rules/make_workbook.py`.

The 14 tables the engine reads are listed above. The other 13 carry the rest of the rulebook as data, so nothing lives only in prose:

| File | Rulebook section |
|------|------------------|
| `rule_loop_step.csv` | §1 the five steps of the loop and what each writes |
| `rule_risk_component.csv` | §2 the five components C, M, K, U, A with formula and cap |
| `rule_cadence.csv` | §2 cadence steps per tier with the rulebook labels |
| `rule_safety_flag.csv` | §2 and §6.3 the safety flag and the event pathway |
| `rule_builder_field_group.csv` | §2 the six builder field groups |
| `rule_ngql_guardrail.csv` | §2 the seven checks on a written query |
| `rule_trigger_state.csv` | §3 fired, cannot tell, not fired |
| `rule_campaign_mode.csv` | §3 automated and business modes |
| `rule_consent_gate.csv` | §5 what is shown before consent and what is not rendered |
| `rule_call_stage.csv` | §5 the ten stages of the call |
| `rule_documentation.csv` | §5 the six items of step J |
| `rule_event_type.csv` | §1 and §6 the twelve event types |
| `rule_open_decision.csv` | §8 the five open decisions |

## Fields, inputs and layouts are data too

Nothing about the extract columns is hard-coded any more. Three tables drive the generator and the care-intelligence view:

| File | What it is | Who edits it |
|------|------------|--------------|
| `rule_layout.csv` | The extract layouts the kit can load (341-column claims extract; 377-column longitudinal), each with its sample file | Data team, when a new export shape arrives |
| `rule_field.csv` | One row per field ever seen in any layout: SQL name, type, group, `load` (1 = goes into `member`), which layouts carry it, plausibility bounds (G0), which rules read it, description | Generated by `two-day-build/tools/gen_fields.py` from the layout headers; `load`, names, bounds and descriptions are kept when you edit them by hand |
| `rule_input.csv` | Every rulebook input (a risk band, a trigger, an alert colour, a gate, a builder group) → the field that feeds it, with a role | Clinical and data team: this is the mapping |

How it fits together: `gen_fields.py` reads the layouts and `rule_input` and refreshes `rule_field`; `gen_sql.py` builds `stg_extract` from the chosen layout's header, `member` from every field with `load = 1` (a field a rule reads is always loaded; a loaded field missing from a layout loads as NULL so every view still works), and the G0 bounds from `rule_field`. `CCL_LAYOUT=377 python3 two-day-build/tools/gen_sql.py` switches the whole kit to the longitudinal extract. Both layouts are loaded in SingleStore as `rule_field` and `rule_input`, and the view `v_rule_input` gives the care-intelligence screen the fields behind each rule.

Verified on MySQL: the 341 layout passes all 8 kit tests; the 377 layout (250 members) loads, fires 1,371 rules, builds 214 care plans, 607 CURRENT needs with 0 missing actions, 75 on today's list, and a re-run adds nothing. `plan_name` is not in the 377 file and loads as NULL; the builder's Plan field should use `policy_type` until it is back.
