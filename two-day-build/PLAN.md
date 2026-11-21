# Chronic Care Loop: the 2-day build on SingleStore

**Goal:** in two days, three developers make the three existing apps run on a real SingleStore backend. The backend covers the whole loop:

**raw member data → triggers → care-plan needs → nudge / call → nurse worklist → nurse outcome → follow-up action → next night**

It follows the CCC Rulebook (T2D and hypertension) rule for rule: the rulebook is a table, every screen reads from it, and the "rulebook view" shows each rule applied to a member and across the programme.

Everything here was tested end to end on MySQL 8.4, which uses the same SQL dialect as SingleStore. The tests used the 24-member sample of the extract. Eight automated checks pass, including one that shows the SQL fires exactly the same triggers, member by member, as the reference rules engine.

---

## 1. The leanest architecture

```
member_features.tsv ──LOAD DATA──▶ stg_extract (341 text cols)
                                       │ 03_load.sql: type + clean (G0)
                                       ▼
                                    member (80 typed cols + scores + consent)
   rules (REFERENCE tables) ─────┐     │ 04_nightly.sql (one SQL script, 8 steps)
                                 ▼     ▼
              member_signal → care_plan_need → action (nudge · call · care_plan) → worklist
                                                    ▲                                  │
                         05_followup.sql            │                                  ▼
                 outcome ──▶ follow-up action ──────┘              Care portal (nurse)
                                                                   Rulebook view (06_views.sql)
```

- **All logic is SQL**, in seven files you run in order. No ORM and no rules engine to build.
- **The API is thin:** about 250 lines of Python (`api/server.py`). Each endpoint is one SQL file or one `SELECT * FROM <view>`. Rewrite it in any language; the SQL doesn't change.
- **The rules are data.** Thresholds, actions, priorities and follow-ups live in REFERENCE tables, generated from the rule database the clinical team signs off (`rules/*.csv`).

## 2. The data model: 8 working tables + staging + 10 rule tables

| Table | One row per | What's in it | Written by |
|-------|-------------|--------------|------------|
| `stg_extract` | extract row | all 341 columns as text, exactly as received | load |
| `member` | member | 80 typed, cleaned columns the rules read; `consent`; scores `r_total`, `tier`, `alert`, `contact_priority` | load, nightly, portal (consent) |
| `campaign` (reference) | campaign | name, status, priority, trigger mode, builder rules, compiled `where_sql`, holdout % | builder |
| `campaign_member` | member × campaign | `holdout` flag (stable 10% control group) | builder, nightly |
| `member_signal` | member × trigger × day | `fired` or `cannot_tell`, with evidence | nightly |
| `care_plan_need` | member × trigger | class, slot (CURRENT / NEXT / FUTURE / CLOSED), status, **gap state**, due date, 90-day hold | nightly, portal |
| `action` | piece of work | kind (`nudge`, `call`, `care_plan`, `follow_up`, `retry`, `escalation`), assignee, due date, status, **`parent_action_id`** (the follow-up chain) | nightly, portal |
| `outcome` | nurse result | what the nurse recorded on an action, consent, notes | portal |
| `worklist` | member × day | today's call list: nurse, rank, lead action, status (`today` or `queued`) | nightly |

**Rule tables** (REFERENCE, so SingleStore copies them to every node and joins are free):

- `rule_trigger`: one row per rulebook rule: raw data, fires-when, class, next best action, owner, done-when, escalation, sign-off status
- `rule_priority`: alert → P1–P4 and SLA
- `rule_tier`, `rule_cadence`: tier bands and contact cadence
- `rule_followup`: outcome → follow-up
- `nurse`, `nurse_language`: the care team and the languages each nurse speaks
- `run_config`: the as-of date and the run date

**SingleStore specifics, already in `01_schema.sql`:**
- Member tables are sharded by `member_id`, and every primary key includes it.
- There are **no foreign keys**: SingleStore doesn't enforce them, so the SQL keeps integrity itself (anti-joins, member-scoped writes).
- The two scratch tables `work_member` and `work_rank` keep every UPDATE to a simple join on `member_id`.

## 3. How it follows the nurse rules (rulebook → where it lives)

