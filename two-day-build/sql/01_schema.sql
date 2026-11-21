-- ════════════════════════════════════════════════════════════════════════════════════
-- Chronic Care Loop · lean schema for SingleStore (MySQL-compatible)
-- Run once:  singlestore -h <host> -u <user> -p < 01_schema.sql
--
-- 8 working tables + 1 staging table + 10 rule/reference tables.
-- SingleStore notes baked in:
--   · REFERENCE tables (rules, nurses, campaigns) are copied to every node, so joins to them are free.
--   · Member-level tables are ROWSTORE and sharded by member_id; every primary key contains member_id.
--   · SingleStore does not enforce foreign keys. The relationships are listed in comments and
--     kept by the SQL itself (anti-joins in 04_nightly.sql, member-scoped writes in 05_followup.sql).
-- Relationships:
--   member 1─* member_signal · member 1─* care_plan_need · care_plan_need 1─1 action(kind='care_plan', open)
--   action 1─* outcome · action 1─* action (parent_action_id: the follow-up chain) · member 1─1 worklist (per day)
--   care_plan_need.trigger_code → rule_trigger (one row per rulebook rule)
-- ════════════════════════════════════════════════════════════════════════════════════
CREATE DATABASE IF NOT EXISTS ccl;
USE ccl;

-- ───────── Rules and reference (REFERENCE = replicated; edit rows, not code) ─────────
CREATE REFERENCE TABLE IF NOT EXISTS run_config (
  id        INT PRIMARY KEY,                -- always 1
  as_of     DATE NOT NULL,                  -- date the extract was computed for (31 Oct 2026)
  run_date  DATE NOT NULL                   -- "today" for the nightly run and the worklist
);
CREATE REFERENCE TABLE IF NOT EXISTS rule_trigger (       -- rulebook §3: trigger → next best action
  trigger_code   VARCHAR(10) PRIMARY KEY,   -- Trig1 … Trig13, BPU
  name           VARCHAR(60) NOT NULL,
  pathway        VARCHAR(20) NOT NULL,
  class          VARCHAR(10) NOT NULL,      -- safety | acute | unctl | barrier | gap | goal
  class_label    VARCHAR(20) NOT NULL,
  class_order    INT NOT NULL,              -- care-plan order (safety first)
  trigger_order  INT NOT NULL,
  due_days       INT NOT NULL,              -- a new need is due this many days after it opens
  raw_data       VARCHAR(200),              -- rulebook §3: the raw data the rule reads
  fires_when     VARCHAR(200),              -- rulebook §3: the condition, in words (the SQL is in 04_nightly.sql)
  extract_flag   VARCHAR(60),               -- the extract column that carries the same flag, if any
  action_code    VARCHAR(12) NOT NULL,      -- ACT-… (rules/rule_action.csv)
  action_title   VARCHAR(120) NOT NULL,     -- the next best action
  owner_role     VARCHAR(40) NOT NULL,
  channel        VARCHAR(30) NOT NULL,
  done_when      VARCHAR(120) NOT NULL,     -- verified in claims
  evidence       VARCHAR(120),
  escalate_to    VARCHAR(40),
  use_variant    VARCHAR(10) NOT NULL,      -- extract (the Trig flag) | rulebook (the thresholds)
  status         VARCHAR(120)               -- clinical sign-off state
);
CREATE REFERENCE TABLE IF NOT EXISTS rule_priority (      -- rulebook §4: alert → P1–P4 and SLA
  priority       VARCHAR(2) NOT NULL,
  alert          VARCHAR(6) NOT NULL,
  needs_trigger  VARCHAR(10) NOT NULL DEFAULT '',   -- e.g. AMBER + Trig4 (post-discharge) is P1
  sla_days       INT,                               -- NULL = digital nudge, no call
  channel        VARCHAR(20) NOT NULL,
  match_order    INT NOT NULL,                      -- first match wins
  PRIMARY KEY (priority, alert, needs_trigger)
);
CREATE REFERENCE TABLE IF NOT EXISTS rule_tier (
  tier   INT PRIMARY KEY, label VARCHAR(20) NOT NULL, r_min INT NOT NULL, r_max INT NOT NULL
);
CREATE REFERENCE TABLE IF NOT EXISTS rule_cadence (       -- contact cadence by tier (days after baseline)
  tier INT NOT NULL, step INT NOT NULL, day_offset INT NOT NULL, PRIMARY KEY (tier, step)
);
CREATE REFERENCE TABLE IF NOT EXISTS rule_followup (      -- rulebook §5: nurse outcome → what happens next
  outcome            VARCHAR(20) PRIMARY KEY,
  action_status      VARCHAR(10),           -- the action the nurse worked
  need_status        VARCHAR(10),           -- its care-plan need
  gap_state          VARCHAR(10),           -- Potential → Verified → Scheduled → Reported → Closed
  hold_days          INT,
  followup_kind      VARCHAR(12),           -- the new action it creates (NULL = none)
  followup_title     VARCHAR(120),          -- {done_when} {action} {attempt} are filled in
  followup_due_days  INT,
  max_attempts       INT,
  promote_next       TINYINT NOT NULL,
  note               VARCHAR(200)
);
CREATE REFERENCE TABLE IF NOT EXISTS nurse (
  nurse_id VARCHAR(10) PRIMARY KEY, name VARCHAR(60) NOT NULL, role VARCHAR(40) NOT NULL, daily_capacity INT NOT NULL
);
CREATE REFERENCE TABLE IF NOT EXISTS nurse_language (     -- worklist matching: language first (rulebook §4)
  nurse_id VARCHAR(10) NOT NULL, language VARCHAR(20) NOT NULL, lang_idx INT NOT NULL,   -- 1..n within the language
  PRIMARY KEY (language, lang_idx)
);
CREATE REFERENCE TABLE IF NOT EXISTS campaign (
  campaign_id   VARCHAR(12) PRIMARY KEY,
  name          VARCHAR(80) NOT NULL,
  status        VARCHAR(10) NOT NULL,       -- Draft | Live | Paused
  priority      INT NOT NULL,               -- 1 = first; a member belongs to the highest-priority live campaign
  trigger_mode  VARCHAR(4) NOT NULL,        -- all | list
  trigger_list  VARCHAR(200),               -- 'Trig9,Trig4' when trigger_mode = list
  rules_json    TEXT,                       -- the builder's rules, as saved
  where_sql     TEXT NOT NULL,              -- the compiled cohort filter over member (built by the API, whitelisted columns only)
  holdout_pct   INT NOT NULL DEFAULT 10,
  created_at    DATETIME NOT NULL
);

