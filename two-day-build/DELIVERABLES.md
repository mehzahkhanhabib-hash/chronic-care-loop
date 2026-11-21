# Chronic Care Loop · the GCEO demo, built in two days by three developers

This is not a batch system we are showing. It is one story told live on screen: **a real member → the rules that fire for them → a care portal already filled with their plan → a nurse who sees it, acts, and records what happened → a worklist that picks that up and moves the next action to the right person.** The rules run is a button in the demo. Scheduling it nightly comes later and changes nothing on screen.

Everything below already exists in this folder and passes its tests on a MySQL stand-in for SingleStore. The two days are for running it on **our** SingleStore with the 250-member snapshot, owning one layer each, wiring the three apps, and rehearsing the story until it runs without a pause.

## The demo story (what the GCEO sees, 10 minutes)

| Beat | On screen | What it proves | Layer that carries it |
|---|---|---|---|
| **1. A member, in full** | Care portal, member header: age, language, pathway, risk tier, alert, priority; the 360 of raw values (HbA1c, BP, eGFR, admissions, adherence) | Member 360 works: the extract is loaded, cleaned and readable | 2 · Member 360 |
| **2. The rules, applied** | The rulebook tab: 14 rules in rulebook order, each with raw data → fires when → fired or not → evidence | The rules work, rule by rule, and each shows why it fired | 1 · Rule layer |
| **3. The plan, already there** | Care plan: CURRENT (top 3), NEXT, FUTURE; each need with its next best action, owner and done-when | The portal is fuelled from the rules, not typed in | 2 · Member 360 |
| **4. The nurse acts** | Nurse records *reached* and consent; marks one action *done*; *declines* another. Each click shows the follow-up it created, with a date | The nurse sees and takes actions, and every action produces the next one | 2 · Member 360 |
| **5. The worklist moves** | Press **Run rules**. Open the nudge queue: the member is back on the nurse's list led by the new follow-up; the need she marked done reads *Awaiting claims*; the declined one is on hold to February | The outcome fed the worklist and is being actioned, in order, by the right nurse | 3 · Worklist orchestration |
| **6. The whole programme** | Programme page: every rule across all 250 members: fired, open, nurse-reported, closed in claims. Then the builder: build a cohort, hand it off, press Run rules, the queue fills | From one member to the population, and campaigns feed the same loop | 1 and 3 |

Beat 5 is the one that matters. It only works if beats 1–4 are real data on real tables, which is why the three layers below exist. The whole story has already been run on the 248-member snapshot with this kit (numbers in the tables below), so the two days are about SingleStore, the screens and the rehearsals, not about whether it works.

## The three deliverables

```
raw extract ─▶ member ─▶ [1 RULE LAYER] rules fire, score, alert, priority
                              │
                              ▼
                 [2 MEMBER 360] care-plan need ─▶ action ─▶ nurse outcome ─▶ follow-up
                              │
                              ▼
                 [3 WORKLIST ORCHESTRATION] campaign ─▶ nudge / call ─▶ nurse list ─▶ run rules ─▶ next action
```

