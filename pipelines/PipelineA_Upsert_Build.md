# Pipeline A — upsert version: build steps

Rebuild of **"Create/Update Time Card Days from New/Updated Time Card"** (YAML in [`YAML/`](YAML/)) so one path handles both new and edited cards. Design and reasons: [TimeCardDays_Report_v2.md](TimeCardDays_Report_v2.md), sections 4 and 15.

What changes from the current version (reviewed 2026-10-15):

| | Current | Upsert version |
|---|---|---|
| Events | Created only | Created **and** updated |
| Watched fields | 7 days + Week Beginning (a formula, never fires) | 7 days + **Date**, Related Task, Related Employee |
| Source of values | Trigger | **Re-read card** (step b) |
| Guard | Action = add | Card found **and** Week Ending ≥ 2026-08-26 |
| Write | 7 × Create Record | **Prepare upsert → 7 rows → Commit**, merged on Day Key |
| Blank hours | Blank | **0** |
| Legacy BU, Hyderabad Project, Snapshot Written | Not written | Written |

The 21 records written on 2026-10-15 already have correct Day Keys, so the upsert merges onto them. It never duplicates them.

---

## Before you start

1. **Turn the pipeline off.** Cards created while it's off get no day records. That's fine: the backfill/refresh script writes the same upserts and fills them in afterward.
2. Pick every field from the **field picker**. Don't type slugs. The slugs below are the ones Pipelines generated in the current version, or best guesses where marked *(check)*.
3. Step letters below assume trigger = **a** and re-read = **b**. If Pipelines assigns different letters, use those.

---

## Steps

### a. Trigger — Quickbase → On New Event

| Setting | Value |
|---|---|
| Table | Time Cards `bhm9822gc` |
| Events | **Record added** and **Record updated** (both ticked) |
| Trigger on all fields | **No** |
| Trigger fields | Date (9), Sunday (23), Monday (10), Tuesday (11), Wednesday (12), Thursday (13), Friday (14), Saturday (24), **Refresh Day Records (329)**, a checkbox for refreshing cards on demand (added 2026-10-15). Related Task (57) and Related Employee (15) left out for now: assumed not to change after entry (build sheet D4) |

**Remove Week Beginning (8)** from the trigger fields. It's a formula (critical note #1). The trigger's export fields can be trimmed to just Record ID#, because nothing after step b reads from **a**.

### b. Re-read the card — Quickbase → Look Up a Record