| Rulebook | Implemented in |
|----------|----------------|
| §2 Cohort uses raw inputs only | `POST /cohorts/estimate` compiles builder rules against whitelisted `member` columns. Risk, tier and triggers are never filters. |
| §2 R = C+M+K+U+A; tiers 0–3 / 4–7 / 8–12 / 13+ | `04_nightly.sql` step 3 + `rule_tier` |
| §3 Raw data → trigger → action → owner → done-when | step 2 (conditions generated from `rule_condition.csv`) + `rule_trigger` |
| §3 Fired / cannot tell / not fired | `member_signal.state`; cannot-tell becomes a question asked once (G8) |
| §4 Alert RED / AMBER / YELLOW / GREEN | step 3 (RED: safety flag, BP ≥ 180/110, eGFR < 15, hypo or DKA; AMBER: post-discharge, HbA1c ≥ 9, BP ≥ 160/100, PDC < 50%) |
| §4 P1 same day · P2 next day · P3 3 days · P4 nudge | `rule_priority` (AMBER + post-discharge = P1) |
| §4 Queue: safety/RED → tier → campaign priority → overdue | step 8 `ROW_NUMBER()` order |
| §4 Match by language, within capacity | step 8 (`nurse_language`, round-robin, `daily_capacity`) |
| §4 Needs: safety → acute → uncontrolled → barrier → gap → goal; ≤ 3 CURRENT | step 5 (`ROW_NUMBER() … ORDER BY class_order`) |
| G7: one action per CURRENT need | step 6 + `05_followup.sql` F8 (anti-join) |
| §5 Write-back: done / declined (90 d) / not reached (3×, then P1 → lead) / carried | `05_followup.sql` + `rule_followup` |
| §5 A gap closes only in claims | done → `Reported`; the next extract without the trigger → `Closed` (step 4c) |
| G0 plausibility · G1c exclusions · G2 consent · G3 contact cap · G9 dispositions survive | load cleaning · step 1 · F4 · step 7 · step 4b |

## 4. The SQL formulas (the important ones)

**Clean a raw value (G0).** Generated for every column:

```sql
CASE WHEN (CASE WHEN TRIM(s.`Last_SystolicPressure_Value`) REGEXP '^-?[0-9]+(\\.[0-9]+)?$'
                THEN CAST(TRIM(s.`Last_SystolicPressure_Value`) AS DECIMAL(14,4)) END) BETWEEN 60 AND 260
     THEN … END                       -- 999 and BP 1/1 become NULL
CASE WHEN TRIM(s.`last_hba1c_date2`) REGEXP '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$'
     THEN STR_TO_DATE(TRIM(s.`last_hba1c_date2`), '%m/%d/%Y') END
```

**Risk, tier, alert, priority.**

```sql
r_total = clinical_score + comorbid_complication_score + kidney_score + utilization_score + age_sex_score
tier    = rule_tier row where r_total BETWEEN r_min AND r_max
alert   = CASE WHEN priority_clinical_review = 1 OR flag_dka_l12m = 1 OR flag_dm_hypoglycaemia_l12m = 1
                 OR last_systolicpressure_value >= 180 OR last_diastolicpressure_value >= 110 OR last_egfr_value < 15 THEN 'RED'
               WHEN trig4_post_discharge_care = 1 OR last_hba1c_value >= 9 OR last_systolicpressure_value >= 160
                 OR last_diastolicpressure_value >= 100 OR pdc_any_t2d_noninsulin < 0.5 OR pdc_any_htn < 0.5 THEN 'AMBER'
               WHEN <any trigger fired> THEN 'YELLOW' ELSE 'GREEN' END
priority = first rule_priority row matching (alert, needs_trigger)
```

**Raw member → trigger.** One block per trigger, generated from the rule database. The `use_variant` column switches between the extract's flag and the rulebook's thresholds:

```sql
SELECT m.member_id, 'Trig1', 'fired', CONCAT('Last_HbA1c_Value ', m.last_hba1c_value), rc.run_date
FROM member m JOIN run_config rc JOIN rule_trigger t ON t.trigger_code = 'Trig1'
WHERE (t.use_variant = 'extract'  AND m.trig1_hba1c_above_target = 1)
   OR (t.use_variant = 'rulebook' AND m.cohort_t2d_l12m = 1 AND m.last_hba1c_value >= 8)
```