| | Deliverable 1 · Rule layer | Deliverable 2 · Member 360 | Deliverable 3 · Worklist orchestration |
|---|---|---|---|
| **Owner** | Dev A | Dev B | Dev C |
| **Demo beats** | 2, 6 | 1, 3, 4 | 5, 6 |
| **Question it answers** | Which rules fire for this member, and how urgent are they? | What is this member's plan, what did the nurse do, what happens next? | Who do we contact today, which nurse, in what order, and what changed after the nurse acted? |
| **Source of truth** | `rules/*.csv` (14 files) → `tools/gen_sql.py` | the extract → `03_load.sql` (G0 cleaning) | `02b_setup.sql` (nurses, languages, campaigns) |
| **SQL owned** | `02_rules.sql`; `04_nightly.sql` steps 2–3 | `01_schema.sql`, `03_load.sql`; `04_nightly.sql` steps 4–6; `05_followup.sql` | `04_nightly.sql` steps 1, 7, 8 |
| **Tables owned** | `rule_trigger` (14 rules, one row each), `rule_priority`, `rule_tier`, `rule_cadence`, `rule_followup`, `run_config`; writes `member_signal` and `member.r_total / tier / alert / contact_priority` | `stg_extract`, `member`, `care_plan_need`, `action`, `outcome` | `campaign`, `campaign_member`, `nurse`, `nurse_language`, `worklist` |
| **Views owned** | `v_rulebook_programme` | `v_member_summary`, `v_care_plan`, `v_rulebook_member`, `v_action_chain` | `v_worklist`, `v_kpis` |
| **API owned** | `GET /rules` · `GET /rulebook/programme` | `GET /members/{id}` · `/care-plan` · `/rulebook` · `/actions` · `POST /actions/{id}/outcome` · `POST /members/{id}/reset` (demo only) | `POST /cohorts/estimate` · `POST /campaigns` · `POST /runs/rules` · `GET /worklist?nurse=` · `GET /kpis` |
| **Screen wired** | Portal: rulebook tab. Care Studio: programme page | Portal: member header, 360 values, care plan, timeline, the five buttons | Portal: nudge queue and the **Run rules** button. Builder: live count and hand-off. KPIs |
| **Must bake in** | `use_variant` switch per rule (extract flag vs rulebook threshold); `cannot_tell` when a value is missing (G8); every rule carries its sign-off status; evidence text on every fired rule | exactly one open care-plan action per CURRENT need (G7); a gap closes **only** in claims; declined = 90-day hold; not reached = 3 attempts, P1 escalates; every follow-up keeps `parent_action_id` | holdout members are never contacted; one contact per member per day; no new contact within 14 days of a reached call; queue order RED/safety → tier → campaign priority → due; language match, then even split up to each nurse's capacity; escalations go to the lead, not the nurse list; a follow-up leads the member's row after a re-run |
| **Done on the 24-member sample** | 152 fired / 7 cannot tell; per rule: Trig3 4 · BPU 1 · Trig4 15 · Trig1 17 · Trig2 6 · Trig5 19 · Trig9 16 · Trig6 8 · Trig12 7 · Trig13 13 · Trig7 1 · Trig11 21 · Trig10 2 · Trig8 22 | 21 care plans, 63 CURRENT needs, `current_needs_without_action = 0`; the m26 chain (reached → check-in 27 Nov; agreed → check 27 Nov; done → Reported + verify 4 Dec; declined → hold to 18 Feb + re-offer) | 21 on today's list: Omar 9, Sara 9, Nadia 3; nobody from the holdout; re-running adds no rows; after m26's outcomes and a re-run, m26 is back on his nurse's list led by the cadence check-in due 27 Nov; a reset returns every KPI to the baseline |
| **Done on the 248-member snapshot** (already run here) | 1,442 fired / 86 cannot tell (all Trig2: no usable BP); per rule: Trig3 23 · BPU 2 · Trig4 90 · Trig1 141 · Trig2 61 · Trig5 187 · Trig9 136 · Trig6 102 · Trig12 65 · Trig13 118 · Trig7 18 · Trig11 195 · Trig10 24 · Trig8 193 | 218 care plans, 632 CURRENT needs, `current_needs_without_action = 0`; demo member **s26** (65, male, Arabic, T2D + HTN, tier 4, P1, 10 rules fired, HbA1c 11.0, no eGFR on record, one admission) | 75 on today's list (25 per nurse, at capacity), 143 queued for the next days; 31 of 248 held out of the main campaign; after s26's outcomes and a re-run he is back on Omar's list led by the cadence check-in; reset returns every KPI to the baseline |
| **Test** | `tests/test_kit.py::test_triggers_match_reference_engine`, `test_rerun_is_idempotent` | `test_every_current_need_has_one_action`, `test_z_nurse_outcomes_create_follow_ups`, `test_zz_gap_closes_only_in_claims`, `test_load_and_g0_cleaning` | `test_worklist_rules`, `test_holdout_and_exclusions_get_no_needs` |

**Dependencies, in order:** load (Dev B) → rules (Dev A) → needs and actions (Dev B) → contacts and worklist (Dev C). All of it already runs as one script, so nobody waits: each developer runs the whole thing and verifies their own layer.

