# Chronic Care Loop · three deliverables, three developers, two days

Everything below is already written and tested in this folder on a MySQL stand-in for SingleStore. The two days are for running it on **your** SingleStore, owning one layer each, loading the 250-member snapshot, wiring the three apps, and demoing. Nobody starts from a blank file.

The loop, and who owns which part of it:

```
raw extract ─▶ member ─▶ [1 RULE LAYER] rules fire, score, alert, priority
                              │
                              ▼
                 [2 MEMBER 360] care-plan need ─▶ action ─▶ nurse outcome ─▶ follow-up
                              │
                              ▼
                 [3 WORKLIST ORCHESTRATION] campaign ─▶ nudge / call ─▶ nurse list ─▶ KPIs
```

| | Deliverable 1 · Rule layer | Deliverable 2 · Member 360 | Deliverable 3 · Worklist orchestration |
|---|---|---|---|
| **Owner** | Dev A | Dev B | Dev C |
| **Question it answers** | Which rules fire for this member, and how urgent are they? | What is this member's plan, what did the nurse do, what happens next? | Who do we contact today, which nurse, in what order? |
| **Source of truth** | `rules/*.csv` (14 files) → `tools/gen_sql.py` | the extract → `03_load.sql` (G0 cleaning) | `02b_setup.sql` (nurses, languages, campaigns) |
| **SQL owned** | `02_rules.sql`; `04_nightly.sql` steps 2–3 | `01_schema.sql`, `03_load.sql`; `04_nightly.sql` steps 4–6; `05_followup.sql` | `04_nightly.sql` steps 1, 7, 8 |
| **Tables owned** | `rule_trigger` (14 rules, one row each), `rule_priority`, `rule_tier`, `rule_cadence`, `rule_followup`, `run_config`; writes `member_signal` and `member.r_total / tier / alert / contact_priority` | `stg_extract`, `member`, `care_plan_need`, `action`, `outcome` | `campaign`, `campaign_member`, `nurse`, `nurse_language`, `worklist` |
| **Views owned** | `v_rulebook_programme` | `v_member_summary`, `v_care_plan`, `v_rulebook_member`, `v_action_chain` | `v_worklist`, `v_kpis` |
| **API owned** | `GET /rules` · `GET /rulebook/programme` | `GET /members/{id}` · `/care-plan` · `/rulebook` · `/actions` · `POST /actions/{id}/outcome` | `POST /cohorts/estimate` · `POST /campaigns` · `POST /runs/nightly` · `GET /worklist?nurse=` · `GET /kpis` |
| **Screen wired** | Care Studio: programme page (every rule across members) | Care portal: member header, care plan, rulebook tab, timeline, the five buttons | Cohort & Campaign builder (count, hand-off); portal nudge queue; KPIs |
| **Must bake in** | `use_variant` switch per rule (extract flag vs rulebook threshold); `cannot_tell` when a value is missing (G8); every rule carries its sign-off status | exactly one open care-plan action per CURRENT need (G7); a gap closes **only** in claims; declined = 90-day hold; not reached = 3 attempts, P1 escalates; every follow-up keeps `parent_action_id` | holdout members are never contacted; one contact per member per day; no new contact within 14 days of a reached call; queue order RED/safety → tier → campaign priority → due; language match, then even split up to each nurse's capacity; escalations go to the lead, not the nurse list |
| **Done on the 24-member sample** | 152 fired / 7 cannot tell; per rule: Trig3 4 · BPU 1 · Trig4 15 · Trig1 17 · Trig2 6 · Trig5 19 · Trig9 16 · Trig6 8 · Trig12 7 · Trig13 13 · Trig7 1 · Trig11 21 · Trig10 2 · Trig8 22 | 21 care plans, 63 CURRENT needs, `current_needs_without_action = 0`; the m26 chain (reached → check-in 27 Nov; agreed → check 27 Nov; done → Reported + verify 4 Dec; declined → hold to 18 Feb + re-offer) | 21 on today's list: Omar 9, Sara 9, Nadia 3; nobody from the holdout; re-running the nightly adds no rows |
| **Done on the 250 snapshot** | same checks; write the counts down at the 10:30 checkpoint as the new baseline | same checks | same checks |
| **Test** | `tests/test_kit.py::test_triggers_match_reference_engine`, `test_rerun_is_idempotent` | `test_every_current_need_has_one_action`, `test_z_nurse_outcomes_create_follow_ups`, `test_zz_gap_closes_only_in_claims`, `test_load_and_g0_cleaning` | `test_worklist_rules`, `test_holdout_and_exclusions_get_no_needs` |

**Dependencies, in order:** load (Dev B) → rules (Dev A) → needs and actions (Dev B) → nudges and worklist (Dev C). All of it already runs as one script, so nobody waits: each developer reads their steps, runs the whole thing, and verifies their own layer.

---

## Action plan

### Hour 0 (together, 09:45–10:30)

