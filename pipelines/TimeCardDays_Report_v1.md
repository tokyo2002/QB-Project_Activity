# Time Card Days — accounting-period hours by Business Unit and Project

Build sheet, **v1** · 2026-10-09 · App: Project Activity (`bg86uwfcw`) · Production

## Contents

- [0. Changelog](#0-changelog)
- [1. Design model (read first)](#1-design-model-read-first)
  - [1.1 Terms that look alike](#11-terms-that-look-alike)
- [2. Tables overview](#2-tables-overview)
- [3. Field type legend](#3-field-type-legend)
- [4. Critical implementation notes](#4-critical-implementation-notes)
- [5. Table specifications](#5-table-specifications)
- [6. Relationships](#6-relationships)
- [7. Lookup fields](#7-lookup-fields)
- [8. Summary (roll-up) fields](#8-summary-roll-up-fields)
- [9. Date logic](#9-date-logic)
- [10. Reports](#10-reports)
- [11. Build order](#11-build-order)
- [12. Open items, deferred work, and declined options](#12-open-items-deferred-work-and-declined-options)
- [13. Roles & permissions](#13-roles--permissions)
- [14. Validation checklist](#14-validation-checklist)
- [15. Pipelines](#15-pipelines)
- [16. One-time backfill](#16-one-time-backfill)
- [Appendix — conventions](#appendix--conventions)

---

## 0. Changelog

| Version | Date | Change |
|---|---|---|
| v1 | 2026-10-09 | First design. Daily child table, snapshot BU/project, accounting period 26th–25th, backfill from 2026-08-26. Day Key is numeric: `Record ID# × 10 + Day Index`. |

---

## 1. Design model (read first)

**Problem.** A Time Card (`bhm9822gc`) is one row per employee × task × week. Hours are stored in seven day columns. Accounting reports on a period that runs from the **26th of one month to the 25th of the next**, and a week can fall across two periods. Quickbase reports can't filter or group on "which day column", so a report on time cards can't split a week.

**Solution.** Add a child table, **Time Card Days**, with exactly **7 records per time card**, one per weekday. Each record carries:

- its **Work Date** and **Hours**
- a computed **Accounting Period**
- **snapshots** of the business unit and project as they stood when the card was last written

After that, every accounting report is an ordinary summary report on Time Card Days: filter on period, group by BU, then by project, and sum Hours.

```
Time Card (week of Sun 9/20/2026, Task → BU "CHART INC.", Project "X")
 ├─ Day 0  Sun 9/20  0.0 h  period 2026-09
 ├─ Day 1  Mon 9/21  8.0 h  period 2026-09
 ├─ …
 ├─ Day 5  Fri 9/25  8.0 h  period 2026-09
 └─ Day 6  Sat 9/26  2.0 h  period 2026-10   ← same card, next period
```

**What this design does:**

- **Time Cards remain the system of record.** Day records are derived. Nobody edits them by hand. They are written only by Pipeline A ([15](#15-pipelines)) and the backfill/refresh script ([16](#16-one-time-backfill)).
- **There are always 7 records, even for zero-hour days.** Zero rows mean an edit that clears a day overwrites the old value. No delete logic is needed. Reports filter `Hours > 0`.
- **Records are upserted on a unique key**, `Day Key` = `Time Card Record ID# × 10 + Day Index`. Card 98213 gets keys 982130 (Sun) through 982136 (Sat), and the card's ID is the key with its last digit dropped. Every writer is idempotent, so running a writer twice, or running the Pipeline and the backfill over the same card, can't create duplicates.
- **BU and project are snapshots, not lookups.** This was a user decision: re-running a closed period must return identical numbers even if a task is later reassigned to another project or BU. Snapshots refresh only when the card itself is written again: an edit, or a refresh run before the period is final ([9.3](#93-when-a-period-is-final)).

### 1.1 Terms that look alike

One Time Card Days record carries every one of these at once, and each value is correct:

| Field | Example value | What it means | Source |
|---|---|---|---|
| Week Beginning (TC fid 8) | 2026-09-20 | Sunday of the card's week. **Formula** `FirstDayOfWeek([Date])` | Time Card |
| Date (TC fid 9) | 2026-09-23 | Whatever day the user picked when creating the card. Any day in the week. **This is the authoritative field** | Time Card |
| Work Date | 2026-09-26 | The specific day these Hours belong to | Day record |
| Week Ending (TC fid 7) | 2026-09-26 | Saturday of the card's week | Time Card |
| Accounting Period | `2026-10` | The period the **Work Date** falls in, named by the month it **ends** in (Sep 26 – Oct 25) | Day record formula |
| Month (TC fid 77) | 9 | Calendar month of **Week Beginning**. **Do not use for accounting** | Time Card |
| BU Full Name (snapshot) | CHART INC. | New-style business unit, Task → Business Unit (TC fids 295–297, 309) | Snapshot |
| Legacy BU (snapshot) | Systems & VIP | Old category formula (TC fid 128). A different vocabulary, **not a duplicate** | Snapshot |
| Project Name (snapshot) | (task's project) | Task → Project (TC fid 300). What report 207 calls "project" | Snapshot |
| Time Card Title (snapshot) | ESR #123 – … | Display label covering all card types (TC fid 137) | Snapshot |

---

## 2. Tables overview

| Table | DBID | Status | Role in this design |
|---|---|---|---|
| Time Cards | `bhm9822gc` | Existing | Parent, system of record. ~123k records, ~760 new per week |
| **Time Card Days** | *(new)* | Specified | Child. 7 records per in-scope time card |
| Tasks | `biwfb28d9` | Existing | Source of BU and project, reached through TC lookups. Not touched |
| Business Units | *(existing, via Task fid 284)* | Existing | Not touched |

Expected size: from 2026-08-26 there are about 3k cards, so roughly **21k day records** at go-live. Growth is about 5.3k records per week. Extending the backfill to all history would mean about 860k records ([12](#12-open-items-deferred-work-and-declined-options), D2).

---

## 3. Field type legend

| Tag | Meaning |
|---|---|
| **A** | Authoritative: written by Pipeline A or the backfill script, and never edited by people |
| **S** | Snapshot: authoritative copy of a Time Card value as it was when written. Frozen until the card is written again |
| **D** | Derived: a formula, lookup or summary. Never written |

---

## 4. Critical implementation notes

These fail **silently**, with no error, just wrong numbers.

1. **Watch Date (fid 9), not Week Beginning (fid 8).** Week Beginning is a formula. A Pipeline "fields changed" filter **never fires on a formula field**. Watch the editable inputs: Date, the 7 day fields, Related Task, and Related Employee ([15](#15-pipelines), A-trigger).
2. **A snapshot can't see a Task change.** If someone sets or changes a Task's BU after the card was last written, the day records keep the old (possibly blank) value. That is intended for closed periods. For open periods it is handled by the refresh run ([9.3](#93-when-a-period-is-final)). **This matters right now:** the new BU structure has been filling in since the week of 2026-08-09, and was only ~46% populated for the week of 2026-10-04.
3. **Blank day fields aren't zero.** A day column left empty arrives in the Pipeline as an empty string. Every Hours expression must default it: `{{ a.sunday or 0 }}`. Otherwise the upsert writes a blank, and in some report types a blank won't sum.
4. **Day Key must be set Unique *before* the first write.** Pipelines' bulk upsert merges on it. If it isn't unique, upsert behaves like insert and duplicates every day on every edit, which doubles the hours in every report.
   Day Key is **numeric** on purpose. A text key such as `98213-6` could be built two ways (`98,213-6`, `98213.0-6`) by a Pipeline or script formatting quirk, and each spelling would quietly become a separate record. A number has only one value. Give it 0 decimals and no thousands separator so it displays the same way it's stored.
5. **A period isn't final until the last week in it locks.** A card stays editable until it is 14 days past Week Beginning (TC fid 307), or longer if someone ticks Unlock Timecard. For the period ending Thu 2026-09-25, the last week starts Sun 09-20 and locks on **Mon 2026-10-05**. A report pulled on 09-26 is provisional ([9.3](#93-when-a-period-is-final)).
6. **Never `Hours = Total Regular Hours / 7`.** Spreading a week evenly is the approximation this whole design exists to avoid.
7. **Cascade delete through the relationship, not a Pipeline.** Set "delete child records when the parent is deleted" on relationship 3a. A Pipeline "on delete" trigger can't read the deleted record's ID reliably enough to clean up. Note the separate soft-delete checkbox, Delete Record (TC fid 268): see O4.
8. **Pause Pipeline A during bulk Time Card edits or imports.** Every touched card is one Pipeline run with about 10 steps. Run the refresh script afterward instead.

---

## 5. Table specifications

### 5.1 Time Card Days *(new)*

Key field: **Day Key** [before 3a]. Record name in reports: Time Card Title + Work Date.

| Field | Type | Tag | Value / formula | Notes |
|---|---|---|---|---|
| Record ID# | Record ID | D | — | |
| **Day Key** | Numeric, 0 decimals, no separators, **Unique**, Required | A | `TC Record ID# × 10 + Day Index`, e.g. card 98213 Saturday = `982136` | Upsert merge field. Set as key field [before 3a] |
| Related Time Card | Numeric (reference) | A | TC Record ID# | Relationship 3a |
| Day Index | Numeric, 0 decimals | A | 0 = Sun … 6 = Sat | |
| Work Date | Date | A | TC day-date field (fids 315–321) | Written, not a formula, so it can be checked for drift (below) |
| Hours | Numeric, 2 decimals | A | TC day-hours field (fids 23, 10, 11, 12, 13, 14, 24), blank → 0 | |
| Employee | User | S | TC Employee (fid 17) | User type so `[Current User]` filters work |
| BU Code | Text | S | TC fid 296 | |
| BU Name | Text | S | TC fid 297 | |
| BU Full Name | Text | S | TC fid 309 | Primary grouping. Blank → shown as "(no BU)" via the formula below |
| Legacy BU | Text | S | TC fid 128 | Hedge for O1. A live formula on TC, unrecoverable if not snapshotted |
| Project Name | Text | S | TC fid 300 | |
| Project Type | Text | S | TC fid 298 | |
| Time Card Title | Text | S | TC fid 137 | |
| Time Card Type | Text | S | TC fid 151 | |
| Hyderabad Project | Text | S | TC fid 273 | Report 207 scopes on this |
| Billable? | Checkbox | S | TC fid 299 | |
| Snapshot Written | Date/Time | A | Pipeline run time (`{{ time.now }}`) | Shows when the snapshot was last refreshed |
| Accounting Period | Formula – Text | D | [9.1](#91-accounting-period) | e.g. `2026-09` |
| Period Start | Formula – Date | D | [9.1](#91-accounting-period) | |
| Period End | Formula – Date | D | [9.1](#91-accounting-period) | |
| In Last Period | Formula – Checkbox | D | [9.2](#92-pre-computed-period-windows) | Drives the default report |
| In Current Period | Formula – Checkbox | D | [9.2](#92-pre-computed-period-windows) | |
| BU (report) | Formula – Text | D | `If(Trim([BU Full Name]) = "", "(no BU)", [BU Full Name])` | Group on this, not the raw field, so blanks get a visible label |
| TC - Week Beginning | Lookup | D | 4a | |
| TC - Timecard Locked | Lookup | D | 4b | |
| Date Drift | Formula – Checkbox | D | `[Work Date] <> [TC - Week Beginning] + Days([Day Index])` | True means the card's Date moved and this record wasn't rewritten. See check V6 |
| Key Mismatch | Formula – Checkbox | D | `[Day Key] <> [Related Time Card] * 10 + [Day Index]` | True means a writer built the key wrong. Should never be true. See check V6 |
| Provisional | Formula – Checkbox | D | `not [TC - Timecard Locked]` | Hours can still change |

### 5.2 Time Cards *(existing: add fields only)*

| Field | Type | Tag | Value / formula | Notes |
|---|---|---|---|---|
| Day Records - Hours | Summary | D | 5a | |
| Day Records - Count | Summary | D | 5b | |
| Day Records Out of Sync | Formula – Checkbox | D | `[Week Ending] >= Date(2026,8,26) and ([Day Records - Count] <> 7 or [Total Hours] <> [Day Records - Hours])` | [after 5a, 5b]. Update the date if the backfill is extended (D2) |

The existing "(at entry)" fields on Time Cards (fids 286–290) have **never been populated**: 0 records. This design does **not** use them. See O3.

---

## 6. Relationships

| ID | Parent → Child | Reference field | Settings |
|---|---|---|---|
| 3a | Time Cards → Time Card Days | Related Time Card | **Delete child records when the parent is deleted: ON.** Don't add "Add Time Card Day" buttons or embedded add forms; records are system-written only. [after Day Key is set as key] |

---

## 7. Lookup fields

On Time Card Days, through 3a:

| ID | Field | Source (Time Cards) |
|---|---|---|
| 4a | TC - Week Beginning | Week Beginning (fid 8) |
| 4b | TC - Timecard Locked | Timecard Locked (fid 307) |

BU and project are deliberately **not** lookups. See the snapshot decision in [1](#1-design-model-read-first).

---

## 8. Summary (roll-up) fields

On Time Cards, through 3a:

| ID | Field | Definition |
|---|---|---|
| 5a | Day Records - Hours | Total of Hours |
| 5b | Day Records - Count | Count of Time Card Days |

---

## 9. Date logic

### 9.1 Accounting period

A period runs from the 26th to the 25th and is **named by the month it ends in**. Confirm this naming with accounting (O2).

**Accounting Period** (text):
```
var date d = [Work Date];
var date p = If(Day($d) >= 26, AdjustMonth(FirstDayOfMonth($d), 1), FirstDayOfMonth($d));
ToText(Year($p)) & "-" & PadLeft(ToText(Month($p)), 2, "0")
```

**Period Start** (date):
```
var date d = [Work Date];
var date p = If(Day($d) >= 26, AdjustMonth(FirstDayOfMonth($d), 1), FirstDayOfMonth($d));
AdjustMonth($p, -1) + Days(25)
```

**Period End** (date):
```
var date d = [Work Date];
var date p = If(Day($d) >= 26, AdjustMonth(FirstDayOfMonth($d), 1), FirstDayOfMonth($d));
$p + Days(24)
```

`FirstDayOfMonth` is applied **before** `AdjustMonth`. That avoids the month-end clamp: `AdjustMonth(Jan 31, 1)` gives Feb 28, which would land in the right month here but is fragile in general.

**Worked examples:**

| Work Date | Day ≥ 26? | p | Period | Start – End |
|---|---|---|---|---|
| 2026-09-25 (Fri) | no | 2026-09-01 | `2026-09` | 2026-08-26 – 2026-09-25 |
| 2026-09-26 (Sat) | yes | 2026-10-01 | `2026-10` | 2026-09-26 – 2026-10-25 |
| 2026-12-28 | yes | 2027-01-01 | `2027-01` | 2026-12-26 – 2027-01-25 (year rolls over) |
| 2027-01-31 | yes | 2027-02-01 | `2027-02` | 2027-01-26 – 2027-02-25 |

The week of Sun 2026-09-20 splits: Sun through Fri go to `2026-09` and Sat goes to `2026-10`.

### 9.2 Pre-computed period windows

Accounting shouldn't have to build date filters by hand.

**In Current Period** (checkbox):
```
var date t = Today();
var date p = If(Day($t) >= 26, AdjustMonth(FirstDayOfMonth($t), 1), FirstDayOfMonth($t));
[Accounting Period] = ToText(Year($p)) & "-" & PadLeft(ToText(Month($p)), 2, "0")
```

**In Last Period** (checkbox): same as above, but with `var date t = Today();` replaced by:
```
var date t0 = Today();
var date p0 = If(Day($t0) >= 26, AdjustMonth(FirstDayOfMonth($t0), 1), FirstDayOfMonth($t0));
var date t = AdjustMonth($p0, -1);
```
`$t` is then the 1st of the previous period's month, which is always before the 26th, so `p` resolves to that month.

### 9.3 When a period is final

The date a period becomes final is **the Monday 15 days after the Sunday that starts the week containing the 25th** (Week Beginning + 15 days, when `Time Card Age > 14`).

| Period | Ends | Last week starts | Final (cards lock) |
|---|---|---|---|
| 2026-09 | Fri 2026-09-25 | Sun 2026-09-20 | Mon 2026-10-05 |
| 2026-10 | Sun 2026-10-25 | Sun 2026-10-25 | Mon 2026-11-09 |

On the final date, run the **refresh** (`backfill_time_card_days.py --period YYYY-MM`, [16](#16-one-time-backfill)). It re-writes every card in that period, so snapshots pick up any Task → BU changes made while the period was open. After that, numbers change only if someone unlocks a card. Pipeline A rewrites that card's snapshots, which is intended: the edit is the correction.

---

## 10. Reports

All on Time Card Days. Every report filters **Hours > 0**.

| # | Name | Type | Filter | Group / columns | Audience |
|---|---|---|---|---|---|
| R1 | Accounting – Last Period by BU & Project | Summary | In Last Period = true; Hours > 0 | Rows: BU (report) → Project Name. Value: Total Hours. Grand total on | Accounting (default) |
| R2 | Accounting – Last Period detail | Table | Same as R1 | BU (report), Project Name, Project Type, Employee, Work Date, Hours, Time Card Title, Provisional. Sort BU, Project, Work Date | Accounting |
| R3 | Accounting – Current Period by BU & Project | Summary | In Current Period = true; Hours > 0 | Same as R1 | Accounting |
| R4 | Accounting – Pick a Period | Summary | Accounting Period = *ask the user*; Hours > 0 | Same as R1 | Power users only (not on the dashboard) |
| R5 | Accounting – Last Period by Legacy BU | Summary | Same as R1 | Rows: Legacy BU → Project Name | Temporary, until O1 is decided |
| R6 | Admin – Sync problems | Table on **Time Cards** | Day Records Out of Sync = true | Record ID#, Employee, Week Beginning, Total Hours, Day Records - Hours, Day Records - Count | Admin |
| R7 | Admin – Date drift / key mismatch | Table | Date Drift = true OR Key Mismatch = true | Day Key, Related Time Card, Day Index, Work Date, TC - Week Beginning | Admin |

R1–R3 can also be shown as Hyderabad-only variants by adding `Hyderabad Project is not blank`, which matches report 207's scope (O5).

---

## 11. Build order

1. Create the table **Time Card Days**.
2. Add **Day Key** (Numeric, 0 decimals, no thousands separator). Set it **Unique** and **Required**, then make it the **key field** [before 3a].
3. Add the A and S fields from [5.1](#51-time-card-days-new).
4. Create relationship **3a**, with cascade delete ON [after step 2].
5. Add lookups **4a**, **4b**.
6. Add the formula fields from [5.1](#51-time-card-days-new): Accounting Period, Period Start, Period End, In Current Period, In Last Period, BU (report), Date Drift, Key Mismatch, Provisional [after 4a, 4b].
7. On Time Cards, add summaries **5a**, **5b**, then **Day Records Out of Sync** [after 5a, 5b].
8. Grant roles access ([13](#13-roles--permissions)).
9. Build **Pipeline A** ([15](#15-pipelines)) and test it on one card ([14](#14-validation-checklist), checks V1–V4). Export its YAML into `pipelines/`.
10. Turn Pipeline A **on**.
11. Run the **backfill** ([16](#16-one-time-backfill)). Order relative to step 10 doesn't matter, because writes are upserts on Day Key. Doing step 10 first means no edits are missed in between.
12. Build reports R1–R7.
13. Run the validation checklist ([14](#14-validation-checklist)).

---

## 12. Open items, deferred work, and declined options

| ID | Status | Item |
|---|---|---|
| O1 | **Open** | **Which BU does accounting mean?** Report 207 points to the new BU (Task → Business Unit). That only appears from about 2026-08-09 and is sparse before the week of 2026-10-04. Both are snapshotted, so the answer changes only which reports are kept (R1 vs R5). It doesn't change the table. If the answer is "new BU", ask accounting how to treat `(no BU)` hours in the 2026-09 period. |
| O2 | **Open** | Confirm with accounting that the period is named by the month it ends in (`2026-09` = Aug 26 – Sep 25). Changing the name later is a formula edit and needs no data rework. |
| O3 | **Open** | The Time Cards fields Department / Location / Discipline / Project / Business Unit (at entry), fids 286–290, exist but are empty. Find out who created them and why before adding parallel snapshots. If that effort is dead, consider deleting them later ("never delete before repointing" applies). |
| O4 | **Open** | **Delete Record (TC fid 268) soft delete.** If cards are marked rather than truly deleted, their day records keep counting. Decide whether to snapshot this flag and filter on it, or confirm that a later process hard-deletes these cards. |
| O5 | **Open** | Should accounting reports be all BUs, or Hyderabad-only like report 207? |
| O6 | **Open** | Pipelines usage: Pipeline A fires on every hours edit, about 760 cards per week × several edits. Check the account's Pipelines step/run allowance. |
| D1 | Deferred | **Automate the period-close refresh.** Now: run the script manually on the date in [9.3](#93-when-a-period-is-final). Later: a scheduled Pipeline that rewrites cards where `Week Ending ≥ Period Start` of the just-finalized period. It needs a loop over about 3k cards, so check O6 first. |
| D2 | Deferred | **Extend the backfill to earlier history.** Run the script with an earlier `--since` and update the cutoff date in "Day Records Out of Sync". ⚠ **Unrecoverable if postponed:** a snapshot captures BU and project *as they are when written*. Backfilling old periods later will record today's Task → BU/project assignments, not the ones in force at the time. If old periods will ever matter, back them up sooner rather than later. |
| X1 | **Declined** | *Formula-only split on Time Cards* (e.g. "Hours in start period" and "Hours in end period" fields). A report can't merge two hour columns into one group per period. |
| X2 | **Declined** | *Formula-query totals on an Accounting Periods table.* This gives totals only, and a BU × project split would need a record per combination. |
| X3 | **Declined** | *Live lookups for BU and project.* Re-running a closed period would change when a task is reassigned. The user requires reproducible numbers. |
| X4 | **Declined** | *Skip zero-hour days.* This would need delete logic for days cleared during an edit. Seven rows per card is simpler and self-correcting. |
| X5 | **Declined** | *Use the Month field (TC fid 77).* It's the calendar month of Week Beginning, not of each day. |

---

## 13. Roles & permissions

| Role | Time Card Days | Notes |
|---|---|---|
| Accounting (or whichever role they use) | View all | Needs view on reports R1–R5 |
| Employees (standard user roles) | None, or view own (`Employee = [Current User]`) | Not needed for this feature |
| Admin / Pipeline user | Full | Pipeline A and the script run as this user. **No other role** should have Add/Modify on Time Card Days |

---

## 14. Validation checklist

| # | Check | Expected |
|---|---|---|
| V1 | Create a test time card for the week of 2026-09-20 with Mon 8 and Sat 2 | 7 day records. Mon 8.0 in `2026-09`, Sat 2.0 in `2026-10`, the rest 0.0 |
| V2 | Edit that card and clear Monday | Same 7 records (Record ID#s unchanged). Mon is now 0.0. Still 7, no duplicates |
| V3 | Change the card's Date to a day in the following week | Same 7 records. Work Dates shift +7. R7 (Date Drift) is empty |
| V4 | Delete the test card | Its 7 day records are gone |
| V5 | Re-run the backfill for the same range | Day record count unchanged. Snapshot Written timestamps update |
| V6 | After the backfill: R6 and R7 | Both empty |
| V7 | Pick 3 cards across a period boundary and calculate their period hours by hand from the day columns | Matches R4 for those cards |
| V8 | Sum of Hours on Time Card Days with `Work Date` from 2026-08-30 to 2026-09-26 (whole weeks) | Equals Total Hours on Time Cards with Week Beginning from 2026-08-30 to 2026-09-20 |
| V9 | **Reproducibility:** export R4 for `2026-09`. Change the BU on one of those cards' Tasks (test task or revert afterward). Re-run R4 | **Identical numbers** |
| V10 | Edit an unrelated field on a card (e.g. Notes) | Pipeline A does not run (check the activity log) |

---

## 15. Pipelines

Store each Pipeline's exported YAML in this folder after building it: `pipelines/<name>.yaml`.

### Pipeline A — "Time Card Days: sync on change"

| Step | Type | Configuration |
|---|---|---|
| **a. Trigger** | Quickbase → Record created / updated, table Time Cards | **Fields to watch** (no-op guard): Date (9), Sunday (23), Monday (10), Tuesday (11), Wednesday (12), Thursday (13), Friday (14), Saturday (24), Related Task (57), Related Employee (15). Formula fields aren't used here; see [4](#4-critical-implementation-notes) #1 |
| **b. Condition** (boundary guard) | If | `Week Ending (7)` **≥ 2026-08-26**. Otherwise end. Update this together with D2 |
| **c. Prepare** | Quickbase → Prepare Bulk Record Upsert | Table: Time Card Days. **Merge field: Day Key** |
| **d.–j. Add rows ×7** | Quickbase → Add a Bulk Upsert Row | One per Day Index 0–6. Field mapping below |
| **k. Commit** | Quickbase → Commit Upserts | |

**Row mapping** (shown for Day Index 0, Sunday; change the day fields for the other six):

| Time Card Days field | Value |
|---|---|
| Day Key | `{{ (a.id | int) * 10 + 0 }}` (Mon `+ 1` … Sat `+ 6`) |
| Related Time Card | `{{ a.id }}` |
| Day Index | `0` |
| Work Date | `{{ a.sunday_day }}` (fid 315; Mon 316 … Sat 321) |
| Hours | `{{ a.sunday or 0 }}` (fid 23; Mon 10, Tue 11, Wed 12, Thu 13, Fri 14, Sat 24) |
| Employee | `{{ a.employee }}` (fid 17) |
| BU Code / BU Name / BU Full Name | `{{ a.business_unit_code }}` / `{{ a.business_unit_name }}` / `{{ a.business_unit_full_name }}` |
| Legacy BU | `{{ a.legacy_business_unit }}` |
| Project Name / Project Type | `{{ a.project_name }}` / `{{ a.project_type }}` |
| Time Card Title / Time Card Type | `{{ a.time_card_title }}` / `{{ a.time_card_type }}` |
| Hyderabad Project | `{{ a.hyderabad_project_project_identifier }}` |
| Billable? | `{{ a.billable }}` |
| Snapshot Written | `{{ time.now }}` |

Jinja field names are Pipelines' generated slugs. Check them against the field picker when building; they may differ.

**Invalid-input guard:** none needed. Every input either maps one-to-one or defaults to 0. A card with no Task writes blank BU/project, which shows as "(no BU)" in reports instead of being guessed.

---

## 16. One-time backfill

**Tool:** `scripts/backfill_time_card_days.py`, to be written after the table exists. It follows the same pattern as the deploy script: `op run --env-file=.qb.env --`, dry run by default, `--apply` to write.

- **Scope:** Time Cards with `Week Ending ≥ 2026-08-26` (`--since`), or every card overlapping one accounting period (`--period 2026-09`, used for the period-close refresh in [9.3](#93-when-a-period-is-final)).
- **Method:** query Time Cards for the same fields Pipeline A reads. Build 7 rows per card, with Day Key computed as an integer (`rid * 10 + day_index`), never via string formatting. Call `POST /v1/records` with `mergeFieldId = Day Key`, in batches of about 500 rows. It writes exactly what Pipeline A writes, so the two are interchangeable.
- **Volume:** about 3k cards, so about 21k rows, or about 45 API calls.
- **Dry run output:** card count, row count, total hours by Accounting Period. Compare these against Time Cards before using `--apply`.
- **Pipeline A** can stay on. Writes to Time Card Days don't trigger it.

---

## Appendix — conventions

- Phase IDs: relationships 3x, lookups 4x, summaries 5x. Never renumber them.
- "TC fid N" means field N on Time Cards (`bhm9822gc`).
- Field IDs for the new table are assigned when it's built. Record them here in v2.
