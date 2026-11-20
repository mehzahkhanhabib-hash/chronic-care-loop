# Chronic Care Loop

Finds members with type 2 diabetes and hypertension who need care, builds their care plan from the CCC Rulebook, puts them on a nurse's call list, and learns from every call.

## What's in this folder

| Folder | What it is | Who uses it |
|--------|------------|-------------|
| `1-care-portal/` | **Care coordinator portal.** The nurse's workstation: call queue, consent, Member 360, care plans linked to actions, analytics. | Nurses, coordinators |
| `2-cohort-campaign-builder/` | **Cohort & campaign builder.** Choose members with rules over raw data, then turn the cohort into a campaign. | Population health |
| `3-care-studio/` | **Care studio.** All three screens in one flow: ① builder → ② care intelligence (risk, triggers, care plan) → ③ portal. | Demos, clinical leads |
| `4-data-model/` | **The data model that drives all three.** Interactive model page, PostgreSQL and SQLite schemas, and the **rule database** (`rules/`). | Developers, analysts, clinical sign-off |
| `server/` | The backend: loads the extract, runs the rules every night, and serves the apps and the API. Python only, nothing to install. | Developers |
| `docs/` | `HANDOFF.md` (for developers), `HOSTING.md`, `DEMO.md` (how to show it), and the executive briefing. | Everyone |

## Run it (2 minutes)

1. Install Python 3.10 or later.
2. Start the server:
   - macOS / Linux: `./run.sh`
   - Windows: double-click `run.bat`
3. Open http://localhost:8000/

On first start, the server loads the 24-member sample extract in `server/data/raw/` and runs the nightly rules once. Everything you then see in the apps comes from that database.

You can also open any `.html` file directly, without the server. It then runs on built-in demo data, which is fine for a walkthrough but not connected to the rules.

## Load your full extract

```bash
cd server
python3 -m backend.ingest path/to/member_features.tsv --glossary data/raw/glossary.tsv
python3 -m backend.engine
```

## Change a rule

Edit the CSV in `4-data-model/rules/`, for example `rule_trigger.csv` or `rule_condition.csv`. Then restart the server and run the nightly. `4-data-model/rules/README.md` explains every table and how to track care plans through to actions.

## Before you share this folder

`server/data/raw/member_features_sample.tsv` holds 24 real rows of the member extract. The IDs are masked, but they are still claims-derived health data. Share the folder only inside the approved environment. To share it more widely, delete that file first. The apps still run on their demo data without it.