1. Dev B creates database `ccl` on SingleStore and runs, in order: `01_schema.sql`, `02_rules.sql`, `02b_setup.sql`, `06_views.sql`.
2. Dev A prepares the snapshot: `python3 tools/add_ids.py <snapshot>.tsv data/member_features.tsv` (adds the pseudonymous `mask_id` the kit keys on), then Dev B runs `03_load.sql` from the `data/` folder.
3. Dev C starts the API (`cd api && S2_DB=ccl python3 server.py --port 8080`) and runs `curl -X POST localhost:8080/runs/nightly`.
4. Everyone runs `SELECT * FROM v_kpis;` and writes the row into the Teams thread. That row is the baseline for the two days.

### Day 1 (own your layer)

| | Dev A · Rule layer | Dev B · Member 360 | Dev C · Worklist |
|---|---|---|---|
| **AM** | Read `rule_trigger` row by row against the rulebook document. Run `04_nightly.sql` step 2 alone; compare `member_signal` counts per rule with the sample baseline. Decide Trig1 variant (extract 6.5% vs rulebook 8%) with the clinical lead; set `use_variant`. | Check `03_load.sql` on the snapshot: nulls, 999 placeholders, BP 1/1, dates. `SELECT * FROM v_member_summary` for 5 members and read them against the raw rows. | Edit `02b_setup.sql`: real nurse names, languages, daily capacity. Re-run step 8 and read `v_worklist` for each nurse. |
| **PM** | `EXPLAIN` steps 2–3 on SingleStore; fix anything the dialect rejects. Add one rule change end to end (edit CSV → `gen_sql.py` → re-run 02 and 04) to prove the path. | Walk the m26 chain through the API with curl: reached, agreed, done, declined. Read `v_action_chain` after each. | Walk a campaign through the API: `POST /cohorts/estimate`, `POST /campaigns`, `POST /runs/nightly`; confirm holdout members get no needs and no contact. |
| **17:00 checkpoint** | fired counts per rule match the engine on both datasets; one rule change proven | the m26 chain works through the API | a campaign hand-off produces a worklist; `v_kpis` unchanged after a re-run |

### Day 2 (wire the screens, demo)

| | Dev A | Dev B | Dev C |
|---|---|---|---|
| **AM** | Care Studio programme page ← `GET /rulebook/programme`. Studio ② member list header ← `GET /members/{id}`. | Portal member page: header ← `/members/{id}`, care plan ← `/care-plan`, rulebook tab ← `/rulebook`, timeline ← `/actions`; the five buttons → `POST /actions/{id}/outcome`. | Builder: live count ← `POST /cohorts/estimate`; hand-off → `POST /campaigns` then `POST /runs/nightly`. Portal nudge queue ← `GET /worklist?nurse=`. KPIs ← `/kpis`. |
| **PM** | Rehearse steps 5–6 of the demo. | Rehearse steps 3–4. | Rehearse steps 1–2; run the full 10-minute demo at 15:00 with the other two. |
| **17:00** | Demo. | | |

---

## Teams post (paste as is)

> **Chronic Care Loop · 2-day build starts tomorrow 09:30**
>
> We are putting the three apps (Cohort & Campaign Builder, Care Studio, Care Coordinator Portal) on a real SingleStore backend in two days. The SQL, the API and the tests already exist and pass on a MySQL stand-in. Our job is to run it on our SingleStore, own one layer each, load the 250-member snapshot, wire the screens, and demo on Day 2 at 17:00.
>
> **Before 09:30 tomorrow**
> 1. Get the kit: `CCL-2-Day-Build.zip` (pinned above) or the repo folder `two-day-build/`. Read `PLAN.md` once, 20 minutes, and `DELIVERABLES.md`.
> 2. Confirm you can log in to SingleStore and create a database. Install `mysql` client and `pip install pymysql`.
> 3. Do **not** load the data anywhere outside the approved SingleStore workspace. The snapshot is real, masked member data.
>
> **Layers**
> - **Dev A: Rule layer.** `rules/*.csv` → `02_rules.sql`, nightly steps 2–3, `v_rulebook_programme`, `GET /rules`, `GET /rulebook/programme`. You own "which rules fire and how urgent".
> - **Dev B: Member 360.** `01_schema.sql`, `03_load.sql`, nightly steps 4–6, `05_followup.sql`, `v_member_summary / v_care_plan / v_rulebook_member / v_action_chain`, the member endpoints and `POST /actions/{id}/outcome`. You own "the plan, what the nurse did, what happens next".
> - **Dev C: Worklist orchestration.** nightly steps 1, 7, 8, `02b_setup.sql`, `v_worklist`, `v_kpis`, the campaign, nightly, worklist and KPI endpoints. You own "who we contact today, which nurse, in what order".
>
> **Tomorrow**
> - 09:30 kickoff (45 min): the loop on one member, the three layers, the rules we don't break.
> - 09:45–10:30 together: database up, rules in, snapshot loaded, first nightly run, `v_kpis` row posted here.
> - 13:00 and 17:00: 10-minute standup in this channel. Post your layer's numbers.
> - Day 2 17:00: demo.
>
> **Rules we don't break**
> - A rule changes only in `rules/*.csv`, then `tools/gen_sql.py`. No thresholds in app code or hand-edited SQL.
> - The apps never write to tables. Every nurse button is `POST /actions/{id}/outcome`.
> - A gap closes only when the claim arrives. A nurse's "done" makes it *Reported*, not *Closed*.
> - Every CURRENT need has exactly one open action. `v_kpis.current_needs_without_action` stays 0.
>
> Questions in this thread, not in DMs, so all three of you see the answer.

