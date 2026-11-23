# Chronic Care Loop · front-end element → column mapping, and the data model

Every element on the three Studio screens and on the Care Coordinator Portal, mapped to the table and column that feeds it in the SingleStore kit, with the rulebook section it comes from. Built from the uploaded `Chronic-Care-Studio_Updated.html` (identical in content to the kit's Studio; only the colours changed), the 248-member `demo_csv.csv`, and the CCC Rulebook of 20 Nov 2026.

**How to read the Status column.** *Ready*: the column exists and the kit fills it today. *Derived*: computed in SQL from columns that exist (the formula is named). *Rule table*: comes from a rule row, not from member data. *Not in extract*: the screen shows it, the data does not have it; the demo either hides it or labels it as not available. *Post-demo*: needs a table the kit does not have yet.

The same mapping is in `mapping/ui_to_column.csv` for anyone who wants to sort or filter it.

## Part A · Studio screen 1: cohort and campaign builder

| Element on screen | Shown as | Source table.column | Rulebook | Status |
|---|---|---|---|---|
| Start from: Daman members | radio, with base count | `member` (`COUNT(*)`) | §2 builder inputs | Ready |
| Start from: SEHA patients, PURA app users | radios with counts | no table | §2 (other populations) | Not in extract: hide or show 0 |
| Rule: Age | between | `member.age` (from `AGE`) | §2 Who they are | Ready |
| Rule: Gender | Female / Male | `member.gender` (`GENDER`) | §2 | Ready |
| Rule: Plan | Enhanced / Basic / Thiqa | `member.plan_name` (`plan_name`) | §2 | Ready (values differ: Enhanced Bronze, Sahtak, Premier …; use the real list) |
| Rule: Region | Abu Dhabi / Al Ain / Al Dhafra | none | §2 | Not in extract |
| Rule: Has condition (ICD-10 family) | chips: T2D, HTN, dyslipidaemia, obesity, CKD, HF … | `member.has_t2d` (`cohort_t2d_l12m`), `member.has_htn` (`cohort_htn_l12m`), `flag_dyslipidemia_l12m`, `flag_obesity`, `flag_ckd`, `flag_heart_failure`, `flag_stroke`, `flag_ischemic_heart_disease`, `flag_pad_l12m` | §2 Health | Ready for these 9; other families Not in extract |
| Rule: Chronic conditions ≥ N | number | derived: count of the condition flags above | §2 | Derived |
| Rule: Latest result (HbA1c, eGFR, UACR, BP, BMI) | lab + operator + value | `last_hba1c_value`, `last_egfr_value`, `last_uacr_value`, `last_systolicpressure_value`, `last_diastolicpressure_value`, `last_measuredbmi_value` | §2 Tests & results | Ready (LDL, TSH Not in extract) |
| Rule: Test overdue (no result in N days) | lab + days | `DATEDIFF(run_config.as_of, last_hba1c_date2 / last_egfr_test_date / last_urine_albumin_date / last_lipid_panel_date / last_potassium_date)` | §2 | Derived |
| Rule: ED visits · 12 months | number | `member.ed_visits_l12m` | §2 Visits & admissions | Ready |
| Rule: Unplanned admissions | number | `member.ip_admissions_l12m` | §2 | Ready |
| Rule: No outpatient visit ≥ N days | days | `DATEDIFF(as_of, member.last_visit_date)` | §2 | Derived |
| Rule: Takes medicine class (ATC) | chips | `flag_active_insulin`, `flag_active_aceinhibitor`, `flag_active_arbinhibitor`; the extract also has `active_drug_classes` text (not loaded yet) | §2 Medicines | Ready for 3 classes; load `active_drug_classes` for the rest |
| Rule: Adherence (PDC) ≤ % | percent | `LEAST(pdc_any_t2d_noninsulin, pdc_any_htn)` | §2 | Derived |
| Rule: Eye exam not on record (24 months) | yes/no | `member.last_retinal_screen_date` (NULL or > 730 days) | §2 Screenings; Trig12 | Derived |
| Rule: Foot exam not on record (12 months) | yes/no | `member.last_foot_exam` (NULL or > 365 days) | §2; Trig13 | Derived |
| Rule: Visits in network ≤ % | percent | extract `phg_share_l12m_encounters` (not loaded yet) | §2 Network & cost | Ready once loaded |
| Rule: Claims cost · 12 months ≥ AED | amount | `member.l12m_payable_diaborhtnrelated` | §2 | Ready |
| Rule: Active on PURA | yes/no | none | §2 Engagement | Not in extract |
| Rule: Opted out of contact | yes/no | `member.consent = 'declined'` | §2; G2 | Derived |
| Rule: Currently pregnant | yes/no | extract `flag_excl_pregnant_postpartum` (not loaded yet) | §2 exclusions | Ready once loaded |
| Rule: Active cancer treatment | yes/no | extract `flag_oncology_l12m` (not loaded yet); `member.excluded` already folds all exclusion flags | §2 exclusions | Ready via `excluded` |
| Include members who match all / any | toggle | `campaign.rules_json` (logic), compiled into `campaign.where_sql` | §2 | Ready |
| Exclude anyone who … | rule rows | same, as `NOT (…)` in `where_sql` | §2 | Ready |
| Who you've got: count, % of base | number | `POST /cohorts/estimate` → `COUNT(*)` over `member` with `where_sql` | §2 | Ready |
| Who you've got: step bars (one per rule) | bars | same endpoint, one count per prefix of the rules | §2 | Ready |
| Profile tab: age bands, gender | bars | `member.age`, `member.gender` grouped | §2 | Ready |
| Who matches tab: sample members | list | `member_id`, `age`, `gender`, `plan_name` (10 rows) | §2 | Ready (pseudonym from `member_id`) |
| Overlap tab | bars | counts against other saved cohorts' `where_sql` | §2 | Post-demo: needs the `cohort` table (below) |
| Describe who you want to find / Feature catalogue / Query the knowledge graph | text, matches, traversal | none in the kit | §2 written nGQL | Post-demo (knowledge graph not in the two days) |
| Generated nGQL · read-only; Checks (read-only, space, starts from Member, returns member_vid, known schema, bounded path, inputs only) | code, 7 ticks | kit compiles SQL instead; the 7 guardrails map to the `compile_rule` whitelist | §2 seven guardrails | Derived (SQL, not nGQL) |
| Cohorts library: id, version, name, definition, size, refresh, owner, source | cards | `cohort` table (proposed, below) | §2 "Loading writes a row to COHORT" | Post-demo for the library; today a cohort is saved inside `campaign` |
| Size, last 12 weeks | sparkline | `cohort_size_history` (proposed) | §2 nightly run | Post-demo |
| Campaign: name, goal | text | `campaign.name`; goal: add `campaign.goal` | §2 | Ready / add column |
| Campaign: include cohorts, leave out anyone already in | pickers | `campaign.where_sql`; exclusion as `NOT IN (SELECT member_id FROM campaign_member WHERE campaign_id = …)` | §2; G3 one owner campaign | Ready |
| Campaign: Which needs? All DoH triggers / Pick triggers | toggle + chips | `campaign.trigger_mode` (all / list), `campaign.trigger_list` | §3 automated vs business mode | Ready |
| Campaign: Channels (Voice, WhatsApp, SMS) | chips | `rule_priority.channel` decides call vs nudge; campaign channel is display only | §4 P4 digital nudge | Rule table |
| Campaign: Priority | 1–n | `campaign.priority` | §4 "campaign priority" in queue order | Ready |
| Campaign: Nurses, Calls per nurse a day | sliders | `nurse` rows, `nurse.daily_capacity` | §4 worklist capacity | Ready (from setup, not from the slider) |
| Campaign: Control group % | slider | `campaign.holdout_pct` → `campaign_member.holdout` by CRC32 | §2 stable-hash 10% holdout | Ready |
| Campaign: Start, Weeks, Calendar next 16 weeks | date, number, strip | add `campaign.start_date`, `campaign.weeks`; calendar is derived from `rule_cadence` by tier | §2 cadence | Add 2 columns; calendar Derived |
| Hand off to care intelligence | button | `POST /campaigns` then `POST /runs/rules` | §1 Cohort → Intelligence | Ready |

## Part B · Studio screen 2: care intelligence

| Element on screen | Shown as | Source table.column | Rulebook | Status |
|---|---|---|---|---|
| Filter: Everyone · Urgent · Priority · Routine | pills with counts | `member.alert`: Urgent = RED, Priority = AMBER, Routine = YELLOW or GREEN | §4 alert colour, tree step G | Derived |
| Member list: initials, name | text | pseudonym from `member.member_id` (names are not in the extract) | — | Derived (name generator or "Member s26") |
| Member list: reason (one line) | text | `rule_trigger.name` of the member's lowest-class fired rule: `member_signal` ∩ `care_plan_need` slot CURRENT, min `class_order`, `trigger_order` | §4 within-member order | Derived |
| Member list: R score | number | `member.r_total` | §2 R = C+M+K+U+A | Ready |
| Member list: tier label | Low / Moderate / High / Very high | `member.tier` → `rule_tier.label` | §2 tier table | Ready |
| Member list: alert chip (Urgent · clinician today / Priority · within 72 h / Routine) | chip | `member.alert` → label; response text from §4 alert table | §4 | Derived |
| Member list: "queued" / "updated tonight" | badge | `worklist` row exists / `outcome` recorded since last run | §1 next iteration | Derived |
| Header: mask, age, sex, conditions, plan | text | `member.member_id`, `age`, `gender`, condition flags (`has_t2d`, `has_htn`, `flag_ischemic_heart_disease`, `flag_dm_retinopathy_l12m`, `flag_dm_neuropathy`), `plan_name` | — | Ready |
| Header: tier chip | Tier 4 · Very high | `member.tier`, `rule_tier.label` | §2 | Ready |
| Header: priority chip (Priority · within 72 h) | chip | `member.alert` + `member.contact_priority` (P1 same day, P2 next day, P3 3 days) | §4 contact SLA | Ready |
| Risk score R / 23 | number | `member.r_total` | §2 | Ready |
| Risk component: Clinical (cap 5) | bar | `member.clinical_score` (extract `Clinical_score`) | §2 C | Ready (extract-computed; the kit trusts the extract's components) |
| Risk component: Comorbidity (cap 6) | bar | `member.comorbid_complication_score` | §2 M | Ready |
| Risk component: Kidney (cap 5) | bar | `member.kidney_score` | §2 K | Ready |
| Risk component: Hospital use (cap 5) | bar | `member.utilization_score` | §2 U | Ready |
| Risk component: Age and sex (cap 2) | bar | `member.age_sex_score` | §2 A | Ready |
| "Kidney is provisional: no eGFR on record" | note | `member.last_egfr_value IS NULL AND last_uacr_value IS NULL` | §2 K fallback "shown as provisional" | Derived |
| Why now: title and detail | text | top fired rule: `rule_trigger.name`, `member_signal.evidence` | §3 | Ready |
| Wearable early warning: band, score, prediction, window, drivers | card | none | not in the rulebook; not in claims | Not in extract: show "No wearable feed in the claims extract" (already does) |
| Care plan, in order · safety first | numbered list | `care_plan_need` ordered by `class_order`, `trigger_order`; first 3 = CURRENT | §4 safety → acute → uncontrolled → barrier → verified gap → patient goal; step I | Ready |
| Care plan row: class pill (Safety, Acute, Uncontrolled, Barrier, Care gap, Goal) | pill | `care_plan_need.class` → `rule_trigger.class_label` | §3 Class column | Rule table |
| Care plan row: title (next best action) | text | `rule_trigger.action_title` (from `rules/rule_action.csv`) | §3 Next best action | Rule table |
| Care plan row: why (evidence) | small text | `care_plan_need.evidence` (copied from `member_signal.evidence`) | §3 Raw data read / Fires when | Ready |
| Care plan row: reference (DoH guideline / technical ref) | small text | `rule_trigger.raw_data`, `rule_trigger.fires_when`; the DoH anchor is in the rulebook text | §3 | Rule table |
| Care plan row: owner | For nurse / Coordinator / Doctor | `rule_trigger.owner_role` | §3 Owner | Rule table |
| Care plan row: status (For nurse · Waiting · Done on call · Done, confirm in claims · Declined, again in 90 d · Call back) | text | `care_plan_need.slot` (CURRENT = For nurse, NEXT/FUTURE = Waiting), `care_plan_need.gap_state` (Reported = confirm in claims), `care_plan_need.status` + `hold_until` (declined), latest `outcome.result` (callback) | §5 write-back; gap states Potential → Verified → Scheduled → Reported → Closed | Ready |
| "Top 3 go to the nurse · rest wait their turn" | caption | `care_plan_need.slot` | step I ≤ 3 needs | Ready |
| Next best action (one line) | text | first CURRENT need's `action_title` | §3 | Ready |
| Language, call slot, preference | text | `member.language` (derived from nationality); slot and preference: none | §4 language match | Language Derived; slot/preference Not in extract (slot = `worklist.due_by` is the honest substitute) |
| Send to nurse's call list / Open in care portal | button | `worklist` row (`nurse_id`, `status`) | §4 | Ready |
| Filter counts (Everyone 21 etc.) | numbers | `COUNT(*)` over `member` by `alert`, restricted to campaign members | §4 | Derived |
| Programme view (all rules across members): in scope, fired, cannot tell, open, in CURRENT, reported by nurse, closed in claims | table | `v_rulebook_programme` | §3 trigger states; §5 gap closes only in claims | Ready |

## Part C · Studio screen 3 and the Care Coordinator Portal (nurse)

The embedded screen 3 is the portal file in an iframe, so one mapping covers both.

| Element on screen | Shown as | Source table.column | Rulebook | Status |
|---|---|---|---|---|
| Nudge queue: tabs Today · This week · This month | counts | `worklist.status = 'today'`; week/month = `worklist.status = 'queued'` by `due_by` | §4 capacity, queued rolls over | Ready |
| Queue row: name, reason, Risk, Priority, segment letter, Consent needed, Next follow-up (overdue · date) | card | pseudonym; `worklist.reason` (lead action title); `member.r_total` (shown out of 23, not 0–100); `member.contact_priority`; segment A/B = in PHG network or not (extract `t2d_category` text, not loaded yet); `member.consent`; `worklist.due_by` and overdue if `< run_config.run_date` | §4 queue order | Ready, except segment (load `t2d_category`) |
| Queue order | sort | `worklist.rank_no`, `nurse_rank` | §4: safety/RED → tier → campaign priority → hours past SLA | Ready |
| Member header: name, flags (Out of network, segment), Risk, Priority, age, sex, language, plan, "Claims extract · pseudonym · masked m26" | header | `member.member_id`, `age`, `gender`, `language`, `plan_name`, `r_total`, `contact_priority` | — | Ready |
| Call button / Dialling / On call timer / End call | call bar | `action` (kind call) for the member; the call itself is simulated | §5 Connect; G3 14-day cap | Ready (telephony out of scope) |
| Why we're calling · class · title · one-line evidence | card | top CURRENT need: `rule_trigger.class_label`, `name`, `care_plan_need.evidence` | §5 Prepare: why → do → done-when | Ready |
| Numbers strip: admissions · ER, HbA1c vs target, adherence, AED claims | tiles | `member.ip_admissions_l12m`, `ed_visits_l12m`, `last_hba1c_value` (target from rule: < 7, individual goal 8), `LEAST(pdc …)`, `l12m_payable_diaborhtnrelated` | §2 | Ready |
| Urgent banner ("check for same-day referral first") | red banner | `member.alert = 'RED'` or a CURRENT need of class safety | step B urgent?; §4 RED response | Derived |
| Also open: chips | chips | the member's other `care_plan_need` rows with `status = 'open'`, by class order | §4 | Ready |
| Consent card: toggle, Declined, Log consent; "Recorded call only" | card | `member.consent` (pending / granted / declined), written with the outcome (`outcome.consent`) | §5 consent gate G2; tree step D | Ready |
| Locked block "Profile · actions · care gaps · outcome: unlocks when consent is logged" | lock | `member.consent <> 'granted'` → the API still returns the data; the screen must not render it (rulebook: not rendered, not hidden) | G2 | Ready (rule enforced on screen; optional: API returns 403 before consent) |
| Review for this call: conditions (with ICD, "on claims") | rows | condition flags → ICD label (`has_t2d` E11, `has_htn` I10, `flag_ischemic_heart_disease` I25, `flag_dm_retinopathy_l12m` E11.3, `flag_dm_neuropathy` E11.4) | §5 Assess; step E | Ready |
| Review: medications with % covered | rows | extract `active_drug_classes`, `pdc_metformin`, `pdc_sglt2`, `pdc_dpp4`, `pdc_glp1`, `pdc_sulfonylurea`, `pdc_acei`, `pdc_arb`, `pdc_ccb`, `pdc_beta_blocker` (only `pdc_any_*`, `pdc_mra`, `pdc_thiazide` loaded today) | §3 Trig9 raw data | Ready once the per-class PDC columns are loaded (one line each in `tools/gen_sql.py` MEMBER_COLS) |
| Review: latest labs (HbA1c, eGFR, BP, BMI) with date and target | rows | `last_hba1c_value` + `last_hba1c_date2`, `last_egfr_value` + `last_egfr_test_date`, BP values + `last_systolicpressure_date`, BMI | §3 | Ready |
| Review buttons: Correct · Note · remove; Member confirmed all; Add history | buttons | `outcome.notes` (free text) for the demo | §5 Member assertion (MEMBER_ASSERTION) | Derived for demo; Post-demo: `member_assertion` table |
| "8 to review" / progress bar | counter | count of review rows above | — | Derived |
| Care plan actions to agree: numbered cards, Best fit, "For <need> · <evidence>", owner chip, channel chip | cards | the 3 CURRENT `care_plan_need` rows and their open `action` (kind care_plan): `rule_trigger.action_title`, `owner_role`, `channel`, `care_plan_need.evidence` | §3; step I | Ready |
| Ask script line ("When can you go for …") | text | add `rule_action.ask_script` (one line per action) | §5 script order why → do → done-when | Add column (rule table) |
| Booking widget: date, time, Recommended by <date>, Confirm booking / Send to DAWAK | calendar | agreed date → `outcome.notes` and follow-up `action.due_date`; "recommended by" = `care_plan_need.due_date` (class due days: acute 3, uncontrolled or barrier 7, gap 30) | §5 Done row: due by class | Ready (date); DAWAK/refill integration Not in scope |
| Guardrail text under a card ("Do not label non-adherence …") | note | add `rule_action.guardrail_text` | §3 Trig9 branch "reason not yet known" | Add column (rule table) |
| Member agrees / Agreed | button | `POST /actions/{id}/outcome` result = agreed → `care_plan_need.gap_state = Scheduled`, follow-up "check it happened" | §5 write-back | Ready |
| Outcome: Member's response (auto: Actions agreed · 2) | card | derived from the outcomes recorded this call | §5 | Derived |
| Outcome: next steps list (Agreed with member / Care plan action / Follow-up call), assigned to, date | list | `action` rows created by `05_followup.sql`: `kind`, `title`, `assignee`, `due_date`, `parent_action_id` | §5 write-back table; step J | Ready |
| Follow-up call "in about 7 days" with the gap picker | row | `rule_followup.followup_due_days` and the member's tier cadence (`rule_cadence`) | §5 Follow up; §2 cadence | Ready |
| Save outcome and write back | button | the outcome call commits; `v_kpis` moves; next run re-slots | §1 write-back → next iteration | Ready |
| Member 360 header: Priority, consent status, nationality, plan | header | `member.contact_priority`, `consent`, `nationality`, `plan_name` | — | Ready |
| Member 360 tiles: risk, admissions · ER, claims cost, open triggers | tiles | `r_total`, `ip_admissions_l12m`, `ed_visits_l12m`, `l12m_payable_diaborhtnrelated`, `COUNT(member_signal fired)` | §2 | Ready |
| Member 360 journey bar: Flagged → Contacted → Consent → Reviewed → Actions → Outcome → Follow-up | steps | `member_signal` (flagged, run date); `outcome.reached`; `member.consent`; notes present; count of outcomes this call; outcome saved; open `action` of kind follow_up | decision tree A–J | Derived |
| Member 360 timeline: upcoming and past items | list | `v_action_chain` (`action` + `outcome` by date) | step J documentation | Ready |
| Care plans page: member list with alert colour, tier, R | list | `member.alert`, `tier`, `r_total` | §4 | Ready |
| Care plan page: Risk 13/23 with components and "kidney provisional" | card | as screen 2 | §2 | Ready |
| Care plan page: Decision path A–J with answers | tiles | A `worklist.nurse_id`; B `alert = RED` or safety need; C `outcome.reached`; D `consent`; E any new `member_signal` since last call; F `has_t2d`/`has_htn`; G `alert`; H `contact_priority`; I count of CURRENT needs; J outcome saved | tree A–J | Derived |
| Care plan columns CURRENT · NEXT · FUTURE with counts | columns | `care_plan_need.slot` | §4 | Ready |
| Care plan card: class pill, due ("Yesterday", "In 6 days"), title, owner, done-when, trigger code, pathway | card | `rule_trigger.class_label`, `care_plan_need.due_date`, `action_title`, `owner_role`, `done_when`, `trigger_code`, `pathway` | §3 all columns | Ready |
| Care plan card: "Action · <date> · <nurse>" and Open in Actions | link | the need's open `action`: `assignee`, `created_at`, `action_id` | G7 | Ready |
| Care plan card buttons Done · Declined · Not reached | buttons | `POST /actions/{id}/outcome` with result done / declined / not_reached | §5 write-back table | Ready |
| "Becomes an action when it reaches Current" | caption | `slot IN ('NEXT','FUTURE')` | G7 | Ready |
| Actions page: Backlog · overdue, Today, Upcoming, Done tiles | tiles | `action` by `due_date` vs `run_config.run_date` and `status` | — | Ready |
| Actions page: filters (All, Agreed with member, Care plan, Check-in calls, Callbacks, Retries) | pills | `action.kind` (care_plan, follow_up, retry, call, nudge, escalation) and the originating `outcome.result` | §5 | Ready |
| Actions page: calendar and list; task rows with member, Agreed / Not agreed, Book, Open | rows | `action.member_id`, `title`, `due_date`, `assignee`, `parent_action_id`; agreed = parent outcome result agreed | §5 | Ready |
| Analytics page | charts | `v_kpis`, `v_rulebook_programme` | §5 "gap closes only in claims" | Ready |
| Wearables page | charts | none | not in rulebook | Not in extract: hide for the demo |
| Shift · 0 of 10 done | counter | `worklist` rows for the nurse with the lead action closed today | §4 | Derived |

## Part D · Column load list (one-time, Dev B, 20 minutes)

These extract columns are referenced above but not yet in `member`. Add them to `MEMBER_COLS` in `tools/gen_sql.py`, regenerate, reload: `active_drug_classes`, `t2d_drug_classes_l12m`, `htn_drug_classes_l12m`, `pdc_metformin`, `pdc_sglt2`, `pdc_dpp4`, `pdc_glp1`, `pdc_sulfonylurea`, `pdc_acei`, `pdc_arb`, `pdc_ccb`, `pdc_beta_blocker`, `phg_share_l12m_encounters`, `t2d_category`, `htn_category`, `flag_excl_pregnant_postpartum`, `flag_oncology_l12m`, `last_ip_facility`, `last_ip_dx_desc`, `last_ed_dx_desc`, `last_claim_date`, `last_claim_medicines`, `dm_complications`, `ckd_stage_l12m`, `Risk_tier`, `Persona` (already as `persona`).

Three rule-table columns to add (Dev A, in the CSVs): `rule_action.ask_script`, `rule_action.guardrail_text`, `campaign.goal`. Two campaign columns: `start_date`, `weeks`.

## Part E · The data model

Nineteen tables in the kit today, plus two proposed for the builder's cohort library. Rule tables are REFERENCE (copied to every SingleStore node). Member tables are ROWSTORE sharded by `member_id`. There are no foreign keys on SingleStore; the arrows below are the joins the SQL and the views make.

```
 RULES (REFERENCE, from rules/*.csv)                   CARE TEAM AND CAMPAIGNS (REFERENCE)
 ┌──────────────────────┐                              ┌────────────────┐  ┌─────────────────┐
 │ rule_trigger         │ 14 rows, one per rule        │ nurse          │  │ nurse_language  │
 │  trigger_code PK     │ class · class_order ·        │  nurse_id PK   │◀─│  nurse_id, lang │
 │  name, pathway,      │ trigger_order · due_days ·   │  name, role,   │  │  lang_idx       │
 │  class, class_label  │ raw_data · fires_when ·      │  daily_capacity│  └─────────────────┘
 │  action_code, title, │ owner_role · channel ·       └────────────────┘
 │  owner_role, channel │ done_when · evidence ·       ┌─────────────────────────────┐
 │  done_when, status   │ escalate_to · use_variant    │ campaign                    │
 └──────────┬───────────┘                              │  campaign_id PK, name,      │
            │ trigger_code                             │  status, priority,          │
 ┌──────────┴───────────┐ ┌──────────────┐ ┌─────────┐ │  trigger_mode, trigger_list,│
 │ rule_priority        │ │ rule_tier    │ │rule_    │ │  rules_json, where_sql,     │
 │  alert + needs_trig  │ │  tier, label,│ │cadence  │ │  holdout_pct, created_at    │
 │  → priority, sla_days│ │  r_min, r_max│ │ tier,   │ │  (+ goal, start_date, weeks)│
 │  channel, match_order│ └──────────────┘ │ step,   │ └──────────────┬──────────────┘
 └──────────────────────┘                  │ day_off │                │ campaign_id
 ┌──────────────────────┐ ┌──────────────┐ └─────────┘ ┌──────────────┴──────────────┐
 │ rule_followup        │ │ run_config   │             │ campaign_member             │
 │  outcome → action_   │ │  as_of,      │             │  member_id, campaign_id PK  │
 │  status, need_status,│ │  run_date    │             │  holdout (CRC32 % 100 < pct)│
 │  gap_state, hold_days│ └──────────────┘             │  added_on                   │
 │  followup_kind/title/│                              └──────────────┬──────────────┘
 │  due_days, max_      │   proposed:  cohort (cohort_id PK, name,    │ member_id
 │  attempts, promote   │   version, base, rules_json, where_sql,     │
 └──────────────────────┘   refresh, owner, source, n_last, created)  │
                            cohort_size_history (cohort_id, day, n)  │
 MEMBER DATA (ROWSTORE, SHARD KEY member_id)                         │
 ┌───────────────┐  03_load  ┌──────────────────────────────────────┴─┐
 │ stg_extract   │ ────────▶ │ member                                 │
 │ 341 TEXT cols │   (G0)    │  member_id PK                          │
 │ mask_id       │           │  who: gender, age, nationality, plan,  │
 └───────────────┘           │       language, excluded, persona      │
                             │  scores: clinical, comorbid, kidney,   │
                             │       utilization, age_sex, total      │
                             │  flags: has_t2d, has_htn, 30 condition │
                             │       and medicine flags, 13 Trig flags│
                             │  labs: last_* values and dates         │
                             │  use: ed_visits, ip_admissions, cost   │
                             │  written by the run: r_total, tier,    │
                             │       alert, contact_priority,scored_on│
                             │  written by the portal: consent        │
                             └──┬───────────┬──────────────┬──────────┘
            step 2 (rules)      │           │              │
 ┌──────────────────────────────┴┐  ┌───────┴────────────┐ │
 │ member_signal                 │  │ worklist           │ │  step 8
 │  member_id, trigger_code,     │  │  work_date,        │ │
 │  run_date PK                  │  │  member_id PK      │ │
 │  state fired|cannot_tell      │  │  nurse_id, rank_no,│ │
 │  evidence                     │  │  nurse_rank,       │ │
 └──────────────┬────────────────┘  │  action_id, reason,│ │
     step 4     │                   │  priority, alert,  │ │
 ┌──────────────┴────────────────┐  │  tier, due_by,     │ │
 │ care_plan_need                │  │  status today|     │ │
 │  member_id, trigger_code PK   │  │  queued            │ │
 │  class, class_order,          │  └────────▲───────────┘ │
 │  trigger_order                │           │ action_id   │
 │  slot CURRENT|NEXT|FUTURE|    │  ┌────────┴────────────┴──────────────┐
 │       CLOSED                  │  │ action                              │
 │  status open|done|declined    │  │  member_id, action_id PK            │
 │  gap_state Potential|Verified|│◀▶│  trigger_code (null for calls)      │
 │       Scheduled|Reported|     │  │  kind nudge|call|care_plan|follow_up│
 │       Closed                  │  │       |retry|escalation             │
 │  due_date, hold_until,        │  │  title, channel, owner_role,        │
 │  evidence, opened_on,         │  │  assignee (nurse_id), due_date,     │
 │  closed_on                    │  │  status open|done|cancelled,        │
 └───────────────────────────────┘  │  attempt, parent_action_id,         │
                                    │  created_by, created_at, closed_at  │
                                    └────────▲───────────────────────────┘
                                             │ action_id
                                    ┌────────┴───────────────────────────┐
                                    │ outcome                             │
                                    │  member_id, outcome_id PK           │
                                    │  action_id, trigger_code, result    │
                                    │  reached, consent, notes, nurse_id, │
                                    │  recorded_at                        │
                                    └─────────────────────────────────────┘
 work_member, work_rank: scratch tables the run truncates and refills.
```

**Which screen reads which table**

| Table | Screen 1 builder | Screen 2 intelligence | Portal |
|---|---|---|---|
| `member` | counts, profile, sample | header, risk, components | header, 360, review, labs |
| `rule_trigger` (+ `rule_action` columns) | trigger picker | class, title, owner, done-when | why we're calling, action cards, care plan cards |
| `member_signal` | — | why now, evidence, flagged | journey "Flagged", also-open |
| `care_plan_need` | — | care plan in order, slots, status | care plan page, actions to agree, gap state |
| `action` | — | queued badge, NBA | call bar, next steps, actions page, timeline |
| `outcome` | — | updated-tonight badge | journey, response, timeline, decision path C/D/J |
| `worklist` | — | send to call list | nudge queue, shift counter |
| `campaign`, `campaign_member` | library, editor, hand-off | filter counts | queue order (campaign priority) |
| `nurse`, `nurse_language` | nurses slider (display) | — | nurse picker, assignee |
| `rule_priority`, `rule_tier`, `rule_cadence`, `rule_followup` | calendar strip | tier label, priority chip | due dates, follow-up dates, retries |
| `v_rulebook_member`, `v_rulebook_programme` | — | rulebook tab, programme page | rulebook tab |
| `v_kpis` | — | — | analytics |

**The order the rulebook fixes, and where it lives.** Within a member, needs are ordered safety → acute event → uncontrolled → barrier → verified gap → patient goal. That order is `rule_need_class.sort_order` in the CSV, copied into `rule_trigger.class_order`, copied into `care_plan_need.class_order` when a need opens, and used by the `ROW_NUMBER()` that assigns CURRENT (1–3), NEXT (4–6) and FUTURE. Across members, the queue order is `worklist.rank_no`: urgent (RED or safety) first, then tier 4 → 1, then campaign priority, then due date. Nothing on any screen sorts on its own.