-- ───────── Raw extract (staging: every column as text, exactly as received) ─────────
CREATE ROWSTORE TABLE IF NOT EXISTS stg_extract (
  `mask_id` TEXT,
  `rank_PURECS_per_payable` TEXT,
  `GENDER` TEXT,
  `AGE` TEXT,
  `NATIONALITY` TEXT,
  `plan_name` TEXT,
  `policy_group` TEXT,
  `policy_type` TEXT,
  `cohort_t2d_l12m` TEXT,
  `cohort_htn_l12m` TEXT,
  `t2d_identified_by` TEXT,
  `htn_identified_by` TEXT,
  `t2d_category` TEXT,
  `htn_category` TEXT,
  `GWP` TEXT,
  `Risk Premium` TEXT,
  `Exclusion` TEXT,
  `P1_Complication` TEXT,
  `P2_Recurrent_ED_IP` TEXT,
  `P3_slipping` TEXT,
  `P5_newlydiagnosed` TEXT,
  `P3_offradar` TEXT,
  `P4_uncontrolled` TEXT,
  `Persona` TEXT,
  `Trig1_HbA1c_above_target` TEXT,
  `Trig2a_NoACEiARB_KidneyOrCAD` TEXT,
  `Trig2b_ACEi_plus_ARB` TEXT,
  `Trig2_HTN_tx_review` TEXT,
  `Trig3a_hypoglycemia_rev` TEXT,
  `Trig3b_glucagon_not_dispensed` TEXT,
  `Trig3_hypoglycemia_tx` TEXT,
  `Trig4a_NoFollowup_post_discharge` TEXT,
  `Trig4b_postdischarge_medsgap` TEXT,
  `Trig4_post_discharge_care` TEXT,
  `Trig5a_Kidney_screen_due` TEXT,
  `Trig5b_CKD_monitoring` TEXT,
  `Trig5c_Neph_due` TEXT,
  `Trig5_Kidney_check` TEXT,
  `Trig6_HbA1c_due` TEXT,
  `Trig7_Renal_Potassium_due` TEXT,
  `Trig8_nutrition_due` TEXT,
  `Trig9_medication_adherence` TEXT,
  `Trig10_new_diagnosis` TEXT,
  `Trig11_annual_labs_due` TEXT,
  `Trig12_eyeexam_due` TEXT,
  `Trig13_highriskfoot_monitor` TEXT,
  `# of triggers` TEXT,
  `HbA1c_score` TEXT,
  `Clinical_score` TEXT,
  `Comorbid_complication_score` TEXT,
  `eGFR + UACR points` TEXT,
  `Kidney_score` TEXT,
  `Utilization_score` TEXT,
  `Age_sex_score` TEXT,
  `Total_risk_Score` TEXT,
  `Risk_tier` TEXT,
  `Cohort_allocation` TEXT,
  `Priority_clinical_review` TEXT,
  `Last_HbA1c_Value` TEXT,
  `Last_HbA1c_Date` TEXT,
  `Last_SystolicPressure_Value` TEXT,
  `Last_SystolicPressure_Date` TEXT,
  `Last_DiastolicPressure_Value` TEXT,
  `Last_DiastolicPressure_Date` TEXT,
  `Last_MeasuredBMI_Value` TEXT,
  `Last_MeasuredBMI_Date` TEXT,
  `Last_eGFR_Value` TEXT,
  `Last_eGFR_Date` TEXT,
  `last_fastingplasmaglucose_value` TEXT,
  `last_fastingplasmaglucose_date` TEXT,
  `last_2hourplasmaglucose_value` TEXT,
  `last_2hourplasmaglucose_date` TEXT,
  `last_randomplasmaglucose_value` TEXT,
  `last_randomplasmaglucose_date` TEXT,
  `last_hba1c_date2` TEXT,
  `last_lipid_panel_date` TEXT,
  `last_urine_albumin_date` TEXT,
  `last_renal_panel_date` TEXT,
  `last_egfr_test_date` TEXT,
  `last_retinal_screen_date` TEXT,
  `last_liver_function_date` TEXT,
  `last_cbc_date` TEXT,
  `last_vitb12_date` TEXT,
  `last_potassium_date` TEXT,
  `last_endocrinology_visit` TEXT,
  `last_podiatry_visit` TEXT,
  `last_foot_exam` TEXT,
  `last_ophthalmology_visit` TEXT,
  `last_cardiology_visit` TEXT,
  `last_nephrology_visit` TEXT,
  `last_dietitian_visit` TEXT,
  `last_diabeducator_visit` TEXT,
  `first_e11_date` TEXT,
  `first_htn_date` TEXT,
  `first_dyslipidemia_date` TEXT,
  `flag_ckd` TEXT,
  `last_ckd_date` TEXT,
  `flag_hypertensive_kidney_disease` TEXT,
  `last_hypertensive_kidney_disease_date` TEXT,
  `flag_kidney_failure` TEXT,
  `last_kidney_failure_date` TEXT,
  `flag_acute_kidney_injury` TEXT,
  `last_acute_kidney_injury_date` TEXT,
  `flag_any_kidney_disease` TEXT,
  `last_any_kidney_disease_date` TEXT,
  `flag_dialysis` TEXT,
  `last_dialysis_date` TEXT,
  `flag_stroke` TEXT,
  `last_stroke_date` TEXT,
  `flag_heart_failure` TEXT,
  `last_heart_failure_date` TEXT,
  `flag_mi` TEXT,
  `last_mi_date` TEXT,
  `flag_other_cvd` TEXT,
  `last_other_cvd_date` TEXT,
  `dm_complications` TEXT,
  `dm_complication_count` TEXT,
  `flag_dm_kidney` TEXT,
  `last_dm_kidney_date` TEXT,
  `flag_dm_eye` TEXT,
  `last_dm_eye_date` TEXT,
  `flag_dm_neuropathy` TEXT,
  `last_dm_neuropathy_date` TEXT,
  `flag_dm_circulatory` TEXT,
  `last_dm_circulatory_date` TEXT,
  `flag_dm_foot` TEXT,
  `last_dm_foot_date` TEXT,
  `flag_amputation` TEXT,
  `last_amputation_date` TEXT,
  `flag_dm_hypoglycaemia` TEXT,
  `last_dm_hypoglycaemia_date` TEXT,
  `flag_dm_hyperglycaemic_crisis` TEXT,
  `last_dm_hyperglycaemic_crisis_date` TEXT,
  `flag_sepsis` TEXT,
  `last_sepsis_date` TEXT,
  `flag_ischemic_heart_disease` TEXT,
  `last_ischemic_heart_disease_date` TEXT,
  `flag_dm_hypoglycaemia_last90days` TEXT,
  `flag_EDorIP_with_hypoglycaemia_last90days` TEXT,
  `flag_hypo_hyper_glycemia_last6months` TEXT,
  `flag_oncology_l12m` TEXT,
  `flag_oncology_l24m` TEXT,
  `last_oncology_claim_date` TEXT,
  `oncology_dx_codes` TEXT,
  `flag_benign_neoplasm_l12m` TEXT,
  `flag_excl_palliative_hospice_ltc_l12m` TEXT,
  `excl_palliative_hospice_ltc_reason` TEXT,
  `flag_dialysis_l12m` TEXT,
  `flag_av_access_procedure_l12m` TEXT,
  `last_av_access_date_l12m` TEXT,
  `flag_excl_transplant_l24m` TEXT,
  `excl_transplant_reason` TEXT,
  `flag_excl_adv_neuro_congenital_l12m` TEXT,
  `excl_adv_neuro_congenital_reason` TEXT,
  `flag_excl_psych_sud_dementia_l12m` TEXT,
  `excl_psych_sud_dementia_reason` TEXT,
  `flag_excl_ventilator_tpn_homenursing_l12m` TEXT,
  `excl_ventilator_tpn_homenursing_reason` TEXT,
  `home_nursing_days_l12m` TEXT,
  `flag_excl_pregnant_postpartum` TEXT,
  `excl_pregnancy_status` TEXT,
  `max_episode_share_since2024` TEXT,
  `flag_excl_single_episode_gt60pct` TEXT,
  `specialty_rx_share_since2024` TEXT,
  `flag_excl_specialty_rx_gt60pct` TEXT,
  `specialty_rx_areas` TEXT,
  `gp_claims_6m` TEXT,
  `specialist_claims_6m` TEXT,
  `last_ip_admit_date` TEXT,
  `last_ip_discharge_date` TEXT,
  `second_last_ip_discharge_date` TEXT,
  `last_ip_facility` TEXT,
  `last_ip_dx` TEXT,
  `last_ip_dx_desc` TEXT,
  `last_ip_drg_desc` TEXT,
  `last_ip_discharge_type` TEXT,
  `last_visit_date` TEXT,
  `first_visit_after_discharge` TEXT,
  `days_discharge_to_first_visit` TEXT,
  `flag_no_visit_after_discharge` TEXT,
  `flag_missing_T2Drefill_post_last_discharge` TEXT,
  `flag_missing_HTNrefill_post_last_discharge` TEXT,
  `last_ed_visit_date` TEXT,
  `last_ed_facility` TEXT,
  `last_ed_dx` TEXT,
  `last_ed_dx_desc` TEXT,
  `active_drug_class_count` TEXT,
  `active_drug_classes` TEXT,
  `flag_active_ACEinhibitor` TEXT,
  `flag_active_ARBinhibitor` TEXT,
  `flag_active_insulin` TEXT,
  `flag_active_sulfonylurea` TEXT,
  `flag_overlap_ACE_ARB_more_than_30days` TEXT,
  `flag_glucagon_last12months` TEXT,
  `flag_no_glucagon_last12months` TEXT,
  `distinct_medicines_90d` TEXT,
  `t2d_drug_classes_l12m` TEXT,
  `pdc_metformin` TEXT,
  `pdc_sglt2` TEXT,
  `pdc_dpp4` TEXT,
  `pdc_glp1` TEXT,
  `pdc_sulfonylurea` TEXT,
  `pdc_tzd` TEXT,
  `pdc_any_t2d_noninsulin` TEXT,
  `first_t2d_fill_date` TEXT,
  `latest_new_t2d_class_start_date` TEXT,
  `last_t2d_fill_date` TEXT,
  `days_since_last_t2d_fill` TEXT,
  `days_since_t2d_supply_ran_out` TEXT,
  `flag_t2d_rx_gap_over_30d` TEXT,
  `htn_drug_classes_l12m` TEXT,
  `pdc_acei` TEXT,
  `pdc_arb` TEXT,
  `pdc_ccb` TEXT,
  `pdc_beta_blocker` TEXT,
  `pdc_thiazide` TEXT,
  `pdc_mra` TEXT,
  `pdc_any_htn` TEXT,
  `first_htn_fill_date` TEXT,
  `latest_new_htn_class_start_date` TEXT,
  `first_ACE_ARB_MRA_thiazide_fill_date` TEXT,
  `last_htn_fill_date` TEXT,
  `days_since_last_htn_fill` TEXT,
  `days_since_htn_supply_ran_out` TEXT,
  `flag_htn_rx_gap_over_30d` TEXT,
  `er_visits_6m` TEXT,
  `ip_admissions_6m` TEXT,
  `ed_visits_l12m` TEXT,
  `ip_admissions_l12m` TEXT,
  `l12m_payable_T2D` TEXT,
  `l12m_payable_non_phg_T2D` TEXT,
  `l12m_share_non_phg_T2D` TEXT,
  `l12m_payable_HTN` TEXT,
  `l12m_payable_non_phg_HTN` TEXT,
  `l12m_share_non_phg_HTN` TEXT,
  `encounters_l12m` TEXT,
  `encounters_l12m_op` TEXT,
  `encounters_l12m_ed` TEXT,
  `encounters_l12m_ip` TEXT,
  `providers_l12m` TEXT,
  `phg_share_l12m_encounters` TEXT,
  `mediclinic_share_l12m_encounters` TEXT,
  `nmc_share_l12m_encounters` TEXT,
  `burjeel_share_l12m_encounters` TEXT,
  `mubadala_share_l12m_encounters` TEXT,
  `others_share_l12m_encounters` TEXT,
  `top_groupownerlevel_l12m_encounters` TEXT,
  `top_groupownerlevel_l12m_encounter_share` TEXT,
  `top_groupownerlevel_l6m_encounters` TEXT,
  `top_groupownerlevel_l3m_encounters` TEXT,
  `top_groupownerlevel_l12m_op_encounters` TEXT,
  `top_groupownerlevel_l12m_op_encounter_share` TEXT,
  `l12m_payable_T2D_op` TEXT,
  `l12m_payable_T2D_ip` TEXT,
  `l12m_payable_T2D_ed` TEXT,
  `l12m_payable_HTN_op` TEXT,
  `l12m_payable_HTN_ip` TEXT,
  `l12m_payable_HTN_ed` TEXT,
  `l12m_T2D_drugs_payable` TEXT,
  `l12m_T2D_consultation_payable` TEXT,
  `l12m_T2D_labandpath_payable` TEXT,
  `l12m_T2D_DRG_payable` TEXT,
  `l12m_T2D_procedures_payable` TEXT,
  `l12m_T2D_others_payable` TEXT,
  `l12m_HTN_drugs_payable` TEXT,
  `l12m_HTN_consultation_payable` TEXT,
  `l12m_HTN_labandpath_payable` TEXT,
  `l12m_HTN_DRG_payable` TEXT,
  `l12m_HTN_procedures_payable` TEXT,
  `l12m_HTN_others_payable` TEXT,
  `last_claim_date` TEXT,
  `last_claim_costblocks` TEXT,
  `last_claim_facilities` TEXT,
  `last_claim_specialties` TEXT,
  `last_claim_dx_codes` TEXT,
  `last_claim_dx_desc` TEXT,
  `last_claim_medicines` TEXT,
  `last_claim_activities` TEXT,
  `last_claim_payable` TEXT,
  `flag_current_smoker_l12m` TEXT,
  `last_smoking_evidence_date` TEXT,
  `flag_former_smoker_code` TEXT,
  `flag_ckd_l12m` TEXT,
  `flag_hypertensive_kidney_disease_l12m` TEXT,
  `flag_kidney_failure_l12m` TEXT,
  `flag_acute_kidney_injury_l12m` TEXT,
  `flag_any_kidney_disease_l12m` TEXT,
  `flag_stroke_l12m` TEXT,
  `flag_heart_failure_l12m` TEXT,
  `flag_mi_l12m` TEXT,
  `flag_other_cvd_l12m` TEXT,
  `flag_dm_kidney_l12m` TEXT,
  `flag_dm_eye_l12m` TEXT,
  `flag_dm_neuropathy_l12m` TEXT,
  `flag_dm_circulatory_l12m` TEXT,
  `flag_dm_foot_l12m` TEXT,
  `flag_amputation_l12m` TEXT,
  `flag_dm_hypoglycaemia_l12m` TEXT,
  `flag_dm_hyperglycaemic_crisis_l12m` TEXT,
  `flag_sepsis_l12m` TEXT,
  `flag_ischemic_heart_disease_l12m` TEXT,
  `flag_dyslipidemia_l12m` TEXT,
  `flag_obesity` TEXT,
  `flag_cad_mi_l12m` TEXT,
  `flag_stroke_tia_l12m` TEXT,
  `flag_pad_l12m` TEXT,
  `flag_dm_retinopathy_l12m` TEXT,
  `flag_peripheral_neuropathy_l12m` TEXT,
  `flag_dm_foot_ulcer_l12m` TEXT,
  `flag_major_amputation_l12m` TEXT,
  `flag_dka_l12m` TEXT,
  `Last_UACR_Value` TEXT,
  `Last_UACR_Date` TEXT,
  `ckd_stage_l12m` TEXT,
  `l12m_payable_DiaborHTNrelated` TEXT,
  `payable_last24months_DiaborHTNrelated` TEXT,
  `payable_since2024_DiaborHTNrelated` TEXT,
  `l12m_payable_DiaborHTNrelated_op` TEXT,
  `l12m_payable_DiaborHTNrelated_ip` TEXT,
  `l12m_payable_DiaborHTNrelated_ed` TEXT,
  `l12m_payable_DiaborHTNrelated_drugs` TEXT,
  `l12m_payable_DiaborHTNrelated_consultation` TEXT,
  `l12m_payable_DiaborHTNrelated_labandpath` TEXT,
  `l12m_payable_DiaborHTNrelated_DRG` TEXT,
  `l12m_payable_DiaborHTNrelated_procedures` TEXT,
  `l12m_payable_DiaborHTNrelated_others` TEXT,
  `l12m_payable_DiaborHTNrelated_PHG` TEXT,
  `l12m_payable_DiaborHTNrelated_Mediclinic` TEXT,
  `l12m_payable_DiaborHTNrelated_NMC` TEXT,
  `l12m_payable_DiaborHTNrelated_Burjeel` TEXT,
  `l12m_payable_DiaborHTNrelated_Mubadala` TEXT,
  `l12m_payable_DiaborHTNrelated_OtherProviders` TEXT,
  `l12m_encounters_DiaborHTNrelated` TEXT,
  `l12m_encounters_op_DiaborHTNrelated` TEXT,
  `l12m_encounters_ed_DiaborHTNrelated` TEXT,
  `l12m_encounters_ip_DiaborHTNrelated` TEXT,
  `top_groupownerlevel_l12m_op_DiaborHTNrelated_encounters` TEXT,
  `top_groupownerlevel_l12m_op_DiaborHTNrelated_encounter_share` TEXT,
  `providers_l12m_DiaborHTNrelated` TEXT,
  `l12m_ED_visits_DiaborHTNrelated` TEXT,
  `l12m_IP_admissions_DiaborHTNrelated` TEXT,
  SHARD KEY (`mask_id`)
);

