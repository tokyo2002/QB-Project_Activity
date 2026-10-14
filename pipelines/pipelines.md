# Pipelines

Quickbase Pipelines, and the scripts that support them, for the Project Activity app (`bg86uwfcw`). Export each Pipeline's YAML into this folder after building it or changing it.

## Time Card Days (accounting-period hours)

Splits each weekly time card into 7 daily records. That lets accounting report hours for any date range, including their 26th-to-25th period, split by business unit and project.

**Status:** Table built 2026-10-14 (`bwe8cjimn`, empty), by `scripts/build_time_card_days.py`. Roles set (admin-only). Next: the delete Pipelines, Pipeline A, and the backfill. Build sheet: [`TimeCardDays_Report_v2.md`](TimeCardDays_Report_v2.md) (current). v1 is kept for history.

### Decisions

| Date | Decision |
|---|---|
| 2026-10-09 | Use a daily child table (Time Card Days) written by a Pipeline. Chosen over formula-only or formula-query options. |
| 2026-10-09 | Snapshot BU and project onto each day record. Re-running a closed period must return identical numbers. |
| 2026-10-09 | Project means Task → Project Name (TC fid 300), the same as report 207. |
| 2026-10-09 | Day Key is numeric, `Time Card Record ID# × 10 + Day Index`, and Unique. Every writer upserts on it, so edits update the same 7 records and can't duplicate them. Numeric instead of text, so formatting can't produce a second spelling of the same key. |
| 2026-10-09 | Pipeline A re-reads the card before writing and stops if the card was deleted. This handles quick repeated saves (v2). |
| 2026-10-09 | Backfill from 2026-08-26 (the start of the 2026-09 period). May go further back later. |

### Open

- Which BU accounting means: new (Task → Business Unit) or Legacy (TC fid 128). Both are snapshotted until they decide. Asking accounting.
- Period naming: `2026-09` = Aug 26 – Sep 25? Confirm with accounting.
- The other items are listed in section 12 of the build sheet.

## NPD Account Sync

Runs on a schedule and calls a remote API once for each unique AFE or subledger number per NPD project, then writes the result back to Quickbase.

**Status:** Live (2026-10-12). Build sheet: [`NPDAccountSync_Report_v1.md`](NPDAccountSync_Report_v1.md).

NPD Investments fields: 13 First Use of Account Number, 14 API Sync Error, 16 API Last Synced, 17 Account Number Valid. Reports: 6 Values to call, 7 Errors, 8 Data cleanup.