**The demo member is s26.** He is the same person as m26 in `PLAN.html`, so the worked story there is his. 65, male, Arabic-speaking, T2D and HTN, tier 4, P1, 10 rules fired, HbA1c 11.0, no kidney test on record, discharged recently. Omar Khalid gets him on the list. Every rehearsal uses him; `POST /members/s26/reset` between runs. Backups with the same shape: s4, s23 (P1, 10 rules fired).

---

## Action plan

### Hour 0 (together, 09:45–10:30)

1. Dev B creates database `ccl` on SingleStore and runs, in order: `01_schema.sql`, `02_rules.sql`, `02b_setup.sql`, `06_views.sql`.
2. The snapshot is already prepared as `data/member_features_250.tsv` (248 members, 341 columns, pseudonymous ids s1 … s248). Dev B copies it to `data/member_features.tsv` and runs `03_load.sql` from the `data/` folder. If a newer export arrives, `python3 tools/add_ids.py <export>.csv data/member_features.tsv` prepares it the same way.
3. Dev C starts the API (`cd api && S2_DB=ccl python3 server.py --port 8080`) and runs `curl -X POST localhost:8080/runs/rules`.
4. Everyone runs `SELECT * FROM v_kpis;` and writes the row into the Teams thread. That row is the baseline for the two days.

### Day 1 (own your layer; by 17:00 the whole story runs in curl)

| | Dev A · Rule layer | Dev B · Member 360 | Dev C · Worklist |
|---|---|---|---|
| **AM** | Read `rule_trigger` row by row against the rulebook document. Run `04_nightly.sql` step 2 alone; compare `member_signal` counts per rule with the baseline. Decide the Trig1 variant (extract 6.5% vs rulebook 8%) with the clinical lead; set `use_variant`. | Check `03_load.sql` on the snapshot: nulls, 999 placeholders, BP 1/1, dates. Pick the demo member. Read `v_member_summary` and `v_rulebook_member` for them against the raw row. | Edit `02b_setup.sql`: real nurse names, languages, daily capacity. Re-run step 8 and read `v_worklist` for each nurse. Confirm the demo member lands with a nurse who speaks their language. |
| **PM** | `EXPLAIN` steps 2–3 on SingleStore; fix anything the dialect rejects. Make one rule change end to end (edit CSV → `gen_sql.py` → re-run 02 and 04) and show the fired count move. | Walk beat 4 through the API with curl on the demo member: reached, done, declined. Read `v_action_chain` after each. | Walk beat 5: after Dev B's outcomes, `POST /runs/rules`, then `GET /worklist?nurse=`: the demo member leads with the follow-up. Then beat 6: `POST /cohorts/estimate`, `POST /campaigns`, `POST /runs/rules`. |
| **17:00 checkpoint** | fired counts per rule match the engine on both datasets; one rule change proven | beats 1–4 work through the API on the demo member | beats 5–6 work; `v_kpis` unchanged after a plain re-run |

### Day 2 (wire the screens, rehearse, demo)