**Slots.**

```sql
ROW_NUMBER() OVER (PARTITION BY member_id ORDER BY class_order, trigger_order) → rn
slot = CASE WHEN rn <= 3 THEN 'CURRENT' WHEN rn <= 6 THEN 'NEXT' ELSE 'FUTURE' END
```

**Holdout (stable 10%).**

```sql
CRC32(CONCAT(campaign_id, ':', member_id)) % 100 < holdout_pct
```

**Worklist rank and nurse.**

```sql
rank_no    = ROW_NUMBER() OVER (ORDER BY urgent DESC, tier DESC, campaign_priority, due_date, r_total DESC)
nurse      = nurse_language row where language = member.language AND lang_idx = MOD(lang_rn - 1, n_nurses) + 1
nurse_rank = ROW_NUMBER() OVER (PARTITION BY nurse_id ORDER BY rank_no);   status = 'today' if nurse_rank <= daily_capacity else 'queued'
```

## 5. Nurse worklist orchestration (step 8)

1. **Who gets a contact.** Every campaign member with an open CURRENT need gets one contact action (step 7). It's a **call** due by the SLA (P1 today, P2 tomorrow, P3 in 3 days), or a **digital nudge** for P4. No new contact is made within 14 days of a reached call (G3).
2. **One row per member.** The member is led by their most urgent open nurse action: call, then retry, then follow-up. Escalations go to the clinical lead, not to a nurse's list.
3. **Order.** Safety or RED first, then tier 4→1, then campaign priority, then due date.
4. **Assignment.** Language first (Arabic or English), round-robin within the language, and up to each nurse's `daily_capacity`. Anything over capacity is `queued` and rolls to the next day.
5. **Assignees.** All of the member's open actions are assigned to the nurse who has them on her list.

**Sample run, 20 Nov:**
- 21 members on today's list: Omar 9, Sara 9, Nadia 3 (English speakers only).
- RED members first, each assigned to a nurse who speaks their language.

## 6. How a nurse's action becomes a follow-up (`05_followup.sql`)

The portal calls one endpoint, `POST /actions/{id}/outcome {result, consent, notes}`. In one transaction, the SQL:

1. records the outcome
2. closes the action
3. moves the need
4. creates the **follow-up action** linked by `parent_action_id`
5. promotes the next need into CURRENT, with its own action

| Nurse records | Action | Need | Gap | Follow-up created |
|---------------|--------|------|-----|-------------------|
| `reached` (on a call) | done | – | – | **Cadence check-in**, on the tier cadence (Tier 4: +7 d, 3: +14, 2: +42, 1: +90) |
| `agreed` | done | open | Scheduled | **Check it happened: {done when}**, on the need's due date |
| `done` | done | done, CLOSED | **Reported** | **Verify in claims: {done when}** (+14 d); the next need is promoted |
| `declined` | declined | declined, 90-day hold (G4) | – | **Re-offer: {action}** at day 90; the next need is promoted |
| `not_reached` | done | – | – | **Retry call (attempt n of 3)** next working day; after 3, a P1 member → **escalation** to the clinical lead |
| `callback` | done | – | – | **Callback requested** (+1 d) |
| `carried` | stays open | stays CURRENT | – | none |
| `escalated` | done | open | – | **Clinician review** the same day |

**Worked example (m26, from the test run).** m26 is 65, speaks Arabic, has T2D and hypertension, R = 13, Tier 4, AMBER, P1.

| Nurse records | On | Becomes |
|---|---|---|
| reached + consent granted | P1 call | **Cadence check-in** on 27 Nov |
| agreed | Glycaemic treatment review | **Check it happened: goal, decision and next test date recorded**, 27 Nov |
| done | Same-day clinician review (hypo) | Gap **Reported**; **Verify in claims: review note and medicine change logged**, 4 Dec; *Home BP recheck* moves into CURRENT |
| declined | GP follow-up within 72 h | Held to 18 Feb; **Re-offer** on 18 Feb; *Book eGFR and UACR* moves into CURRENT |

The chain is visible with `GET /members/m26/actions` (`v_action_chain`: action → because of outcome → came from).

## 7. The rulebook view (`v_rulebook_member`, `v_rulebook_programme`)