-- ───────── Member: typed, cleaned values the rules read, plus scores ─────────
CREATE ROWSTORE TABLE IF NOT EXISTS member (
  member_id                          VARCHAR(20) NOT NULL,
  gender                             VARCHAR(120),
  age                                DECIMAL(10,2),
  nationality                        VARCHAR(120),
  plan_name                          VARCHAR(120),
  excluded                           TINYINT,
  persona                            VARCHAR(120),
  clinical_score                     DECIMAL(10,2),
  comorbid_complication_score        DECIMAL(10,2),
  kidney_score                       DECIMAL(10,2),
  utilization_score                  DECIMAL(10,2),
  age_sex_score                      DECIMAL(10,2),
  total_risk_score                   DECIMAL(10,2),
  priority_clinical_review           TINYINT,
  cohort_t2d_l12m                    TINYINT,
  cohort_htn_l12m                    TINYINT,
  flag_ckd                           TINYINT,
  flag_dyslipidemia_l12m             TINYINT,
  flag_obesity                       TINYINT,
  flag_ischemic_heart_disease        TINYINT,
  flag_heart_failure                 TINYINT,
  flag_stroke                        TINYINT,
  flag_dm_neuropathy                 TINYINT,
  flag_dm_retinopathy_l12m           TINYINT,
  flag_pad_l12m                      TINYINT,
  flag_dm_foot_ulcer_l12m            TINYINT,
  flag_amputation                    TINYINT,
  flag_dka_l12m                      TINYINT,
  flag_dm_hypoglycaemia_l12m         TINYINT,
  flag_dm_hypoglycaemia_last90days   TINYINT,
  flag_no_glucagon_last12months      TINYINT,
  flag_active_insulin                TINYINT,
  flag_active_aceinhibitor           TINYINT,
  flag_active_arbinhibitor           TINYINT,
  last_hba1c_value                   DECIMAL(10,2),
  last_hba1c_date                    DATE,
  last_hba1c_date2                   DATE,
  last_systolicpressure_value        DECIMAL(10,2),
  last_diastolicpressure_value       DECIMAL(10,2),
  last_systolicpressure_date         DATE,
  last_egfr_value                    DECIMAL(10,2),
  last_egfr_date                     DATE,
  last_uacr_value                    DECIMAL(10,2),
  last_uacr_date                     DATE,
  last_measuredbmi_value             DECIMAL(10,2),
  last_egfr_test_date                DATE,
  last_urine_albumin_date            DATE,
  last_lipid_panel_date              DATE,
  last_renal_panel_date              DATE,
  last_potassium_date                DATE,
  last_retinal_screen_date           DATE,
  last_ophthalmology_visit           DATE,
  last_foot_exam                     DATE,
  last_podiatry_visit                DATE,
  last_dietitian_visit               DATE,
  last_diabeducator_visit            DATE,
  first_e11_date                     DATE,
  first_htn_date                     DATE,
  last_visit_date                    DATE,
  last_ip_discharge_date             DATE,
  last_ed_visit_date                 DATE,
  ed_visits_l12m                     DECIMAL(10,2),
  ip_admissions_l12m                 DECIMAL(10,2),
  pdc_any_t2d_noninsulin             DECIMAL(6,4),
  pdc_any_htn                        DECIMAL(6,4),
  pdc_mra                            DECIMAL(6,4),
  pdc_thiazide                       DECIMAL(6,4),
  days_since_t2d_supply_ran_out      DECIMAL(10,2),
  days_since_htn_supply_ran_out      DECIMAL(10,2),
  l12m_payable_diaborhtnrelated      DECIMAL(14,2),
  trig1_hba1c_above_target           TINYINT,
  trig2_htn_tx_review                TINYINT,
  trig3_hypoglycemia_tx              TINYINT,
  trig4_post_discharge_care          TINYINT,
  trig5_kidney_check                 TINYINT,
  trig6_hba1c_due                    TINYINT,
  trig7_renal_potassium_due          TINYINT,
  trig8_nutrition_due                TINYINT,
  trig9_medication_adherence         TINYINT,
  trig10_new_diagnosis               TINYINT,
  trig11_annual_labs_due             TINYINT,
  trig12_eyeexam_due                 TINYINT,
  trig13_highriskfoot_monitor        TINYINT,
  -- set by the load
  language                           VARCHAR(20),
  has_t2d                            TINYINT,
  has_htn                            TINYINT,
  consent                            VARCHAR(10) NOT NULL DEFAULT 'pending',   -- pending | granted | declined (written by the portal)
  -- set by the nightly run (rulebook §2 and §4)
  r_total                            INT,
  tier                               INT,           -- 1 Low · 2 Moderate · 3 High · 4 Very high
  alert                              VARCHAR(6),    -- RED | AMBER | YELLOW | GREEN
  contact_priority                   VARCHAR(2),    -- P1 … P4
  scored_on                          DATE,
  PRIMARY KEY (member_id)
);

