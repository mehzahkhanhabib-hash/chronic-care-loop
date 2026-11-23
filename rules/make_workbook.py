#!/usr/bin/env python3
"""rules/*.csv → CCC_Rulebook_Tables.xlsx (one sheet per table, with an Index) and rulebook_tables.sql (text columns, any SQL dialect).
Run from the repository root or from rules/:  python3 rules/make_workbook.py"""
import csv, glob, os, re
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
INDEX = [
 ('rule_loop_step', '§1 How to use this rulebook', 'The five steps of the loop and what each writes', 'kit: documentation'),
 ('rule_risk_component', '§2 Targeting', 'The five risk components, formula and cap', 'member.*_score'),
 ('rule_risk_band', '§2 Targeting', 'Every scoring band: input → points', 'member.*_score (computed in the extract)'),
 ('rule_tier', '§2 Targeting', 'Tier bands 1–4, what the campaign does, cadence', 'rule_tier'),
 ('rule_cadence', '§2 Targeting', 'Cadence steps per tier with the rulebook labels (Baseline, W2, M1 …)', 'rule_cadence'),
 ('rule_safety_flag', '§2 Targeting / §6.3', 'Safety flag: raised by, effect, event pathway', 'member.alert = RED; rule_priority'),
 ('rule_builder_field_group', '§2 Builder inputs', 'The six field groups the builder offers', 'compile_rule whitelist'),
 ('rule_ngql_guardrail', '§2 Written nGQL', 'The seven checks before a query can load', 'compile_rule'),
 ('rule_trigger', '§3 Rule table', 'The 14 triggers: pathway, raw data, fires when, class, variant switch, sign-off status', 'rule_trigger'),
 ('rule_condition', '§3 Rule table', "Each trigger's condition as column, operator, value (extract flag and rulebook threshold variants; cannot-tell; RED/AMBER)", '04_nightly.sql step 2 (generated)'),
 ('rule_action', '§3 Rule table', 'Next best action per trigger: owner, channel, done when, evidence, prerequisite, escalation', 'rule_trigger.action_*'),
 ('rule_trigger_state', '§3 Trigger states', 'fired / cannot tell / not fired', 'member_signal.state'),
 ('rule_campaign_mode', '§3 Campaign modes', 'automated vs business', 'campaign.trigger_mode'),
 ('rule_need_class', '§4 Within a member', 'Class order safety → acute → uncontrolled → barrier → verified gap → patient goal, with due days', 'rule_trigger.class_order; care_plan_need'),
 ('rule_slot', '§4 Within a member', 'CURRENT 1–3, NEXT 4–6, FUTURE', 'care_plan_need.slot'),
 ('rule_queue_order', '§4 Across members', 'Queue order: safety/RED → tier → campaign priority → hours past SLA', 'worklist.rank_no'),
 ('rule_contact_priority', '§4 Contact SLA', 'P1–P4 from alert colour, SLA days, channel', 'rule_priority'),
 ('rule_alert', '§4 Alert colour', 'RED / AMBER / YELLOW / GREEN: when and response', 'member.alert'),
 ('rule_decision_step', '§4 Decision tree', 'Steps A–J as the portal shows them', 'portal decision path'),
 ('rule_consent_gate', '§5 Consent gate', 'What is shown before consent and what is not rendered', 'portal LOCKED'),
 ('rule_call_stage', '§5 The call', 'The ten stages of the call and the portal step for each', 'portal call workflow'),
 ('rule_writeback', '§5 Write-back', 'Outcome → engine reaction → new calendar item', 'rule_followup; 05_followup.sql'),
 ('rule_gap_state', '§5 Write-back', 'Potential → Verified → Scheduled → Reported → Closed; who moves it', 'care_plan_need.gap_state'),
 ('rule_documentation', '§5 Minimum documentation', 'The six items of step J', 'outcome, action, member'),
 ('rule_event_type', '§1 and §6', 'The twelve event types the loop writes', 'kit table per event'),
 ('rule_guardrail', '§8 Guardrails', 'G0–G10 and where each is enforced', '04_nightly.sql, 05_followup.sql, portal'),
 ('rule_open_decision', '§8 Open decisions', 'The five open decisions', 'clinical lead / data platform'),
]
assert {n for n, *_ in INDEX} == {os.path.basename(p)[:-4] for p in glob.glob('rule_*.csv')}, 'INDEX and rules/*.csv are out of sync'
H = Font(bold=True, color='FFFFFF'); HF = PatternFill('solid', fgColor='13223A'); WR = Alignment(wrap_text=True, vertical='top')
wb = Workbook(); ws = wb.active; ws.title = 'Index'
ws.append(['CCC Rulebook · T2D and Hypertension · 20 Nov 2026 · the rules as data']); ws['A1'].font = Font(bold=True, size=13)
ws.append(['Source of truth for care intelligence. Edit a row here (or in rules/*.csv), regenerate, re-run. Every rule row is Draft until the clinical lead signs it off (§8).'])
ws.append([]); ws.append(['Sheet', 'Rulebook section', 'What it holds', 'Rows', 'Feeds in the kit'])
for c in ws[4]: c.font = H; c.fill = HF
sql = ['-- CCC Rulebook (T2D and Hypertension, 20 Nov 2026) as tables. Generated from rules/*.csv by rules/make_workbook.py.',
       "-- Every column is text here so the file loads on SingleStore, MySQL, PostgreSQL and SQLite unchanged; the kit's typed copies are in two-day-build/sql/02_rules.sql.", '']
q = lambda v: 'NULL' if v == '' else "'" + v.replace("'", "''") + "'"
for name, sec, what, feeds in INDEX:
    rows = list(csv.reader(open(name + '.csv', encoding='utf-8-sig'))); hdr, body = rows[0], rows[1:]
    ws.append([name, sec, what, len(body), feeds])
    s = wb.create_sheet(name[:31]); s.append(hdr)
    for c in s[1]: c.font = H; c.fill = HF
    for r in body: s.append(r)
    for i, h in enumerate(hdr, 1):
        s.column_dimensions[get_column_letter(i)].width = min(60, max(10, max(len(str(x[i - 1])) for x in [hdr] + body) + 2))
    for r in s.iter_rows(min_row=2):
        for c in r: c.alignment = WR
    s.freeze_panes = 'A2'
    cols = ', '.join(f'`{re.sub(r"[^a-z0-9_]", "_", h.lower())}` TEXT' for h in hdr)
    sql.append(f'-- {sec}: {what}'); sql.append(f'DROP TABLE IF EXISTS {name};\nCREATE TABLE {name} ({cols});')
    sql.append(f'INSERT INTO {name} VALUES\n' + ',\n'.join('  (' + ', '.join(q(v) for v in r) + ')' for r in body) + ';\n')
for col, wd in zip('ABCDE', [26, 24, 70, 6, 42]): ws.column_dimensions[col].width = wd
for r in ws.iter_rows(min_row=5):
    for c in r: c.alignment = WR
ws.freeze_panes = 'A5'
wb.save('CCC_Rulebook_Tables.xlsx'); open('rulebook_tables.sql', 'w', encoding='utf-8').write('\n'.join(sql))
print('wrote CCC_Rulebook_Tables.xlsx (%d sheets) and rulebook_tables.sql (%d tables)' % (len(wb.sheetnames), len(INDEX)))