| Setting | Value |
|---|---|
| Table | Time Cards `bhm9822gc` |
| Record ID# | `{{ a.id }}` |
| If not found | **Continue** (don't fail) |
| Fields to return | Week Ending (7), Week Beginning (8), Sunday (23), Monday (10), Tuesday (11), Wednesday (12), Thursday (13), Friday (14), Saturday (24), Employee (17), Business Unit Code (296), Business Unit Name (297), Business Unit Full Name (309), Legacy BU (128), Project Name (300), Project Type (298), Time Card Title (137), Time Card Type (151), Hyderabad Project (273), Billable? (299) |

Every later step reads from **b**, never **a** (critical note #9: overlapping saves).

### c. Condition — If

**b** Record ID# **is not empty** AND **b** Week Ending **is on or after** 2026-08-26.

- **Yes:** steps d–l.
- **No:** Stop. The card was deleted mid-run, or it's older than the backfill window.

### d. Prepare Bulk Record Upsert — inside "Yes"

| Setting | Value |
|---|---|
| Table | Time Card Days `bwe8cjimn` |
| **Merge field** | **Day Key (6)** |
| Fields | Day Key (6), Day Index (7), Work Date (8), Hours (9), Employee (10), BU Code (11), BU Name (12), BU Full Name (13), Legacy BU (14), Project Name (15), Project Type (16), Time Card Title (17), Time Card Type (18), Hyderabad Project (19), Billable? (20), Snapshot Written (21), Related Time Card (22) |

### e.–k. Add a Bulk Upsert Row × 7

**Same on every row:**

| Field (fid) | Value |
|---|---|
| Related Time Card (22) | `{{ b.id }}` |
| Employee (10) | `{{ b.employee.email }}` |
| BU Code (11) | `{{ b.business_unit_code }}` |
| BU Name (12) | `{{ b.business_unit_name }}` |
| BU Full Name (13) | `{{ b.business_unit_full_name }}` |
| Legacy BU (14) | `{{ b.legacy_business_unit }}` *(check)* |
| Project Name (15) | `{{ b.project_name }}` |
| Project Type (16) | `{{ b.project_type }}` |
| Time Card Title (17) | `{{ b.time_card_title }}` |
| Time Card Type (18) | `{{ b.time_card_type }}` |
| Hyderabad Project (19) | `{{ b.hyderabad_project }}` *(check, from fid 273)* |
| Billable? (20) | `{{ b.billable }}` |
| Snapshot Written (21) | `{{ time.now }}` |

**Different on each row:**

| Row | Day Key (6) | Day Index (7) | Work Date (8) | Hours (9) |
|---|---|---|---|---|
| e. Sun | `{{ (b.id \| int) * 10 + 0 }}` | `0` | `{{ b.week_beginning + time.delta(days=0) }}` | `{{ b.sunday or 0 }}` |
| f. Mon | `{{ (b.id \| int) * 10 + 1 }}` | `1` | `{{ b.week_beginning + time.delta(days=1) }}` | `{{ b.monday or 0 }}` |
| g. Tue | `{{ (b.id \| int) * 10 + 2 }}` | `2` | `{{ b.week_beginning + time.delta(days=2) }}` | `{{ b.tuesday or 0 }}` |
| h. Wed | `{{ (b.id \| int) * 10 + 3 }}` | `3` | `{{ b.week_beginning + time.delta(days=3) }}` | `{{ b.wednesday or 0 }}` |
| i. Thu | `{{ (b.id \| int) * 10 + 4 }}` | `4` | `{{ b.week_beginning + time.delta(days=4) }}` | `{{ b.thursday or 0 }}` |
| j. Fri | `{{ (b.id \| int) * 10 + 5 }}` | `5` | `{{ b.week_beginning + time.delta(days=5) }}` | `{{ b.friday or 0 }}` |
| k. Sat | `{{ (b.id \| int) * 10 + 6 }}` | `6` | `{{ b.week_beginning + time.delta(days=6) }}` | `{{ b.saturday or 0 }}` |

Inside the brackets, the bar is a plain `|` (it's escaped only for this table). Keep Day Key as arithmetic. Never join text (critical note #4).

### l. Commit Upsert

No settings.

---

## Test, then turn on

Run by hand against one **test card** (test task, week with Week Ending ≥ 2026-08-26). Checks from section 15:

| Check | Do | Expect |
|---|---|---|
| V1 | New card, week of 2026-09-20, Mon 8 and Sat 2 | 7 records. Mon 8.0 in `2026-09`, Sat 2.0 in `2026-10`, the rest **0.0**. Key Mismatch false |
| V2 | Clear Monday | Same 7 Record ID#s, Mon now 0.0 |
| V3 | Move the Date to the next week | Same 7 records, Work Dates +7, Date Drift false |
| V10 | Edit only Notes | Pipeline doesn't run |
| V11 | Save Mon = 4 then Mon = 6 within seconds | Mon = 6.0, card not on R6 |
| V12 | Save, then delete straight away | Run stops at c. No records left for that card |
| V4 | Delete through Delete Record | Card and its 7 records gone |

Also check on one record that **Hyderabad Project, Legacy BU and Snapshot Written** are filled in. If not, the slug in that row is wrong.

Then turn it on. Run the backfill/refresh for cards created while it was off, and check that R6, R7 and R8 are empty.