There is no separate "disease-management view". The rulebook itself is the view. `rule_trigger` holds one row per rule, with the columns the rulebook document has: raw data, fires when, class, next best action, owner, done when, escalation, and the sign-off status. The nightly run writes which rules fired per member; the view joins the two.

**Per member** (`GET /members/{id}/rulebook`): one row per rule the member is in scope for (T2D rules for T2D members, HTN rules for HTN members, shared rules for both), in rulebook order (safety → acute → uncontrolled → barrier → gap → goal). Columns, left to right, exactly as the rulebook reads:

| Rule | Raw data | Fires when | State | Evidence | Need (slot · status · gap) | Next best action · owner | Done when | Action now · due |
|---|---|---|---|---|---|---|---|---|

Status per rule: **Open · off target** (safety / acute / uncontrolled) · **Open** · **Awaiting claims** (nurse reported done) · **Declined · on hold** · **Closed in claims** · **Unknown** (a value the rule needs is missing) · **Not triggered**.

**m26 after the call:** Trig3 hypoglycaemia *Awaiting claims* (verify by 4 Dec) · Trig4 post-discharge *Declined · on hold* to 18 Feb · Trig1 HbA1c, Trig2 BP treatment review and Trig5 kidney check *Open · off target* in CURRENT, each with its action due 27 Nov · Trig9, Trig6, Trig13 *Open* in NEXT · Trig11, Trig8 *Open* in FUTURE · BPU, Trig12, Trig7, Trig10 *Not triggered*.

**Programme** (`GET /rulebook/programme`): one row per rule across all members: in scope, fired, cannot tell, open needs, in CURRENT, **reported by nurse**, **closed in claims**, declined, and the rule's sign-off status. Nurse-reported against closed-in-claims is the measure of impact; the rulebook is explicit that a nurse's "done" click is not evidence on its own.

To change a rule, change its row in `rules/*.csv`, run `tools/gen_sql.py`, and re-run `02_rules.sql` and `04_nightly.sql`. Nothing else moves.

## 8. The API (`api/server.py`, about 250 lines)

| Method | Path | SQL | Used by |
|--------|------|-----|---------|
| GET | `/health` | `run_config` | all |
| POST | `/cohorts/estimate` | compiled `COUNT(*)` | Builder: live count |
| POST | `/campaigns` | `campaign` + `campaign_member` (holdout) | Builder: hand-off |
| POST | `/runs/nightly` | `04_nightly.sql` | scheduler; "run now" after hand-off |
| GET | `/worklist?nurse=` | `v_worklist` | Portal: nudge queue |
| GET | `/members/{id}` | `v_member_summary` + signals | Portal header; Studio ② care intelligence |
| GET | `/members/{id}/care-plan` | `v_care_plan` | Portal: care plan (CURRENT / NEXT / FUTURE) |
| GET | `/members/{id}/rulebook` | `v_rulebook_member` | Portal: the rulebook tab |
| GET | `/members/{id}/actions` | `v_action_chain` | Portal: actions and timeline |
| POST | `/actions/{id}/outcome` | `05_followup.sql` | Portal: every nurse button |
| GET | `/rulebook/programme` | `v_rulebook_programme` | Programme page: every rule across members |
| GET | `/kpis` | `v_kpis` | analytics |

Real responses for every endpoint are in `api/examples/`. The record shapes today's apps render are in `api/app-shapes/`.

## 9. The 3-developer plan

### Dev A: data and rules (SingleStore)

**Day 1 AM**
- Create the database and run `01_schema.sql`, `02_rules.sql` and `02b_setup.sql`.
- Load the extract with `03_load.sql` (`LOAD DATA LOCAL INFILE`).
- ✔ 24 members; the cleaning query lists m44, m75 and m147.

**Day 1 PM**
- Run `06_views.sql`, then refresh `campaign_member` (the statement is in the API) and run `04_nightly.sql`.
- ✔ The acceptance numbers in §10 match.

**Day 2 AM**
- Load the **full 167-row extract**.
- Set up the nightly job: an `api/server.py` call from cron, or a SingleStore PIPELINE for the file.
- Take `rule_trigger.use_variant` for Trig1 to the clinical team (6.5% vs 8%).

**Day 2 PM**
- Performance pass: `EXPLAIN` the views.
- Add a columnstore copy of `member_signal` if history grows.
- Support the demo.

