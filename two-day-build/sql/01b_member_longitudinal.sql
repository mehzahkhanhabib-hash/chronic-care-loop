-- member_longitudinal: the 250-member longitudinal extract (377 columns) typed for SingleStore / MySQL.
-- Generated from 250_members_longitudinal_data.xlsx by the mapping build. mask_id → member_id. Column names lower-cased; spaces and symbols → _.
-- Placeholders (999, BP 1/1, text NULL, #VALUE!) are cleaned by 03_load.sql rules (G0) when loaded through stg_extract.
CREATE ROWSTORE TABLE IF NOT EXISTS member_longitudinal (
  member_id                                                    VARCHAR(20) NOT NULL,   -- mask_id
  gender                                                       VARCHAR(200),   -- GENDER
  age                                                          INT,   -- AGE
  nationality                                                  VARCHAR(200),   -- NATIONALITY
  policy_group                                                 VARCHAR(200),   -- policy_group
  policy_type                                                  VARCHAR(200),   -- policy_type
  cohort_t2d_l12m                                              TINYINT,   -- cohort_t2d_l12m
  cohort_htn_l12m                                              TINYINT,   -- cohort_htn_l12m
  t2d_identified_by                                            VARCHAR(200),   -- t2d_identified_by
  htn_identified_by                                            VARCHAR(200),   -- htn_identified_by
  t2d_category                                                 VARCHAR(200),   -- t2d_category
  htn_category                                                 VARCHAR(200),   -- htn_category
  gwp                                                          DECIMAL(14,4),   -- GWP
  risk_premium                                                 DECIMAL(14,4),   -- Risk Premium
  exclusion_nonactiveaccounts                                  TINYINT,   -- Exclusion_nonactiveaccounts · new
  exclusion_op_consultations_encounter                         TINYINT,   -- Exclusion_op_consultations_encounter · new
  exclusion_alreadyenrolled                                    TINYINT,   -- Exclusion_alreadyenrolled · new
  exclusion                                                    TINYINT,   -- Exclusion
  p1_complication                                              TINYINT,   -- P1_Complication
  p2_recurrent_ed_ip                                           TINYINT,   -- P2_Recurrent_ED_IP
  p3_slipping                                                  TINYINT,   -- P3_slipping
  p5_newlydiagnosed                                            TINYINT,   -- P5_newlydiagnosed
  p3_offradar                                                  TINYINT,   -- P3_offradar
  p4_uncontrolled                                              TINYINT,   -- P4_uncontrolled
  persona                                                      VARCHAR(200),   -- Persona
  trig1_hba1c_above_target                                     TINYINT,   -- Trig1_HbA1c_above_target
  trig2a_noaceiarb_kidneyorcad                                 TINYINT,   -- Trig2a_NoACEiARB_KidneyOrCAD
  trig2b_acei_plus_arb                                         TINYINT,   -- Trig2b_ACEi_plus_ARB
  trig2_htn_tx_review                                          TINYINT,   -- Trig2_HTN_tx_review
  trig3a_hypoglycemia_rev                                      TINYINT,   -- Trig3a_hypoglycemia_rev
  trig3b_glucagon_not_dispensed                                TINYINT,   -- Trig3b_glucagon_not_dispensed
  trig3_hypoglycemia_tx                                        TINYINT,   -- Trig3_hypoglycemia_tx
  trig4a_nofollowup_post_discharge                             TINYINT,   -- Trig4a_NoFollowup_post_discharge
  trig4b_postdischarge_medsgap                                 TINYINT,   -- Trig4b_postdischarge_medsgap
  trig4_post_discharge_care                                    TINYINT,   -- Trig4_post_discharge_care
  trig5a_kidney_screen_due                                     TINYINT,   -- Trig5a_Kidney_screen_due
  trig5b_ckd_monitoring                                        TINYINT,   -- Trig5b_CKD_monitoring
  trig5c_neph_due                                              TINYINT,   -- Trig5c_Neph_due
  trig5_kidney_check                                           TINYINT,   -- Trig5_Kidney_check
  trig6_hba1c_due                                              TINYINT,   -- Trig6_HbA1c_due
  trig7_renal_potassium_due                                    TINYINT,   -- Trig7_Renal_Potassium_due
  trig8_nutrition_due                                          TINYINT,   -- Trig8_nutrition_due
  trig9_medication_adherence                                   TINYINT,   -- Trig9_medication_adherence
  trig10_new_diagnosis                                         TINYINT,   -- Trig10_new_diagnosis
  trig11_annual_labs_due                                       TINYINT,   -- Trig11_annual_labs_due
  trig12_eyeexam_due                                           TINYINT,   -- Trig12_eyeexam_due
  trig13_highriskfoot_monitor                                  TINYINT,   -- Trig13_highriskfoot_monitor
  n_triggers                                                   INT,   -- # of triggers
  hba1c_score                                                  INT,   -- HbA1c_score
  clinical_score                                               INT,   -- Clinical_score
  comorbid_complication_score                                  INT,   -- Comorbid_complication_score
  egfr_uacr_points                                             INT,   -- eGFR + UACR points
  kidney_score                                                 INT,   -- Kidney_score
  utilization_score                                            INT,   -- Utilization_score
  age_sex_score                                                INT,   -- Age_sex_score
  total_risk_score                                             INT,   -- Total_risk_Score
  risk_tier                                                    VARCHAR(200),   -- Risk_tier
  cohort_allocation                                            VARCHAR(200),   -- Cohort_allocation
  initial_target_cohort                                        TINYINT,   -- Initial_target_cohort · new
  priority_clinical_review                                     TINYINT,   -- Priority_clinical_review
  last_hba1c_value                                             DECIMAL(14,4),   -- Last_HbA1c_Value
  last_hba1c_date                                              DATE,   -- Last_HbA1c_Date
  last_systolicpressure_value                                  INT,   -- Last_SystolicPressure_Value
  last_systolicpressure_date                                   DATE,   -- Last_SystolicPressure_Date
  last_diastolicpressure_value                                 INT,   -- Last_DiastolicPressure_Value
  last_diastolicpressure_date                                  DATE,   -- Last_DiastolicPressure_Date
  last_measuredbmi_value                                       DECIMAL(14,4),   -- Last_MeasuredBMI_Value
  last_measuredbmi_date                                        DATE,   -- Last_MeasuredBMI_Date
  last_egfr_value                                              INT,   -- Last_eGFR_Value
  last_egfr_date                                               DATE,   -- Last_eGFR_Date
  last_fastingplasmaglucose_value                              DECIMAL(14,4),   -- last_fastingplasmaglucose_value
  last_fastingplasmaglucose_date                               DATE,   -- last_fastingplasmaglucose_date
  last_2hourplasmaglucose_value                                VARCHAR(120),   -- last_2hourplasmaglucose_value
  last_2hourplasmaglucose_date                                 VARCHAR(120),   -- last_2hourplasmaglucose_date
  last_randomplasmaglucose_value                               DECIMAL(14,4),   -- last_randomplasmaglucose_value
  last_randomplasmaglucose_date                                DATE,   -- last_randomplasmaglucose_date
  last_hba1c_date2                                             DATE,   -- last_hba1c_date2
  last_lipid_panel_date                                        DATE,   -- last_lipid_panel_date
  last_urine_albumin_date                                      DATE,   -- last_urine_albumin_date
  last_renal_panel_date                                        DATE,   -- last_renal_panel_date
  last_egfr_test_date                                          DATE,   -- last_egfr_test_date
  last_retinal_screen_date                                     DATE,   -- last_retinal_screen_date
  last_liver_function_date                                     DATE,   -- last_liver_function_date
  last_cbc_date                                                DATE,   -- last_cbc_date
  last_vitb12_date                                             DATE,   -- last_vitb12_date
  last_potassium_date                                          DATE,   -- last_potassium_date
  last_endocrinology_visit                                     DATE,   -- last_endocrinology_visit
  last_podiatry_visit                                          DATE,   -- last_podiatry_visit
  last_foot_exam                                               DATE,   -- last_foot_exam
  last_ophthalmology_visit                                     DATE,   -- last_ophthalmology_visit
  last_cardiology_visit                                        DATE,   -- last_cardiology_visit
  last_nephrology_visit                                        DATE,   -- last_nephrology_visit
  last_dietitian_visit                                         DATE,   -- last_dietitian_visit
  last_diabeducator_visit                                      DATE,   -- last_diabeducator_visit
  first_e11_date                                               DATE,   -- first_e11_date
  first_htn_date                                               DATE,   -- first_htn_date
  first_dyslipidemia_date                                      DATE,   -- first_dyslipidemia_date
  flag_ckd                                                     TINYINT,   -- flag_ckd
  last_ckd_date                                                DATE,   -- last_ckd_date
  flag_hypertensive_kidney_disease                             TINYINT,   -- flag_hypertensive_kidney_disease
  last_hypertensive_kidney_disease_date                        DATE,   -- last_hypertensive_kidney_disease_date
  flag_kidney_failure                                          TINYINT,   -- flag_kidney_failure
  last_kidney_failure_date                                     DATE,   -- last_kidney_failure_date
  flag_acute_kidney_injury                                     TINYINT,   -- flag_acute_kidney_injury
  last_acute_kidney_injury_date                                DATE,   -- last_acute_kidney_injury_date
  flag_any_kidney_disease                                      TINYINT,   -- flag_any_kidney_disease
  last_any_kidney_disease_date                                 DATE,   -- last_any_kidney_disease_date
  flag_dialysis                                                TINYINT,   -- flag_dialysis
  last_dialysis_date                                           VARCHAR(120),   -- last_dialysis_date
  flag_stroke                                                  TINYINT,   -- flag_stroke
  last_stroke_date                                             DATE,   -- last_stroke_date
  flag_heart_failure                                           TINYINT,   -- flag_heart_failure
  last_heart_failure_date                                      DATE,   -- last_heart_failure_date
  flag_mi                                                      TINYINT,   -- flag_mi
  last_mi_date                                                 DATE,   -- last_mi_date
  flag_other_cvd                                               TINYINT,   -- flag_other_cvd
  last_other_cvd_date                                          DATE,   -- last_other_cvd_date
  dm_complications                                             TEXT,   -- dm_complications
  dm_complication_count                                        INT,   -- dm_complication_count
  flag_dm_kidney                                               TINYINT,   -- flag_dm_kidney
  last_dm_kidney_date                                          DATE,   -- last_dm_kidney_date
  flag_dm_eye                                                  TINYINT,   -- flag_dm_eye
  last_dm_eye_date                                             DATE,   -- last_dm_eye_date
  flag_dm_neuropathy                                           TINYINT,   -- flag_dm_neuropathy
  last_dm_neuropathy_date                                      DATE,   -- last_dm_neuropathy_date
  flag_dm_circulatory                                          TINYINT,   -- flag_dm_circulatory
  last_dm_circulatory_date                                     DATE,   -- last_dm_circulatory_date
  flag_dm_foot                                                 TINYINT,   -- flag_dm_foot
  last_dm_foot_date                                            DATE,   -- last_dm_foot_date
  flag_amputation                                              TINYINT,   -- flag_amputation
  last_amputation_date                                         VARCHAR(120),   -- last_amputation_date
  flag_dm_hypoglycaemia                                        TINYINT,   -- flag_dm_hypoglycaemia
  last_dm_hypoglycaemia_date                                   DATE,   -- last_dm_hypoglycaemia_date
  flag_dm_hyperglycaemic_crisis                                TINYINT,   -- flag_dm_hyperglycaemic_crisis
  last_dm_hyperglycaemic_crisis_date                           DATE,   -- last_dm_hyperglycaemic_crisis_date
  flag_sepsis                                                  TINYINT,   -- flag_sepsis
  last_sepsis_date                                             DATE,   -- last_sepsis_date
  flag_ischemic_heart_disease                                  TINYINT,   -- flag_ischemic_heart_disease
  last_ischemic_heart_disease_date                             DATE,   -- last_ischemic_heart_disease_date
  flag_dm_hypoglycaemia_last90days                             TINYINT,   -- flag_dm_hypoglycaemia_last90days
  flag_edorip_with_hypoglycaemia_last90days                    TINYINT,   -- flag_EDorIP_with_hypoglycaemia_last90days
  flag_hypo_hyper_glycemia_last6months                         TINYINT,   -- flag_hypo_hyper_glycemia_last6months
  flag_oncology_l12m                                           TINYINT,   -- flag_oncology_l12m
  flag_oncology_l24m                                           TINYINT,   -- flag_oncology_l24m
  last_oncology_claim_date                                     DATE,   -- last_oncology_claim_date
  oncology_dx_codes                                            TEXT,   -- oncology_dx_codes
  flag_benign_neoplasm_l12m                                    TINYINT,   -- flag_benign_neoplasm_l12m
  flag_excl_palliative_hospice_ltc_l12m                        TINYINT,   -- flag_excl_palliative_hospice_ltc_l12m
  excl_palliative_hospice_ltc_reason                           VARCHAR(120),   -- excl_palliative_hospice_ltc_reason
  flag_dialysis_l12m                                           TINYINT,   -- flag_dialysis_l12m
  flag_av_access_procedure_l12m                                TINYINT,   -- flag_av_access_procedure_l12m
  last_av_access_date_l12m                                     VARCHAR(120),   -- last_av_access_date_l12m
  flag_excl_transplant_l24m                                    TINYINT,   -- flag_excl_transplant_l24m
  excl_transplant_reason                                       VARCHAR(120),   -- excl_transplant_reason
  flag_excl_adv_neuro_congenital_l12m                          TINYINT,   -- flag_excl_adv_neuro_congenital_l12m
  excl_adv_neuro_congenital_reason                             VARCHAR(120),   -- excl_adv_neuro_congenital_reason
  flag_excl_psych_sud_dementia_l12m                            TINYINT,   -- flag_excl_psych_sud_dementia_l12m
  excl_psych_sud_dementia_reason                               VARCHAR(120),   -- excl_psych_sud_dementia_reason
  flag_excl_ventilator_tpn_homenursing_l12m                    TINYINT,   -- flag_excl_ventilator_tpn_homenursing_l12m
  excl_ventilator_tpn_homenursing_reason                       VARCHAR(120),   -- excl_ventilator_tpn_homenursing_reason
  home_nursing_days_l12m                                       TINYINT,   -- home_nursing_days_l12m
  flag_excl_pregnant_postpartum                                TINYINT,   -- flag_excl_pregnant_postpartum
  excl_pregnancy_status                                        VARCHAR(120),   -- excl_pregnancy_status
  max_episode_share_since2024                                  DECIMAL(14,4),   -- max_episode_share_since2024
  max_episode_type                                             VARCHAR(200),   -- max_episode_type · new
  max_episode_dmhtn_related                                    TINYINT,   -- max_episode_dmhtn_related · new
  flag_excl_single_episode_gt60pct                             TINYINT,   -- flag_excl_single_episode_gt60pct
  specialty_rx_share_since2024                                 DECIMAL(14,4),   -- specialty_rx_share_since2024
  flag_excl_specialty_rx_gt60pct                               TINYINT,   -- flag_excl_specialty_rx_gt60pct
  specialty_rx_areas                                           TEXT,   -- specialty_rx_areas
  gp_claims_6m                                                 INT,   -- gp_claims_6m
  specialist_claims_6m                                         INT,   -- specialist_claims_6m
  last_ip_admit_date                                           DATE,   -- last_ip_admit_date
  last_ip_discharge_date                                       DATE,   -- last_ip_discharge_date
  second_last_ip_discharge_date                                DATE,   -- second_last_ip_discharge_date
  last_ip_facility                                             VARCHAR(200),   -- last_ip_facility
  last_ip_dx                                                   VARCHAR(200),   -- last_ip_dx
  last_ip_dx_desc                                              TEXT,   -- last_ip_dx_desc
  last_ip_drg_desc                                             TEXT,   -- last_ip_drg_desc
  last_ip_discharge_type                                       VARCHAR(200),   -- last_ip_discharge_type
  last_visit_date                                              DATE,   -- last_visit_date
  first_visit_after_discharge                                  DATE,   -- first_visit_after_discharge
  days_discharge_to_first_visit                                INT,   -- days_discharge_to_first_visit
  flag_no_visit_after_discharge                                TINYINT,   -- flag_no_visit_after_discharge
  flag_missing_t2drefill_post_last_discharge                   TINYINT,   -- flag_missing_T2Drefill_post_last_discharge
  flag_missing_htnrefill_post_last_discharge                   TINYINT,   -- flag_missing_HTNrefill_post_last_discharge
  last_ed_visit_date                                           DATE,   -- last_ed_visit_date
  last_ed_facility                                             VARCHAR(200),   -- last_ed_facility
  last_ed_dx                                                   VARCHAR(200),   -- last_ed_dx
  last_ed_dx_desc                                              TEXT,   -- last_ed_dx_desc
  active_drug_class_count                                      INT,   -- active_drug_class_count
  active_drug_classes                                          TEXT,   -- active_drug_classes
  flag_active_aceinhibitor                                     TINYINT,   -- flag_active_ACEinhibitor
  flag_active_arbinhibitor                                     TINYINT,   -- flag_active_ARBinhibitor
  flag_active_insulin                                          TINYINT,   -- flag_active_insulin
  flag_active_sulfonylurea                                     TINYINT,   -- flag_active_sulfonylurea
  flag_overlap_ace_arb_more_than_30days                        TINYINT,   -- flag_overlap_ACE_ARB_more_than_30days
  flag_glucagon_last12months                                   TINYINT,   -- flag_glucagon_last12months
  flag_no_glucagon_last12months                                TINYINT,   -- flag_no_glucagon_last12months
  distinct_medicines_90d                                       INT,   -- distinct_medicines_90d
  t2d_drug_classes_l12m                                        TEXT,   -- t2d_drug_classes_l12m
  pdc_metformin                                                DECIMAL(14,4),   -- pdc_metformin
  pdc_sglt2                                                    DECIMAL(14,4),   -- pdc_sglt2
  pdc_dpp4                                                     DECIMAL(14,4),   -- pdc_dpp4
  pdc_glp1                                                     DECIMAL(14,4),   -- pdc_glp1
  pdc_sulfonylurea                                             DECIMAL(14,4),   -- pdc_sulfonylurea
  pdc_tzd                                                      DECIMAL(14,4),   -- pdc_tzd
  pdc_any_t2d_noninsulin                                       DECIMAL(14,4),   -- pdc_any_t2d_noninsulin
  first_t2d_fill_date                                          DATE,   -- first_t2d_fill_date
  latest_new_t2d_class_start_date                              DATE,   -- latest_new_t2d_class_start_date
  last_t2d_fill_date                                           DATE,   -- last_t2d_fill_date
  days_since_last_t2d_fill                                     INT,   -- days_since_last_t2d_fill
  days_since_t2d_supply_ran_out                                INT,   -- days_since_t2d_supply_ran_out
  flag_t2d_rx_gap_over_30d                                     TINYINT,   -- flag_t2d_rx_gap_over_30d
  htn_drug_classes_l12m                                        TEXT,   -- htn_drug_classes_l12m
  pdc_acei                                                     DECIMAL(14,4),   -- pdc_acei
  pdc_arb                                                      DECIMAL(14,4),   -- pdc_arb
  pdc_ccb                                                      DECIMAL(14,4),   -- pdc_ccb
  pdc_beta_blocker                                             DECIMAL(14,4),   -- pdc_beta_blocker
  pdc_thiazide                                                 DECIMAL(14,4),   -- pdc_thiazide
  pdc_mra                                                      DECIMAL(14,4),   -- pdc_mra
  pdc_any_htn                                                  DECIMAL(14,4),   -- pdc_any_htn
  first_htn_fill_date                                          DATE,   -- first_htn_fill_date
  latest_new_htn_class_start_date                              DATE,   -- latest_new_htn_class_start_date
  first_ace_arb_mra_thiazide_fill_date                         DATE,   -- first_ACE_ARB_MRA_thiazide_fill_date
  last_htn_fill_date                                           DATE,   -- last_htn_fill_date
  days_since_last_htn_fill                                     INT,   -- days_since_last_htn_fill
  days_since_htn_supply_ran_out                                INT,   -- days_since_htn_supply_ran_out
  flag_htn_rx_gap_over_30d                                     TINYINT,   -- flag_htn_rx_gap_over_30d
  er_visits_6m                                                 INT,   -- er_visits_6m
  ip_admissions_6m                                             INT,   -- ip_admissions_6m
  ed_visits_l12m                                               INT,   -- ed_visits_l12m
  ip_admissions_l12m                                           INT,   -- ip_admissions_l12m
  l12m_payable_allcause                                        DECIMAL(14,4),   -- l12m_payable_allcause · new
  l12m_payable_t2d                                             DECIMAL(14,4),   -- l12m_payable_T2D
  l12m_payable_non_phg_t2d                                     DECIMAL(14,4),   -- l12m_payable_non_phg_T2D
  l12m_share_non_phg_t2d                                       DECIMAL(14,4),   -- l12m_share_non_phg_T2D
  l12m_payable_htn                                             DECIMAL(14,4),   -- l12m_payable_HTN
  l12m_payable_non_phg_htn                                     DECIMAL(14,4),   -- l12m_payable_non_phg_HTN
  l12m_share_non_phg_htn                                       DECIMAL(14,4),   -- l12m_share_non_phg_HTN
  encounters_l12m                                              INT,   -- encounters_l12m
  encounters_l12m_op                                           INT,   -- encounters_l12m_op
  encounters_l12m_ed                                           INT,   -- encounters_l12m_ed
  encounters_l12m_ip                                           INT,   -- encounters_l12m_ip
  providers_l12m                                               INT,   -- providers_l12m
  phg_share_l12m_encounters                                    DECIMAL(14,4),   -- phg_share_l12m_encounters
  mediclinic_share_l12m_encounters                             DECIMAL(14,4),   -- mediclinic_share_l12m_encounters
  nmc_share_l12m_encounters                                    DECIMAL(14,4),   -- nmc_share_l12m_encounters
  burjeel_share_l12m_encounters                                DECIMAL(14,4),   -- burjeel_share_l12m_encounters
  mubadala_share_l12m_encounters                               DECIMAL(14,4),   -- mubadala_share_l12m_encounters
  others_share_l12m_encounters                                 DECIMAL(14,4),   -- others_share_l12m_encounters
  top_groupownerlevel_l12m_encounters                          VARCHAR(200),   -- top_groupownerlevel_l12m_encounters
  top_groupownerlevel_l12m_encounter_share                     DECIMAL(14,4),   -- top_groupownerlevel_l12m_encounter_share
  top_groupownerlevel_l12m_op_encounters                       VARCHAR(200),   -- top_groupownerlevel_l12m_op_encounters
  top_groupownerlevel_l12m_op_encounter_share                  DECIMAL(14,4),   -- top_groupownerlevel_l12m_op_encounter_share
  encounters_l12m_op_consultations                             INT,   -- encounters_l12m_op_consultations · new
  top_groupownerlevel_l12m_op_encounter_consultations_share    DECIMAL(14,4),   -- top_groupownerlevel_l12m_op_encounter_consultations_share · new
  top_groupownerlevel_l12m_op_consultations                    VARCHAR(200),   -- top_groupownerlevel_l12m_op_consultations · new
  l12m_payable_op                                              DECIMAL(14,4),   -- l12m_payable_op · new
  l12m_payable_ip                                              DECIMAL(14,4),   -- l12m_payable_ip · new
  l12m_payable_ed                                              DECIMAL(14,4),   -- l12m_payable_ed · new
  l12m_payable_t2d_op                                          DECIMAL(14,4),   -- l12m_payable_T2D_op
  l12m_payable_t2d_ip                                          DECIMAL(14,4),   -- l12m_payable_T2D_ip
  l12m_payable_t2d_ed                                          DECIMAL(14,4),   -- l12m_payable_T2D_ed
  l12m_payable_htn_op                                          DECIMAL(14,4),   -- l12m_payable_HTN_op
  l12m_payable_htn_ip                                          DECIMAL(14,4),   -- l12m_payable_HTN_ip
  l12m_payable_htn_ed                                          DECIMAL(14,4),   -- l12m_payable_HTN_ed
  l12m_drugs_payable                                           DECIMAL(14,4),   -- l12m_drugs_payable · new
  l12m_consultation_payable                                    DECIMAL(14,4),   -- l12m_consultation_payable · new
  l12m_labandpath_payable                                      DECIMAL(14,4),   -- l12m_labandpath_payable · new
  l12m_drg_payable                                             DECIMAL(14,4),   -- l12m_DRG_payable · new
  l12m_procedures_payable                                      DECIMAL(14,4),   -- l12m_procedures_payable · new
  l12m_others_payable                                          DECIMAL(14,4),   -- l12m_others_payable · new
  l12m_t2d_drugs_payable                                       DECIMAL(14,4),   -- l12m_T2D_drugs_payable
  l12m_t2d_consultation_payable                                DECIMAL(14,4),   -- l12m_T2D_consultation_payable
  l12m_t2d_labandpath_payable                                  DECIMAL(14,4),   -- l12m_T2D_labandpath_payable
  l12m_t2d_drg_payable                                         DECIMAL(14,4),   -- l12m_T2D_DRG_payable
  l12m_t2d_procedures_payable                                  DECIMAL(14,4),   -- l12m_T2D_procedures_payable
  l12m_t2d_others_payable                                      DECIMAL(14,4),   -- l12m_T2D_others_payable
  l12m_htn_drugs_payable                                       DECIMAL(14,4),   -- l12m_HTN_drugs_payable
  l12m_htn_consultation_payable                                DECIMAL(14,4),   -- l12m_HTN_consultation_payable
  l12m_htn_labandpath_payable                                  DECIMAL(14,4),   -- l12m_HTN_labandpath_payable
  l12m_htn_drg_payable                                         TINYINT,   -- l12m_HTN_DRG_payable
  l12m_htn_procedures_payable                                  DECIMAL(14,4),   -- l12m_HTN_procedures_payable
  l12m_htn_others_payable                                      DECIMAL(14,4),   -- l12m_HTN_others_payable
  last_claim_date                                              DATE,   -- last_claim_date
  last_claim_costblocks                                        TEXT,   -- last_claim_costblocks
  last_claim_facilities                                        TEXT,   -- last_claim_facilities
  last_claim_specialties                                       TEXT,   -- last_claim_specialties
  last_claim_dx_codes                                          TEXT,   -- last_claim_dx_codes
  last_claim_dx_desc                                           TEXT,   -- last_claim_dx_desc
  last_claim_medicines                                         TEXT,   -- last_claim_medicines
  last_claim_activities                                        TEXT,   -- last_claim_activities
  last_claim_payable                                           DECIMAL(14,4),   -- last_claim_payable
  flag_current_smoker_l12m                                     TINYINT,   -- flag_current_smoker_l12m
  last_smoking_evidence_date                                   DATE,   -- last_smoking_evidence_date
  flag_former_smoker_code                                      TINYINT,   -- flag_former_smoker_code
  flag_ckd_l12m                                                TINYINT,   -- flag_ckd_l12m
  flag_hypertensive_kidney_disease_l12m                        TINYINT,   -- flag_hypertensive_kidney_disease_l12m
  flag_kidney_failure_l12m                                     TINYINT,   -- flag_kidney_failure_l12m
  flag_acute_kidney_injury_l12m                                TINYINT,   -- flag_acute_kidney_injury_l12m
  flag_any_kidney_disease_l12m                                 TINYINT,   -- flag_any_kidney_disease_l12m
  flag_stroke_l12m                                             TINYINT,   -- flag_stroke_l12m
  flag_heart_failure_l12m                                      TINYINT,   -- flag_heart_failure_l12m
  flag_mi_l12m                                                 TINYINT,   -- flag_mi_l12m
  flag_other_cvd_l12m                                          TINYINT,   -- flag_other_cvd_l12m
  flag_dm_kidney_l12m                                          TINYINT,   -- flag_dm_kidney_l12m
  flag_dm_eye_l12m                                             TINYINT,   -- flag_dm_eye_l12m
  flag_dm_neuropathy_l12m                                      TINYINT,   -- flag_dm_neuropathy_l12m
  flag_dm_circulatory_l12m                                     TINYINT,   -- flag_dm_circulatory_l12m
  flag_dm_foot_l12m                                            TINYINT,   -- flag_dm_foot_l12m
  flag_amputation_l12m                                         TINYINT,   -- flag_amputation_l12m
  flag_dm_hypoglycaemia_l12m                                   TINYINT,   -- flag_dm_hypoglycaemia_l12m
  flag_dm_hyperglycaemic_crisis_l12m                           TINYINT,   -- flag_dm_hyperglycaemic_crisis_l12m
  flag_sepsis_l12m                                             TINYINT,   -- flag_sepsis_l12m
  flag_ischemic_heart_disease_l12m                             TINYINT,   -- flag_ischemic_heart_disease_l12m
  flag_dyslipidemia_l12m                                       TINYINT,   -- flag_dyslipidemia_l12m
  flag_obesity                                                 TINYINT,   -- flag_obesity
  flag_cad_mi_l12m                                             TINYINT,   -- flag_cad_mi_l12m
  flag_stroke_tia_l12m                                         TINYINT,   -- flag_stroke_tia_l12m
  flag_pad_l12m                                                TINYINT,   -- flag_pad_l12m
  flag_dm_retinopathy_l12m                                     TINYINT,   -- flag_dm_retinopathy_l12m
  flag_peripheral_neuropathy_l12m                              TINYINT,   -- flag_peripheral_neuropathy_l12m
  flag_dm_foot_ulcer_l12m                                      TINYINT,   -- flag_dm_foot_ulcer_l12m
  flag_major_amputation_l12m                                   TINYINT,   -- flag_major_amputation_l12m
  flag_dka_l12m                                                TINYINT,   -- flag_dka_l12m
  last_uacr_value                                              DECIMAL(14,4),   -- Last_UACR_Value
  last_uacr_date                                               DATE,   -- Last_UACR_Date
  ckd_stage_l12m                                               VARCHAR(200),   -- ckd_stage_l12m
  l12m_payable_diaborhtnrelated                                DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated
  l12m_payable_diaborhtnrelated_drugs_inside_network           DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_drugs_inside_network · new
  l12m_payable_diaborhtnrelated_inside                         DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_inside · new
  l12m_payable_diaborhtnrelated_outside                        DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_outside · new
  l12m_payable_diaborhtnrelated_drugs_outside_network          DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_drugs_outside_network · new
  l12m_payable_diaborhtnrelated_consultation_inside_network    DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_consultation_inside_network · new
  l12m_payable_diaborhtnrelated_consultation_outside_network   DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_consultation_outside_network · new
  l12m_payable_diaborhtnrelated_labandpath_inside_network      DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_labandpath_inside_network · new
  l12m_payable_diaborhtnrelated_labandpath_outside_network     DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_labandpath_outside_network · new
  l12m_payable_diaborhtnrelated_drg_inside_network             DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_DRG_inside_network · new
  l12m_payable_diaborhtnrelated_drg_outside_network            DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_DRG_outside_network · new
  l12m_payable_diaborhtnrelated_procedures_inside_network      DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_procedures_inside_network · new
  l12m_payable_diaborhtnrelated_procedures_outside_network     DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_procedures_outside_network · new
  l12m_payable_diaborhtnrelated_others_inside_network          DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_others_inside_network · new
  l12m_payable_diaborhtnrelated_others_outside_network         DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_others_outside_network · new
  payable_last24months_diaborhtnrelated                        DECIMAL(14,4),   -- payable_last24months_DiaborHTNrelated
  payable_since2024_diaborhtnrelated                           DECIMAL(14,4),   -- payable_since2024_DiaborHTNrelated
  l12m_payable_diaborhtnrelated_op                             DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_op
  l12m_payable_diaborhtnrelated_ip                             DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_ip
  l12m_payable_diaborhtnrelated_ed                             DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_ed
  l12m_payable_diaborhtnrelated_drugs                          DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_drugs
  l12m_payable_diaborhtnrelated_consultation                   DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_consultation
  l12m_payable_diaborhtnrelated_labandpath                     DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_labandpath
  l12m_payable_diaborhtnrelated_drg                            DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_DRG
  l12m_payable_diaborhtnrelated_procedures                     DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_procedures
  l12m_payable_diaborhtnrelated_others                         DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_others
  l12m_payable_diaborhtnrelated_phg                            DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_PHG
  l12m_payable_diaborhtnrelated_mediclinic                     DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_Mediclinic
  l12m_payable_diaborhtnrelated_nmc                            DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_NMC
  l12m_payable_diaborhtnrelated_burjeel                        DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_Burjeel
  l12m_payable_diaborhtnrelated_mubadala                       DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_Mubadala
  l12m_payable_diaborhtnrelated_otherproviders                 DECIMAL(14,4),   -- l12m_payable_DiaborHTNrelated_OtherProviders
  l12m_encounters_diaborhtnrelated                             INT,   -- l12m_encounters_DiaborHTNrelated
  l12m_encounters_op_diaborhtnrelated                          INT,   -- l12m_encounters_op_DiaborHTNrelated
  l12m_encounters_ed_diaborhtnrelated                          INT,   -- l12m_encounters_ed_DiaborHTNrelated
  l12m_encounters_ip_diaborhtnrelated                          INT,   -- l12m_encounters_ip_DiaborHTNrelated
  top_groupownerlevel_l12m_op_diaborhtnrelated_encounters      VARCHAR(200),   -- top_groupownerlevel_l12m_op_DiaborHTNrelated_encounters
  top_groupownerlevel_l12m_op_diaborhtnrelated_encounter_share DECIMAL(14,4),   -- top_groupownerlevel_l12m_op_DiaborHTNrelated_encounter_share
  providers_l12m_diaborhtnrelated                              INT,   -- providers_l12m_DiaborHTNrelated
  l12m_ed_visits_diaborhtnrelated                              INT,   -- l12m_ED_visits_DiaborHTNrelated
  l12m_ip_admissions_diaborhtnrelated                          INT,   -- l12m_IP_admissions_DiaborHTNrelated
  l12m_encounters_diaborhtnrelated_phg                         INT,   -- l12m_encounters_DiaborHTNrelated_PHG · new
  l12m_encounters_diaborhtnrelated_mediclinic                  INT,   -- l12m_encounters_DiaborHTNrelated_Mediclinic · new
  l12m_encounters_diaborhtnrelated_nmc                         INT,   -- l12m_encounters_DiaborHTNrelated_NMC · new
  l12m_encounters_diaborhtnrelated_burjeel                     INT,   -- l12m_encounters_DiaborHTNrelated_Burjeel · new
  l12m_encounters_diaborhtnrelated_mubadala                    INT,   -- l12m_encounters_DiaborHTNrelated_Mubadala · new
  l12m_encounters_diaborhtnrelated_otherproviders              INT,   -- l12m_encounters_DiaborHTNrelated_OtherProviders · new
  l12m_encounters_diaborhtnrelated_total                       INT,   -- l12m_encounters_DiaborHTNrelated_total · new
  PRIMARY KEY (member_id),
  SHARD KEY (member_id)
);