---

## Tomorrow morning: what you do, what you say, what each step looks like

**08:45. You.** Open `PLAN.html` and `DELIVERABLES.md` on the shared screen. Have the snapshot file ready in the workspace. Have the Teams post already posted (tonight).

**09:30–09:45. Kickoff, part 1: the loop on one member.** Open `PLAN.html` section 2 (m26). Say: *"This is one member. The raw extract says HbA1c 11, kidney tests missing, discharged recently. Ten rules fire. Three become CURRENT needs. Each need gets one action. The nurse calls him today. Whatever she records, the system creates the next action. The gap closes only when the claim arrives next month. Everything we build in two days is this picture, for 250 members, on SingleStore."* Scroll section 4 (action → follow-up) and section 5 (the rulebook view). Five minutes.

**09:45. Kickoff, part 2: the three layers.** Open `DELIVERABLES.md`, the big table. Read the "Question it answers" row aloud. Assign the owners. Say: *"All the SQL exists. Day 1 you run it, read your steps line by line against the rulebook, and prove your layer with the checks in your column. Day 2 you wire your screen."* Then the four rules we don't break. Five minutes.

**09:55–10:30. Hour 0, hands on, one screen.** Dev B drives, the other two follow on their machines.

| Step | Command | What you see when it worked |
|---|---|---|
| 1. Database and tables | `mysql -h … ccl < sql/01_schema.sql` | no output; `SHOW TABLES;` lists 19 tables (9 reference, 1 staging, 7 member tables, 2 scratch work tables) |
| 2. The rulebook as rows | `mysql ccl < sql/02_rules.sql` | `SELECT trigger_code, class_label, fires_when, action_title FROM rule_trigger ORDER BY class_order, trigger_order;` prints 14 rows in rulebook order, Trig3 first |
| 3. Nurses and campaigns | `mysql ccl < sql/02b_setup.sql` | `SELECT * FROM nurse;` shows the team; `SELECT * FROM run_config;` shows as-of 2026-10-31, run date 2026-11-20 |
| 4. Views | `mysql ccl < sql/06_views.sql` | `SHOW FULL TABLES WHERE table_type='VIEW';` lists 7 views |
| 5. The snapshot | `python3 tools/add_ids.py snapshot.tsv data/member_features.tsv` then `cd data && mysql --local-infile=1 ccl < ../sql/03_load.sql` | the script prints `wrote … 250 members, 341 columns`; `SELECT COUNT(*) FROM member;` returns 250; `SELECT member_id, age, language, last_hba1c_value FROM member LIMIT 5;` shows typed values, no 999s |
| 6. First nightly run | `cd api && S2_DB=ccl python3 server.py --port 8080 &` then `curl -X POST localhost:8080/runs/nightly` | JSON with the step timings; takes seconds |
| 7. The baseline row | `curl localhost:8080/kpis` | one JSON object: members 250, triggers_fired_today, members_with_plan, current_needs, **current_needs_without_action: 0**, on_todays_list. Paste it into Teams. |
| 8. One member, end to end | `curl localhost:8080/members/s1/rulebook` and `curl localhost:8080/worklist?nurse=U-0150` | the rulebook table for one member (14 rows, state and status per rule); a nurse's list, ranked, each row with the lead action and the due date |

If step 5 fails on a column, that is the first real finding of the day: post the error, Dev B fixes `03_load.sql`, everyone re-runs from step 5.

**10:30.** Split. Each developer opens their column in the Day 1 table and works it. You check in at 13:00 and 17:00 in the channel, nowhere else.

**What to watch for as the lead**
- The 250-member counts will differ from the 24-member sample. That is expected. What must not differ: `current_needs_without_action` is 0, a re-run adds nothing, holdout members have no contact.
- Dev A's Trig1 decision (6.5% from the extract flag or 8% from the rulebook) needs the clinical lead in the room, not a developer's guess. Get that answer before 13:00.
- If SingleStore rejects a statement, the fix goes in the SQL file in the repo, not in someone's terminal history.

---

## About the snapshot you sent

The 250-member snapshot pasted into chat has the same columns as the extract, but two things need handling before it loads:

- **It has no `mask_id` column** (the header starts at GENDER). The kit keys everything on `mask_id`. `tools/add_ids.py` adds a pseudonymous id (`s1 … s250`) and the empty rank column so the file matches the 341-column layout `03_load.sql` expects. If the original export does have an id column, use that file instead and skip the script.
- **It must arrive as a file, not as pasted text.** Pasting into chat turns tabs into spaces, and facility names and diagnoses contain spaces, so the pasted copy cannot be split back into columns reliably. Put the original `.tsv` in the SingleStore workspace and point step 5 at it.