-- ───────── The loop ─────────
CREATE ROWSTORE TABLE IF NOT EXISTS campaign_member (
  member_id    VARCHAR(20) NOT NULL,
  campaign_id  VARCHAR(12) NOT NULL,
  holdout      TINYINT NOT NULL,              -- stable 10% control group: CRC32(campaign:member) % 100 < holdout_pct
  added_on     DATE NOT NULL,
  PRIMARY KEY (member_id, campaign_id)
);
CREATE ROWSTORE TABLE IF NOT EXISTS member_signal (     -- raw member → trigger, one row per trigger per run
  member_id     VARCHAR(20) NOT NULL,
  trigger_code  VARCHAR(10) NOT NULL,
  state         VARCHAR(12) NOT NULL,          -- fired | cannot_tell
  evidence      VARCHAR(400),
  run_date      DATE NOT NULL,
  PRIMARY KEY (member_id, trigger_code, run_date)
);
CREATE ROWSTORE TABLE IF NOT EXISTS care_plan_need (   -- trigger → care-plan need (one per member per trigger)
  member_id      VARCHAR(20) NOT NULL,
  trigger_code   VARCHAR(10) NOT NULL,
  class          VARCHAR(10) NOT NULL,
  class_order    INT NOT NULL,
  trigger_order  INT NOT NULL,
  slot           VARCHAR(8) NOT NULL,          -- CURRENT (top 3) | NEXT (4–6) | FUTURE | CLOSED
  status         VARCHAR(10) NOT NULL,         -- open | done | declined
  gap_state      VARCHAR(10) NOT NULL,         -- Potential | Verified | Scheduled | Reported | Closed
  due_date       DATE NOT NULL,
  hold_until     DATE,
  evidence       VARCHAR(400),
  opened_on      DATE NOT NULL,
  closed_on      DATE,
  PRIMARY KEY (member_id, trigger_code)
);
CREATE ROWSTORE TABLE IF NOT EXISTS action (    -- every piece of work: nudge, call, care-plan action, follow-up, retry, escalation
  action_id         BIGINT AUTO_INCREMENT,
  member_id         VARCHAR(20) NOT NULL,
  trigger_code      VARCHAR(10),               -- set for care-plan actions and their follow-ups
  kind              VARCHAR(12) NOT NULL,      -- nudge | call | care_plan | follow_up | retry | escalation
  title             VARCHAR(160) NOT NULL,
  channel           VARCHAR(30),
  owner_role        VARCHAR(40),
  assignee          VARCHAR(10),               -- nurse_id
  due_date          DATE NOT NULL,
  status            VARCHAR(10) NOT NULL,      -- open | done | declined
  parent_action_id  BIGINT,                    -- the action whose outcome created this one
  attempt           INT NOT NULL DEFAULT 1,
  created_by        VARCHAR(10) NOT NULL,      -- nightly | a nurse_id
  created_at        DATETIME NOT NULL,
  closed_at         DATETIME,
  PRIMARY KEY (action_id, member_id),
  SHARD KEY (member_id)
);
CREATE ROWSTORE TABLE IF NOT EXISTS outcome (   -- what the nurse recorded
  outcome_id    BIGINT AUTO_INCREMENT,
  member_id     VARCHAR(20) NOT NULL,
  action_id     BIGINT NOT NULL,
  trigger_code  VARCHAR(10),
  result        VARCHAR(20) NOT NULL,          -- a rule_followup.outcome
  reached       TINYINT,
  consent       VARCHAR(10),
  notes         VARCHAR(400),
  nurse_id      VARCHAR(10) NOT NULL,
  recorded_at   DATETIME NOT NULL,
  PRIMARY KEY (outcome_id, member_id),
  SHARD KEY (member_id)
);
CREATE ROWSTORE TABLE IF NOT EXISTS worklist (  -- today's call list, one row per member, rebuilt each run
  work_date    DATE NOT NULL,
  member_id    VARCHAR(20) NOT NULL,
  nurse_id     VARCHAR(10),
  rank_no      INT NOT NULL,                   -- order across the whole team
  nurse_rank   INT NOT NULL,                   -- order in this nurse's list
  action_id    BIGINT NOT NULL,                -- the lead action for the call
  priority     VARCHAR(2), alert VARCHAR(6), tier INT,
  reason       VARCHAR(160),
  due_by       DATE NOT NULL,
  status       VARCHAR(8) NOT NULL,            -- today | queued (over capacity: rolls to tomorrow)
  PRIMARY KEY (member_id, work_date)
);

-- ───────── Work tables used inside one run (keep UPDATEs to simple joins on member_id) ─────────
CREATE ROWSTORE TABLE IF NOT EXISTS work_member (
  member_id VARCHAR(20) PRIMARY KEY, n_fired INT DEFAULT 0, has_trig4 TINYINT DEFAULT 0, match_order INT,
  owner_campaign VARCHAR(12), owner_priority INT, trigger_mode VARCHAR(4), trigger_list VARCHAR(200),
  has_open_contact TINYINT DEFAULT 0, reached_14d TINYINT DEFAULT 0, top_need VARCHAR(160)
);
CREATE ROWSTORE TABLE IF NOT EXISTS work_rank (
  member_id VARCHAR(20) NOT NULL, trigger_code VARCHAR(10) NOT NULL, rn INT NOT NULL, PRIMARY KEY (member_id, trigger_code)
);