| | Dev A | Dev B | Dev C |
|---|---|---|---|
| **AM** | Portal rulebook tab ← `GET /members/{id}/rulebook`. Care Studio programme page ← `GET /rulebook/programme`. | Portal member page: header and 360 ← `/members/{id}`, care plan ← `/care-plan`, timeline ← `/actions`; the five buttons → `POST /actions/{id}/outcome`, each showing the follow-up it created. | Portal nudge queue ← `GET /worklist?nurse=` with a **Run rules** button → `POST /runs/rules` then refresh. Builder: live count ← `/cohorts/estimate`; hand-off → `/campaigns` then `/runs/rules`. KPIs ← `/kpis`. |
| **13:00** | First full rehearsal, all six beats, on the demo member. Fix what breaks. | | |
| **15:00** | Second rehearsal, timed. Reset the demo member between runs with `POST /members/{id}/reset` (forgets the nurse's work on that member and runs the rules again; proven to return the KPIs to the baseline). | | |
| **17:00** | Demo to the GCEO. Dev C drives, Dev B narrates the member, Dev A answers rule questions. | | |

---

## Teams post (paste as is)

> **Chronic Care Loop · 2-day build starts tomorrow 09:30 · GCEO demo on Day 2 at 17:00**
>
> We are showing the GCEO one live story: a real member, the rules that fire for them, a care portal already filled with their plan, a nurse who acts and records it, and a worklist that picks that up and moves the next action. To make that real, the three apps (Cohort & Campaign Builder, Care Studio, Care Coordinator Portal) go onto our SingleStore in two days. The SQL, the API and the tests already exist and pass on a MySQL stand-in. Our job is to run it here, own one layer each, load the 250-member snapshot, wire the screens, and rehearse.
>
> **Before 09:30 tomorrow**
> 1. Get the kit: `CCL-2-Day-Build.zip` (pinned above) or the repo folder `two-day-build/`. Read `DELIVERABLES.md` (the demo story, your layer, and the numbers the 248-member snapshot already produces) and skim `PLAN.md`.
> 2. Confirm you can log in to SingleStore and create a database. Install the `mysql` client and `pip install pymysql`.
> 3. Do **not** load the data anywhere outside the approved SingleStore workspace. The snapshot is real, masked member data.
>
> **Layers**
> - **Dev A: Rule layer.** The 14 rules as rows, firing with evidence, score, alert, priority. Demo beats 2 and 6 (the rulebook tab and the programme page).
> - **Dev B: Member 360.** Load and cleaning, the member page, care plan, the five nurse buttons and the follow-up each creates. Demo beats 1, 3 and 4.
> - **Dev C: Worklist orchestration.** Campaigns, contacts, the nurse queue, the Run rules button, KPIs. Demo beats 5 and 6.
>
> **Tomorrow**
> - 09:30 kickoff (45 min): the story on one member, the three layers, the rules we don't break.
> - 09:45–10:30 together: database up, rules in, snapshot loaded, first rules run, `v_kpis` row posted here.
> - 13:00 and 17:00: 10-minute standup in this channel. By 17:00 the whole story runs end to end in curl.
> - Day 2: 13:00 first full rehearsal, 15:00 timed rehearsal, 17:00 demo.
>
> **Rules we don't break**
> - A rule changes only in `rules/*.csv`, then `tools/gen_sql.py`. No thresholds in app code or hand-edited SQL.
> - The apps never write to tables. Every nurse button is `POST /actions/{id}/outcome`.
> - A gap closes only when the claim arrives. A nurse's "done" makes it *Reported*, not *Closed*.
> - Every CURRENT need has exactly one open action. `v_kpis.current_needs_without_action` stays 0.
> - Nothing in the demo is typed in by hand. If a screen is empty, the fix is in the data or the SQL, not in the app.
>
> Questions in this thread, not in DMs, so all three of you see the answer.

---

## Tomorrow morning: what you do, what you say, what each step looks like

**08:45. You.** Open `PLAN.html` and `DELIVERABLES.md` on the shared screen. Have the snapshot file ready in the workspace. Have the Teams post already posted (tonight).

**09:30–09:45. Kickoff, part 1: the story.** Open `PLAN.html` section 2 (m26). Say: *"On Day 2 at five we show the GCEO one member. The extract says HbA1c 11, kidney tests missing, discharged recently. Ten rules fire, and the screen shows why each one fired. Three become the member's current plan. The nurse calls him, records what happened, and each click creates the next action. Then we press Run rules and the worklist has moved: he is back on the nurse's list with the follow-up, the thing she finished is waiting for the claim, the thing he declined is parked until February. Everything we build in two days is that story, on real data, for 250 members."* Scroll section 4 (action → follow-up) and section 5 (the rulebook view). Five minutes.

**09:45. Kickoff, part 2: the three layers.** Open `DELIVERABLES.md`: the demo story table, then the three-layer table. Read the "Demo beats" and "Question it answers" rows aloud. Assign the owners. Say: *"All the SQL exists. Day 1 you run it, read your steps against the rulebook, and prove your beats with curl. Day 2 you wire your screen and we rehearse twice."* Then the rules we don't break. Five minutes.

**09:55–10:30. Hour 0, hands on, one screen.** Dev B drives, the other two follow on their machines.

| Step | Command | What you see when it worked |
|---|---|---|
| 1. Database and tables | `mysql -h … ccl < sql/01_schema.sql` | no output; `SHOW TABLES;` lists 19 tables (9 reference, 1 staging, 7 member tables, 2 scratch work tables) |
| 2. The rulebook as rows | `mysql ccl < sql/02_rules.sql` | `SELECT trigger_code, class_label, fires_when, action_title FROM rule_trigger ORDER BY class_order, trigger_order;` prints 14 rows in rulebook order, Trig3 first |
| 3. Nurses and campaigns | `mysql ccl < sql/02b_setup.sql` | `SELECT * FROM nurse;` shows the team; `SELECT * FROM run_config;` shows as-of 2026-10-31, run date 2026-11-20 |
| 4. Views | `mysql ccl < sql/06_views.sql` | `SHOW FULL TABLES WHERE table_type='VIEW';` lists 7 views |
| 5. The snapshot | `cp data/member_features_250.tsv data/member_features.tsv && cd data && mysql --local-infile=1 ccl < ../sql/03_load.sql` | `SELECT COUNT(*) FROM member;` returns 248; `SELECT member_id, age, language, last_hba1c_value FROM member LIMIT 5;` shows typed values, no 999s, no `#VALUE!` |
| 6. First rules run | `cd api && S2_DB=ccl python3 server.py --port 8080 &` then `curl -X POST localhost:8080/runs/rules` | JSON with the step timings; takes seconds. This is the same button the demo presses. |
| 7. The baseline row | `curl localhost:8080/kpis` | one JSON object. Expected: members 248, triggers_fired_today 1442, members_with_plan 218, current_needs 632, **current_needs_without_action 0**, on_todays_list 75, queued_over_capacity 143. Paste it into Teams. |
| 8. One member, the whole story in curl | `curl localhost:8080/members/s26/rulebook`, `curl localhost:8080/members/s26/care-plan`, `curl localhost:8080/worklist?nurse=U-0150` | the rulebook table for one member (14 rows, state and status per rule); their plan with one action per CURRENT need; a nurse's list, ranked, each row with the lead action and the due date. Beats 1–3 and 5, before anyone has written a line. |

If step 5 fails on a column, that is the first real finding of the day: post the error, Dev B fixes `03_load.sql`, everyone re-runs from step 5.

**10:30.** Split. Each developer opens their column in the Day 1 table and works it. You check in at 13:00 and 17:00 in the channel, nowhere else.

**What to watch for as the lead**
- The 248-member numbers above came from this kit on a MySQL stand-in. SingleStore should reproduce them exactly; if a number differs, that is the finding to chase, not to explain away. What must never differ: `current_needs_without_action` is 0, a plain re-run adds nothing, holdout members have no contact.
- Dev A's Trig1 decision (6.5% from the extract flag or 8% from the rulebook) needs the clinical lead in the room, not a developer's guess. Get that answer before 13:00.
- The demo member is s26. Reset him between rehearsals. Do not let the rehearsals drift onto different members.
- If SingleStore rejects a statement, the fix goes in the SQL file in the repo, not in someone's terminal history.
- In front of the GCEO, Dev C drives and nobody types a value. Every number on screen came from the extract or from a nurse click.

---

## About the snapshot

The 248-member file (`demo_csv.csv`, comma-separated, 339 columns, no member id) is prepared and included as `data/member_features_250.tsv`: `tools/add_ids.py` added a pseudonymous `mask_id` (s1 … s248) and the empty rank column so it matches the 341-column layout the loader expects, and it loads with `03_load.sql` unchanged. The kit was run on it end to end here: load, rules, plans, worklist, the s26 nurse chain, re-run and reset. Two data notes for Dev B: 167 of 248 have no usable blood pressure (so 86 members read *cannot tell* on the BP treatment-review rule, which the nurse asks about once), and the two `#VALUE!` cells in the priority column load as NULL. The file is real, masked member data: it stays inside the approved SingleStore workspace and the private repo.
