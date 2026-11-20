# How to show it (10-minute demo)

The demo tells one story: from raw claims data, to a nurse's call, to the next night's update. Start the server and open http://localhost:8000/ before the meeting. If you need a clean start, delete `server/data/ccl.db` and restart.

| Minute | Screen | Do | Say |
|--------|--------|----|-----|
| 0–1 | **Overview** (`index.html`) | Point at the four products. | "One loop: choose who, score and plan, call, learn. One database and one rulebook drive all of it." |
| 1–4 | **2 · Cohort & campaign builder** | Add *Has condition: Type 2 diabetes*, then *Latest HbA1c ≥ 9*. Watch the count and the funnel change. Add an *LDL* rule. Open **Who matches**. Click **Save** and **Use in a campaign**, step through, then **Hand off**. | "Every number is a live query on the member extract. Rules use raw data only: risk and triggers come later. LDL isn't in our extract, and the builder says so instead of guessing. Hand-off runs care intelligence now; in production it runs nightly." |
| 4–6 | **3 · Care studio, screen ②** | Open the top member. Show the five risk parts, the tier, the alert colour and the ordered care plan. | "R = C+M+K+U+A gives the tier. The alert colour and the P1–P4 call priority come from the rule database. Needs are ordered safety first, and only the top three go to the nurse." |
| 6–9 | **1 · Care portal** | Show the queue: RED, P1 members first (same-day), then the rest by tier. Open Ahmed Saleh (m133): a hypoglycaemia safety need, P1. His record is locked because consent isn't on record yet. Call him and log consent: the record unlocks. Open **Care plans** and mark the first need **Done**: the next need moves into CURRENT. Open **Actions**: each current need has exactly one action. | "Nothing clinical shows before consent. Every decision is written back. Done promotes the next need; Declined holds it for 90 days; Not reached schedules a retry. A nurse's done only *reports* the gap. It closes when the claim arrives." |
| 9–10 | **4 · Data model** | Open the model view, then step 16 of the walkthrough. Optionally, open `rules/rule_trigger.csv`. | "29 tables, six groups. The rules are data: clinical leads sign them off, and changing a CSV changes the loop. We track every need through to its action and outcome." |

## If someone asks…

- **"Is this real data?"** Yes: 24 masked members from the extract. Names are generated, not real.
- **"How do we know it works?"** Watch `GET /api/tracking`. Needs should move from *Reported* to *Closed in claims*, and RED/AMBER counts should fall night over night (rulebook §7). Nurse clicks alone don't count as impact.
- **"What's not done yet?"** Clinical sign-off of the thresholds, single sign-on, PostgreSQL, the telephony integration and the full extract pipeline. See `HANDOFF.md`.

## Showing it without the server

- Open any HTML file directly. It runs on demo data, which is enough for a screen walkthrough.
- Or share the private gallery of the final screens, captured from the live backend.