### Dev B: API and orchestration

**Day 1 AM**
- Stand up `api/server.py`, or port it to your stack. The SQL files are the contract.
- Point it at SingleStore with `S2_HOST`, `S2_USER`, `S2_PASSWORD` and `S2_DB`.

**Day 1 PM**
- `POST /actions/{id}/outcome` in one transaction.
- Walk the m26 example in §6 and check `v_action_chain`.

**Day 2 AM**
- `/worklist`, `/members/{id}/…` and `/dm/programme`.
- CORS for the apps.
- A fixed demo login: a nurse picker that sets `nurse_id`.

**Day 2 PM**
- Hardening: validate `result` against `rule_followup`; whitelisted builder fields only (already done).
- Request logging.

### Dev C: frontend and demo

**Day 1 AM**
- In the **portal**, swap the live-mode data source to the new API:
  - nudge queue ← `/worklist`
  - care plan ← `/members/{id}/care-plan`
  - Done / Declined / Not reached / Agreed buttons → `POST /actions/{id}/outcome`

**Day 1 PM**
- Add the **rulebook tab** on the member page (`/members/{id}/rulebook`) and the **programme page** (`/rulebook/programme`).

**Day 2 AM**
- **Builder:** estimate → `/cohorts/estimate`; hand-off → `POST /campaigns` then `POST /runs/nightly`.
- **Studio ②:** member list ← `/worklist` + `/members/{id}`.

**Day 2 PM**
- Rehearse the demo in §11 on the full extract.
- Fallback: the apps still run on their built-in data if the API is down.

**Checkpoints:**
- **End of day 1:** the m26 chain works in SQL and through the API.
- **Midday, day 2:** the portal shows the real worklist and the care plan, and records outcomes.
- **End of day 2:** the demo.

## 10. Acceptance checks (24-member sample, run date 20 Nov 2026)

| Check | Expected |
|-------|----------|
| `SELECT COUNT(*) FROM member` | 24 |
| fired / cannot-tell signals | 152 / 7 |
| fired, by trigger | Trig3 4 · BPU 1 · Trig4 15 · Trig1 17 · Trig2 6 · Trig5 19 · Trig9 16 · Trig6 8 · Trig12 7 · Trig13 13 · Trig7 1 · Trig11 21 · Trig10 2 · Trig8 22 |
| members with a care plan | 21 |
| open needs / CURRENT needs | 144 / 63 |
| `current_needs_without_action` | **0, always** |
| on today's worklist | 21 (Omar 9, Sara 9, Nadia 3) |
| re-running the nightly | adds no rows |

`tests/test_kit.py` runs all of this automatically, plus the follow-up rules and the "gap closes only in claims" check.

## 11. The demo (10 minutes)

1. **Builder.** Build "T2D, HbA1c ≥ 9" (live count: 6 of 24) and hand it off. The nightly run takes seconds.
2. **Portal, nudge queue.** RED P1 members first, each with a nurse who speaks their language.
3. **Open m26.** P1 call, consent pending. Log consent and record *reached*: a cadence check-in appears for 27 Nov.
4. **Care plan.** Mark the hypo review **done**: it becomes *Reported*, a *Verify in claims* follow-up appears, and the next need moves into CURRENT. Decline the GP follow-up: it's held to 18 Feb with a re-offer.
5. **Rulebook tab.** The same member, rule by rule: raw data → fires when → fired → need → next best action → done when.
6. **Programme page.** Every rule across all members: in scope, fired, open, nurse-reported, closed in claims.

## 12. Out of scope for the two days, and risks

- **Not in the two days:**
  - single sign-on and roles (use a nurse picker)
  - telephony
  - the knowledge-graph "Describe" in the builder
  - the builder's full field list (dx, labs, age, admissions, ED, PDC, cost and gender are wired; add others to `compile_rule`)
  - the extract pipeline from the warehouse
- **SingleStore check on day 1:** the SQL avoids correlated subqueries in UPDATEs and uses only joins on `member_id`, but `EXPLAIN` the views once on your cluster version.
- **Data:** the extract is real (masked) member data. Keep it in the approved SingleStore workspace.
- **Clinical:** every rule is marked *Draft: needs clinical sign-off*.
