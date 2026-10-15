# Time Card Days (accounting-period hours)

Splits each weekly time card into 7 daily records. That lets accounting report hours for any date range, including their 26th-to-25th period, split by business unit and project. Project Activity app (`bg86uwfcw`), table Time Card Days (`bwe8cjimn`).

**Status (2026-10-15):** Live. The table was built 2026-10-14 by `scripts/build_time_card_days.py`, admin-only. All three Pipelines are on and tested. The backfill from Week Beginning 2026-08-23 is done: 4,988 cards, 34,916 day records, and R6/R7/R8 are empty. Next: accounting checks (V7–V9) and the open questions below.

## Files

| File | What it is |
|---|---|
| [`TimeCardDays_Report_v2.md`](TimeCardDays_Report_v2.md) | Build sheet (current): design, fields, Pipelines, tests, results |
| [`PipelineA_Upsert_Build.md`](PipelineA_Upsert_Build.md) | Step-by-step build of Pipeline A (upsert version) |
| [`time_card_days_fields.json`](time_card_days_fields.json) | Field IDs, written by `scripts/build_time_card_days.py` |
| [`YAML/`](YAML/) | Exported Pipeline YAML. Re-export after every change |

The v1 build sheet (`TimeCardDays_Report_v1.md`) was deleted by Kris on 2026-10-15. v2 replaces it, and its changelog covers v1. The file is still in git history: `git show 6fdef35:pipelines/TimeCardDays_Report_v1.md`.

## Decisions

| Date | Decision |
|---|---|
| 2026-10-09 | Use a daily child table (Time Card Days) written by a Pipeline. Chosen over formula-only or formula-query options. |
| 2026-10-09 | Snapshot BU and project onto each day record. Re-running a closed period must return identical numbers. |
| 2026-10-09 | Project means Task → Project Name (TC fid 300), the same as report 207. |
| 2026-10-09 | Day Key is numeric, `Time Card Record ID# × 10 + Day Index`, and Unique. Every writer upserts on it, so edits update the same 7 records and can't duplicate them. Numeric instead of text, so formatting can't produce a second spelling of the same key. |
| 2026-10-09 | Pipeline A re-reads the card before writing and stops if the card was deleted. This handles quick repeated saves (v2). |
| 2026-10-09 | Backfill from 2026-08-26 (the start of the 2026-09 period). May go further back later. |
| 2026-10-15 | Backfill and later refreshes go through Pipeline A, triggered by the Refresh Day Records checkbox (TC fid 329), instead of a script. |
| 2026-10-15 | Related Task and Related Employee are assumed not to change after entry, so Pipeline A doesn't watch them (D4). |

## Open

- Which BU accounting means: new (Task → Business Unit) or Legacy (TC fid 128). Both are snapshotted until they decide. Asking accounting.
- Period naming: `2026-09` = Aug 26 – Sep 25? Confirm with accounting.
- The other items are listed in section 12 of the build sheet.
