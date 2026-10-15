# Time Card Days — accounting-period hours by Business Unit and Project

Build sheet, **v2** · 2026-10-09 · App: Project Activity (`bg86uwfcw`) · Production

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
- [17. Time Cards field audit and cleanup](#17-time-cards-field-audit-and-cleanup)
- [Appendix — conventions](#appendix--conventions)

---

## 0. Changelog

| Version | Date | Change |
|---|---|---|
| v2 (amended) | 2026-10-15 | Pipeline A rebuilt as a bulk upsert and tested (V1–V3, V10, V11). Backfill done through Pipeline A, and its result is recorded in [16](#16-one-time-backfill). Day Records Out of Sync now rounds hours to 2 decimals. Added D4 (Related Task and Related Employee not watched). |
| v2 (amended) | 2026-10-14 | Orphan (fid 37) is now `[TC - Record ID#] = 0` instead of `IsNull(...)`: a numeric lookup with no parent reads as 0, so 0 is the reliable test. Changed live by Kris; script and sheet updated to match. |
| v2 (amended) | 2026-10-14 | Rewrote [15](#15-pipelines) as a step-by-step build plan with the real field IDs: build order B → Delete Record step → A, Pipeline B as Search + loop delete, Pipeline A's two guards merged into one condition (step c), a full 7-row mapping table, and the tests for each Pipeline. |
| v2 (amended) | 2026-10-14 | **Quickbase has no cascade delete.** Earlier versions relied on a relationship setting that doesn't exist. Day records are now removed by a step added to the Delete Record (fid 268) Pipeline, plus **Pipeline B**, a nightly orphan sweep. Added the lookup 4c TC - Record ID# and the formula Orphan. Reports filter `Orphan = false`. Rewrote critical note #7, relationship 3a, build order steps 4 and 9–10, and check V4. Added V13. |
| v2 (amended) | 2026-10-14 | Added [17](#17-time-cards-field-audit-and-cleanup), a field audit of Time Cards with a proposed cleanup. Updated O3 and O4 with what the audit found. No change to the design. |
| v2 | 2026-10-09 | Pipeline A handles quick repeated saves: (1) step b re-reads the card's **current** values instead of using the trigger's copy, so a run that finishes late can't overwrite newer hours with older ones; (2) step c stops if the card has been deleted, so a late run can't recreate orphan day records after the cascade delete. Field mapping moves from `a.` to `b.`. Added critical note #9 and checks V11–V12. |
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
| **Time Card Days** | `bwe8cjimn` | Built 2026-10-14 (no records yet) | Child. 7 records per in-scope time card |
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
3. **Blank day fields aren't zero.** A day column left empty arrives in the Pipeline as an empty string. Every Hours expression must default it: `{{ b.sunday or 0 }}`. Otherwise the upsert writes a blank, and in some report types a blank won't sum.
4. **Day Key must be set Unique *before* the first write.** Pipelines' bulk upsert merges on it. If it isn't unique, upsert behaves like insert and duplicates every day on every edit, which doubles the hours in every report.
   Day Key is **numeric** on purpose. A text key such as `98213-6` could be built two ways (`98,213-6`, `98213.0-6`) by a Pipeline or script formatting quirk, and each spelling would quietly become a separate record. A number has only one value. Give it 0 decimals and no thousands separator so it displays the same way it's stored.
5. **A period isn't final until the last week in it locks.** A card stays editable until it is 14 days past Week Beginning (TC fid 307), or longer if someone ticks Unlock Timecard. For the period ending Thu 2026-09-25, the last week starts Sun 09-20 and locks on **Mon 2026-10-05**. A report pulled on 09-26 is provisional ([9.3](#93-when-a-period-is-final)).
6. **Never `Hours = Total Regular Hours / 7`.** Spreading a week evenly is the approximation this whole design exists to avoid.
7. **Quickbase has no cascade delete.** Deleting a Time Card leaves its 7 day records behind as orphans, and they keep counting in reports. Two layers handle this ([15](#15-pipelines)). (1) The existing Delete Record Pipeline deletes the card's day records (`Related Time Card` = the card's ID) **before** it deletes the card, while the ID is still known. Delete Record (TC fid 268) is the trigger for the hard delete, not a soft delete: a checked card is deleted, which is why the audit found no checked cards (O4). (2) **Pipeline B** sweeps nightly for orphans left by any other route: an admin deleting cards by hand or in bulk, or a late Pipeline A run (#9). Until the sweep runs, the **Orphan** formula (true when the lookup TC - Record ID# is 0) keeps them out of every report.
8. **Pause Pipeline A during bulk Time Card edits or imports.** Every touched card is one Pipeline run with about 10 steps. Run the refresh script afterward instead.
9. **Quick repeated saves start overlapping Pipeline runs.** Someone saving a card twice in a few seconds starts two runs of Pipeline A, and they can finish in either order. If the rows were built from the trigger's copy of the card, a late-finishing older run would overwrite newer hours, and a run for a card deleted in the meantime would recreate its 7 records with no parent. Pipeline A therefore **re-reads the card** (step b) and **stops if it's gone** (step c). A small window remains: run 1 re-reads, run 2 re-reads and commits, then run 1 commits. That needs two saves within the second or two a run takes. The **Day Records Out of Sync** flag (R6) shows any card where it happens, and the next edit or refresh run corrects it.

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
| TC - Record ID# | Lookup | D | 4c | Blank once the card is deleted |
| Date Drift | Formula – Checkbox | D | `IsNull([Work Date]) or [Work Date] <> [TC - Week Beginning] + Days([Day Index])` (blank Work Date added 2026-10-14) | True means the card's Date moved and this record wasn't rewritten. See check V6 |
| Key Mismatch | Formula – Checkbox | D | `IsNull([Day Index]) or [Day Index] < 0 or [Day Index] > 6 or [Day Key] <> [Related Time Card] * 10 + [Day Index]` (updated 2026-10-14, D3) | True means a writer built the key wrong. Should never be true. See check V6 |
| Provisional | Formula – Checkbox | D | `not [TC - Timecard Locked]` | Hours can still change |
| Orphan | Formula – Checkbox | D | `[TC - Record ID#] = 0` | Test for 0, not `IsNull`: a numeric lookup with no parent record reads as 0, and any value above 0 means the card exists (changed 2026-10-14). True means the card was deleted and Pipeline B hasn't swept this record yet. Every report filters it out. See critical note #7 |

### 5.1.1 As built (2026-10-14)

Table `bwe8cjimn` (alias `_DBID_TIME_CARD_DAYS`), built by `scripts/build_time_card_days.py`. IDs are also in [`time_card_days_fields.json`](time_card_days_fields.json). Pipeline A and the backfill script use these.

| fid | Field |
|---|---|
| 6 | Day Key |
| 7 | Day Index |
| 8 | Work Date |
| 9 | Hours |
| 10 | Employee |
| 11 | BU Code |
| 12 | BU Name |
| 13 | BU Full Name |
| 14 | Legacy BU |
| 15 | Project Name |
| 16 | Project Type |
| 17 | Time Card Title |
| 18 | Time Card Type |
| 19 | Hyderabad Project |
| 20 | Billable? |
| 21 | Snapshot Written |
| 22 | Related Time Card |
| 23 | TC - Record ID# |
| 24 | TC - Week Beginning |
| 25 | TC - Timecard Locked |
| 26 | Accounting Period |
| 27 | Period Start |
| 28 | Period End |
| 29 | In Current Period |
| 32 | In Last Period |
| 33 | BU (report) |
| 34 | Date Drift |
| 35 | Key Mismatch |
| 36 | Provisional |
| 37 | Orphan |

Fids 30–31 were throwaway test fields, already deleted. Day Key is Unique and Required. The table's key field is still Record ID# (fid 3). Upserts only need Day Key to be Unique.

### 5.2 Time Cards *(existing: add fields only)*

| Field | Type | Tag | Value / formula | Notes |
|---|---|---|---|---|
| Day Records - Hours (fid 326) | Summary | D | 5a | |
| Day Records - Count (fid 327) | Summary | D | 5b | |
| Refresh Day Records (fid 329) | Checkbox | — | Admin only | Pipeline A trigger field. Changing it either way rebuilds the card's 7 day records. Not on user forms |
| Time Card Day records (fid 324) | Report link | D | Created automatically with relationship 3a | Not on any form. Can be embedded on an admin form to show a card's day records |
| ~~Add Time Card Day (fid 325)~~ | Formula – URL | D | Created automatically with relationship 3a | **Deleted 2026-10-14**: day records are system-written only (relationship 3a) |
| Day Records Out of Sync (fid 328) | Formula – Checkbox | D | `[Week Ending] >= Date(2026,8,26) and ([Day Records - Count] <> 7 or Round([Total Hours], 0.01) <> Round([Day Records - Hours], 0.01))` | [after 5a, 5b]. Update the date if the backfill is extended (D2). Round added 2026-10-15: the summed hours can carry a floating-point remainder (40.839999… vs 40.84 on card 549541), which flagged a correct card |

The existing "(at entry)" fields on Time Cards (fids 286–290) have **never been populated**: 0 records. This design does **not** use them. See O3 and [17](#17-time-cards-field-audit-and-cleanup).

---

## 6. Relationships

| ID | Parent → Child | Reference field | Settings |
|---|---|---|---|
| 3a | Time Cards → Time Card Days | Related Time Card | Quickbase has **no cascade delete**. Deleting is handled by Pipelines (critical note #7). Don't add "Add Time Card Day" buttons or embedded add forms; records are system-written only. [after Day Key is set Unique] |

---

## 7. Lookup fields

On Time Card Days, through 3a:

| ID | Field | Source (Time Cards) |
|---|---|---|
| 4a | TC - Week Beginning | Week Beginning (fid 8) |
| 4b | TC - Timecard Locked | Timecard Locked (fid 307) |
| 4c | TC - Record ID# | Record ID# (fid 3). Feeds Orphan |

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

**In Last Period** (checkbox): same as above, but with `var date t = Today();` replaced by the lines below. Formula variable names must be **letters only**: Quickbase rejects `$t0` or `$p0` as a syntax error (found 2026-10-14).
```
var date now = Today();
var date pc = If(Day($now) >= 26, AdjustMonth(FirstDayOfMonth($now), 1), FirstDayOfMonth($now));
var date t = AdjustMonth($pc, -1);
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

All on Time Card Days. Every report filters **Hours > 0** and **Orphan = false**, except R6–R8.

| # | Name | Type | Filter | Group / columns | Audience |
|---|---|---|---|---|---|
| R1 | Accounting – Last Period by BU & Project | Summary | In Last Period = true; Hours > 0 | Rows: BU (report) → Project Name. Value: Total Hours. Grand total on | Accounting (default) |
| R2 | Accounting – Last Period detail | Table | Same as R1 | BU (report), Project Name, Project Type, Employee, Work Date, Hours, Time Card Title, Provisional. Sort BU, Project, Work Date | Accounting |
| R3 | Accounting – Current Period by BU & Project | Summary | In Current Period = true; Hours > 0 | Same as R1 | Accounting |
| R4 | Accounting – Pick a Period | Summary | Accounting Period = *ask the user*; Hours > 0 | Same as R1 | Power users only (not on the dashboard) |
| R5 | Accounting – Last Period by Legacy BU | Summary | Same as R1 | Rows: Legacy BU → Project Name | Temporary, until O1 is decided |
| R6 | Admin – Sync problems | Table on **Time Cards** | Day Records Out of Sync = true | Record ID#, Employee, Week Beginning, Total Hours, Day Records - Hours, Day Records - Count | Admin |
| R7 | **Date Drift or Key Mismatch** (report ID 6, built 2026-10-14) | Table | Date Drift = true OR Key Mismatch = true | As built: Day Key, Day Index, Related Time Card, TC - Week Beginning, Date Drift, Key Mismatch; sort Day Key desc. **Signed off 2026-10-14** | Admin |
| R8 | **Orphaned Records** (report ID 5, built 2026-10-14) | Table | Orphan = true | As built: Day Key, Day Index, Work Date, Hours, Employee, Orphan; sort Day Key desc. Suggested: add Related Time Card, which keeps the deleted card's ID | Admin. Should be empty the morning after Pipeline B runs. Pipeline B can also use it as its query |

R1–R3 can also be shown as Hyderabad-only variants by adding `Hyderabad Project is not blank`, which matches report 207's scope (O5).

---

## 11. Build order

Steps 1–7 were done on 2026-10-14 by `scripts/build_time_card_days.py`. Step 8 (roles) was done by hand on 2026-10-14. Step 9 onward is still to do.

1. Create the table **Time Card Days**.
2. Add **Day Key** (Numeric, 0 decimals, no thousands separator). Set it **Unique** and **Required**, then make it the **key field** [before 3a].
3. Add the A and S fields from [5.1](#51-time-card-days-new).
4. Create relationship **3a** [after step 2]. There is no cascade-delete setting; see steps 9–10.
5. Add lookups **4a**, **4b**, **4c**.
6. Add the formula fields from [5.1](#51-time-card-days-new): Accounting Period, Period Start, Period End, In Current Period, In Last Period, BU (report), Date Drift, Key Mismatch, Provisional, Orphan [after 4a, 4b, 4c].
7. On Time Cards, add summaries **5a**, **5b**, then **Day Records Out of Sync** [after 5a, 5b].
8. Set roles ([13](#13-roles--permissions)): every non-admin role gets **None** and **Hide** on Time Card Days. By hand, because the API can't do it.
9. Build **Pipeline A** ([15](#15-pipelines)) and test it on one card ([14](#14-validation-checklist), checks V1–V4). Export its YAML into `YAML/`.
10. Add the day-record delete step to the **Delete Record Pipeline**, and build **Pipeline B** ([15](#15-pipelines)). Test with V4 and V13. Then turn Pipelines A and B **on**.
11. Run the **backfill** ([16](#16-one-time-backfill)). Order relative to step 10 doesn't matter, because writes are upserts on Day Key. Doing step 10 first means no edits are missed in between.
12. Build reports R1–R7.
13. Run the validation checklist ([14](#14-validation-checklist)).

---

## 12. Open items, deferred work, and declined options

| ID | Status | Item |
|---|---|---|
| O1 | **Open** | **Which BU does accounting mean?** Report 207 points to the new BU (Task → Business Unit). That only appears from about 2026-08-09 and is sparse before the week of 2026-10-04. Both are snapshotted, so the answer changes only which reports are kept (R1 vs R5). It doesn't change the table. If the answer is "new BU", ask accounting how to treat `(no BU)` hours in the 2026-09 period. **Measured 2026-10-14** (cards with Week Ending ≥ 2026-08-26: 25,788 hours). **The new BU (309) is blank on 21,021 hours (82%).** It's filled in only for Hyderabad and Howden India cards; every other type, Administrative and Project Task included, has none. **Project Name (300) is blank on 5,206 hours**, almost all NPD Project (4,186 h) and Product (897 h), because those cards have no Task. **Legacy BU (128) is blank on 3,667 hours**, mostly Product Task (2,868 h) and Product (799 h). Neither BU field covers everything as things stand. Accounting needs to say which it wants, and whether NPD and Product hours need a project from somewhere other than Task, such as Related NPD Project (266) or Related Product (18). That second question would add snapshot fields, so it needs an answer before the backfill. See the "What makes a Time Card" section in `app-map.md`. |
| O2 | **Open** | Confirm with accounting that the period is named by the month it ends in (`2026-09` = Aug 26 – Sep 25). Changing the name later is a formula edit and needs no data rework. |
| O3 | **Open** | The Time Cards fields Department / Location / Discipline / Project / Business Unit (at entry), fids 286–290, have **never held a value** (audit, 2026-10-14). That effort is dead, and this design keeps its own snapshot on Time Card Days. **Each field is still referenced by one Pipeline and one form.** Find that Pipeline before deleting them. See [17](#17-time-cards-field-audit-and-cleanup), group C. |
| O4 | **Closed** 2026-10-14 | **Delete Record (TC fid 268).** This is part of the delete trigger (confirmed 2026-10-14): checking it starts the Delete Record Pipeline, which hard-deletes the card. A step added to that Pipeline removes the card's day records first (critical note #7), so Time Card Days doesn't need to snapshot or filter on it. **Keep the field.** |
| O5 | **Open** | Should accounting reports be all BUs, or Hyderabad-only like report 207? |
| O6 | **Open** | Pipelines usage: Pipeline A fires on every hours edit, about 760 cards per week × several edits. Check the account's Pipelines step/run allowance. |
| O7 | **Deferred** | **Accounting access.** There is no Accounting role. Until it's decided, only admins can see Time Card Days and run R1–R5. Options: a new Accounting role with View (recommended), View for an existing role, or admins export the reports. Decide before step 12 (reports) goes to accounting. |
| D1 | Deferred | **Automate the period-close refresh.** Now: run the script manually on the date in [9.3](#93-when-a-period-is-final). Later: a scheduled Pipeline that rewrites cards where `Week Ending ≥ Period Start` of the just-finalized period. It needs a loop over about 3k cards, so check O6 first. |
| D2 | Deferred | **Extend the backfill to earlier history.** Run the script with an earlier `--since` and update the cutoff date in "Day Records Out of Sync". ⚠ **Unrecoverable if postponed:** a snapshot captures BU and project *as they are when written*. Backfilling old periods later will record today's Task → BU/project assignments, not the ones in force at the time. If old periods will ever matter, back them up sooner rather than later. |
| D4 | Deferred 2026-10-15 | **Pipeline A doesn't watch Related Task (57) or Related Employee (15).** Assumed for now that they don't change after a card is entered. If one does change, the day records keep the old BU, project and employee until a watched field (Date or a day) is edited, or the period-close refresh runs. To cover it later, add both fields to the trigger. |
| D3 | **Done** 2026-10-14 | **Key Mismatch (fid 35) missed records with a blank Day Index.** Kris changed the formula to also flag a blank or out-of-range Day Index (see 5.1). Test record 1, which had a blank Day Index, now appears on R7. |
| X1 | **Declined** | *Formula-only split on Time Cards* (e.g. "Hours in start period" and "Hours in end period" fields). A report can't merge two hour columns into one group per period. |
| X2 | **Declined** | *Formula-query totals on an Accounting Periods table.* This gives totals only, and a BU × project split would need a record per combination. |
| X3 | **Declined** | *Live lookups for BU and project.* Re-running a closed period would change when a task is reassigned. The user requires reproducible numbers. |
| X4 | **Declined** | *Skip zero-hour days.* This would need delete logic for days cleared during an edit. Seven rows per card is simpler and self-correcting. |
| X5 | **Declined** | *Use the Month field (TC fid 77).* It's the calendar month of Week Beginning, not of each day. |

---

## 13. Roles & permissions

**Decision (2026-10-14):** Time Card Days is **admin-only for now**. **Set on 2026-10-14.** Accounting access is deferred (O7). Role permissions can't be set through the API; they're set by hand under Settings → Roles → *role*.

| Role | Permissions tab: Time Card Days | User Interface tab | Notes |
|---|---|---|---|
| Administrator (12) | Full | Shown | Pipelines A and B, the delete Pipeline and the scripts run as an admin user |
| All 18 other roles: Purchasing (33), Hyderabad Projects Creator (59), Engineering (38), Project Coordinator (50), Project Manager (32), Project Manager Sri City (56), DataBase Coordinator (26), Field Service (41), Design Lead (44), Manufacturing Engineering (46), Master Scheduler (47), Executive (48), Participant with Resource Rights (49), Persons In Responsible Charge NP (51), Howden India Creator (58), Howden India Participant (57), Participant (11), Viewer (10) | **None** | **Hide** ticked | Hide only removes the table from the table bar. **None** is what blocks access. Don't use the table's own "Show in the table bar" setting, which hides it from admins too |

Roles as of 2026-10-14, from `API_GetRoleInfo`. A role added later needs the same two settings.

---

## 14. Validation checklist

| # | Check | Expected |
|---|---|---|
| V1 | Create a test time card for the week of 2026-09-20 with Mon 8 and Sat 2 | 7 day records. Mon 8.0 in `2026-09`, Sat 2.0 in `2026-10`, the rest 0.0 |
| V2 | Edit that card and clear Monday | Same 7 records (Record ID#s unchanged). Mon is now 0.0. Still 7, no duplicates |
| V3 | Change the card's Date to a day in the following week | Same 7 records. Work Dates shift +7. R7 (Date Drift) is empty |
| V4 | Delete the test card by checking Delete Record (fid 268) | The card and its 7 day records are gone. R8 is empty |
| V5 | Re-run the backfill for the same range | Day record count unchanged. Snapshot Written timestamps update |
| V6 | After the backfill: R6 and R7 | Both empty |
| V7 | Pick 3 cards across a period boundary and calculate their period hours by hand from the day columns | Matches R4 for those cards |
| V8 | Sum of Hours on Time Card Days with `Work Date` from 2026-08-30 to 2026-09-26 (whole weeks) | Equals Total Hours on Time Cards with Week Beginning from 2026-08-30 to 2026-09-20 |
| V9 | **Reproducibility:** export R4 for `2026-09`. Change the BU on one of those cards' Tasks (test task or revert afterward). Re-run R4 | **Identical numbers** |
| V10 | Edit an unrelated field on a card (e.g. Notes) | Pipeline A does not run (check the activity log) |
| V11 | On a test card, save Mon = 4, then immediately Mon = 6 (two saves within a few seconds, e.g. grid edit) | Two runs in the activity log. Mon day record = 6.0. Card not on R6 |
| V13 | Delete a test card directly (not through Delete Record), then run Pipeline B | Before the run: its 7 records are on R8 and missing from R1–R4. Related Time Card (22) still shows the deleted card's ID (confirmed by Kris 2026-10-14), so orphans can be traced back to their card. Only the lookup TC - Record ID# (23) goes to 0, which is why Orphan tests fid 23. After the run: they're gone |
| V12 | Save a test card, then delete it straight away, before the run finishes | Run ends at step c. A Time Card Days search for Day Key between `rid × 10` and `rid × 10 + 6` returns nothing |

---

## 15. Pipelines

Three Pipelines write to or delete from Time Card Days (`bwe8cjimn`). All three run as an **admin user** (section 13), so they need no role changes. Export each one's YAML into this folder after building it: `YAML/pipeline-<name>.yaml`.

| Pipeline | Trigger | What it does | Status |
|---|---|---|---|
| **B. Orphan sweep** (new) | Nightly schedule | Deletes day records whose card no longer exists | **Built and tested 2026-10-14** (V13). Export YAML to `YAML/` |
| **Delete Record** (existing) | Delete Record (TC fid 268) checked | **New step:** deletes the card's day records before deleting the card | **Step added and tested 2026-10-14** (V4, using a test card with hand-made day records). Export YAML to `YAML/` |
| **A. Sync on change** (new) | Time Card created or updated | Writes the card's 7 day records | **Upsert version live and tested 2026-10-15** (V1, V2, V3, V10, V11 on test card 555173). Created-only version ran 16:04–17:22 UTC that day. Rebuild steps: [PipelineA_Upsert_Build.md](PipelineA_Upsert_Build.md). Export YAML to `YAML/` after changes |

Build them in that order (B, Delete Record, A). B and the delete step only remove records, so they're safe to switch on first. A is switched on last, after its tests pass.

**Field IDs used below.** Time Card Days: 6 Day Key, 7 Day Index, 8 Work Date, 9 Hours, 10 Employee, 11 BU Code, 12 BU Name, 13 BU Full Name, 14 Legacy BU, 15 Project Name, 16 Project Type, 17 Time Card Title, 18 Time Card Type, 19 Hyderabad Project, 20 Billable?, 21 Snapshot Written, 22 Related Time Card, 37 Orphan. Time Cards: see the row mapping.

**Pipelines naming.** In Jinja, Pipelines refers to fields by slugs generated from their labels (for example `{{ b.sunday_day }}` for "Sunday - Day"). The slugs below are best guesses. **Pick each field from the field picker** instead of typing it, and check the result matches the intended fid.

### Pipeline B — "Time Card Days: orphan sweep"

| Step | Type | Configuration |
|---|---|---|
| **a. Trigger** | Schedule | Daily at 02:00 (outside working hours) |
| **b. Find orphans** | Quickbase → Search Records, table Time Card Days | Query: **Orphan (37) is true** |
| **c. For each** | Loop over b | |
| **c1. Delete** | Quickbase → Delete Record, table Time Card Days | Record ID = `{{ c.id }}` (the looped record) |

If your Pipelines has a query-based **Delete Records** step, it can replace b–c1 with one step: table Time Card Days, query Orphan (37) is true.

It's normally a no-op, because Search Records finds nothing. **Test (V13):** turn it on, delete a test card directly (not through Delete Record), check that its 7 records appear on R8, then run B by hand and check that they're gone.

### Delete Record Pipeline — add one step *(existing Pipeline)*

The Delete Record Pipeline is the only thing that deletes the card. There is no separate webhook (confirmed 2026-10-14. The usage API counts the Pipeline's own trigger as a webhook; see section 17, step 2 of the cleanup checklist). Add the new steps **before** its existing delete step.

| Step | Type | Configuration |
|---|---|---|
| **New: find day records** | Quickbase → Search Records, table Time Card Days | Query: **Related Time Card (22) equals** `{{ <trigger>.id }}`, the card's Record ID# |
| **New: for each → delete** | Loop → Quickbase → Delete Record, table Time Card Days | Record ID = the looped record's ID |
| *(existing)* delete the card | | Unchanged, now **after** the new steps |

A card outside the backfill window has no day records, so the search finds nothing and the loop does nothing. That's expected.

**Test (V4):** on a test card that has day records, check Delete Record. The card and all 7 day records should be gone, and R8 should stay empty.

### Pipeline A — "Time Card Days: sync on change"

| Step | Type | Configuration |
|---|---|---|
| **a. Trigger** | Quickbase → Record event, table Time Cards. Events: **created** and **updated** | **Only when these fields change** (no-op guard): Date (9), Sunday (23), Monday (10), Tuesday (11), Wednesday (12), Thursday (13), Friday (14), Saturday (24), Related Task (57), Related Employee (15). Don't watch formula or lookup fields; a change filter never fires on them (critical note #1) |
| **b. Re-read card** (stale-data guard) | Quickbase → Look Up a Record, table Time Cards | Record ID# = `{{ a.id }}`. If not found: **continue, don't fail**. Every later step reads from **b**, never **a** (critical note #9) |
| **c. Condition** (deleted-card and boundary guard) | If / condition | **b found a record** AND **b Week Ending (7) ≥ 2026-08-26**. If not, the run ends with no changes: the card was deleted mid-run, or it's older than the backfill window. Update the date together with D2 and Day Records Out of Sync (TC 328) |
| **d. Prepare** (inside the "yes" branch) | Quickbase → Prepare Bulk Record Upsert | Table: Time Card Days. **Merge field: Day Key (6)**. Fields: 6–22 as in the mapping |
| **e.–k. Add rows ×7** | Quickbase → Add a Bulk Upsert Row | One per Day Index 0 (Sun) to 6 (Sat). Mapping below |
| **l. Commit** | Quickbase → Commit Upsert | |

**Row mapping.** The fixed fields are the same on all 7 rows:

| Time Card Days field (fid) | Value | Source on Time Cards |
|---|---|---|
| Related Time Card (22) | `{{ b.id }}` | Record ID# (3) |
| Employee (10) | `{{ b.employee }}` | Employee (17), a user field. If the step wants an email or user ID, use Related Employee (15) |
| BU Code (11) | `{{ b.business_unit_code }}` | 296 |
| BU Name (12) | `{{ b.business_unit_name }}` | 297 |
| BU Full Name (13) | `{{ b.business_unit_full_name }}` | 309 |
| Legacy BU (14) | `{{ b.legacy_business_unit }}` | 128 |
| Project Name (15) | `{{ b.project_name }}` | 300 |
| Project Type (16) | `{{ b.project_type }}` | 298 |
| Time Card Title (17) | `{{ b.time_card_title }}` | 137 |
| Time Card Type (18) | `{{ b.time_card_type }}` | 151 |
| Hyderabad Project (19) | `{{ b.hyderabad_project_project_identifier }}` | 273 |
| Billable? (20) | `{{ b.billable }}` | 299 |
| Snapshot Written (21) | `{{ time.now }}` | Run time |

The day-specific fields differ on each row:

| Row | Day Key (6) | Day Index (7) | Work Date (8), from Time Cards | Hours (9), from Time Cards |
|---|---|---|---|---|
| e | `{{ (b.id \| int) * 10 + 0 }}` | 0 | `{{ b.sunday_day }}` (315) | `{{ b.sunday or 0 }}` (23) |
| f | `{{ (b.id \| int) * 10 + 1 }}` | 1 | `{{ b.monday_day }}` (316) | `{{ b.monday or 0 }}` (10) |
| g | `{{ (b.id \| int) * 10 + 2 }}` | 2 | `{{ b.tuesday_day }}` (317) | `{{ b.tuesday or 0 }}` (11) |
| h | `{{ (b.id \| int) * 10 + 3 }}` | 3 | `{{ b.wednesday_day }}` (318) | `{{ b.wednesday or 0 }}` (12) |
| i | `{{ (b.id \| int) * 10 + 4 }}` | 4 | `{{ b.thursday_day }}` (319) | `{{ b.thursday or 0 }}` (13) |
| j | `{{ (b.id \| int) * 10 + 5 }}` | 5 | `{{ b.friday_day }}` (320) | `{{ b.friday or 0 }}` (14) |
| k | `{{ (b.id \| int) * 10 + 6 }}` | 6 | `{{ b.saturday_day }}` (321) | `{{ b.saturday or 0 }}` (24) |

Day Key **must** be computed as a number, as shown. Never build it by joining text (critical note #4). The `or 0` on Hours is required: blank day fields arrive as empty strings (critical note #3).

**Invalid-input guard:** none needed beyond step c. Every input either maps one-to-one or defaults to 0. A card with no Task writes blank BU and project, which reports show as "(no BU)" instead of guessing.

**Testing Pipeline A** (build sheet section 14). Leave A **off** while building, and run it by hand against one test card. Use a test task, and a week whose Week Ending is on or after 2026-08-26:

| Check | Do | Expect |
|---|---|---|
| V1 | Create a test card for the week of 2026-09-20 with Mon 8 and Sat 2 | 7 day records. Mon 8.0 in `2026-09`, Sat 2.0 in `2026-10`, the rest 0.0. Day Keys = card ID × 10 + 0…6. Key Mismatch false |
| V2 | Clear Monday | Same 7 records (Record ID#s unchanged), Mon now 0.0 |
| V3 | Move the card's Date to the next week | Same 7 records, Work Dates +7, Date Drift false on all |
| V10 | Edit only Notes | A doesn't run (activity log) |
| V11 | Save Mon = 4 then Mon = 6 within seconds | Two runs. Mon = 6.0. Card not on R6 |
| V12 | Save, then delete immediately | Run ends at step c. No records with Day Key between ID × 10 and ID × 10 + 6 |
| V4 | Delete the test card through Delete Record | Card and its 7 records gone (also tests the delete step) |

**Results, 2026-10-15** (test card 555173, checked through the API):

- **V1, V2, V3, V10, V11 passed.** Same Record ID#s (176–182) through every edit, no duplicate Day Keys, blank days written as 0.0, Snapshot Written set on each run, Date Drift and Key Mismatch false, card never on R6. V11's two runs weren't checked in the activity log; the final value (Mon = 6.0) was correct.
- **V12 and V4 not re-run.** Deletes are handled by the Delete Record Pipeline (V4 passed 2026-10-14). A late run that recreates records for a deleted card is caught by Orphan and swept by Pipeline B (V13).
- **Live use:** a bulk save of 5 existing cards (Ryan Schuldt, 17:45 UTC) got correct day records, so bulk saves trigger A.
- **Not yet covered by A:** cards created before 16:04 UTC or edited before 17:22 UTC on 2026-10-15, plus 555170 and 555171 (created 16:19 UTC, likely while A was switched off). The backfill picks these up.
- **Deliberately not written yet:** Hyderabad Project (19) and Legacy BU (14). Related Task and Related Employee aren't watched (D4).

Then switch A on (build step 10). Check the Pipelines usage allowance first (O6): A runs about 760 cards a week × several edits, at about 12 steps per run.

**After all three are on:** run the backfill (section 16), then check R6, R7 and R8 are empty.

---


## 16. One-time backfill

**Done 2026-10-15, through Pipeline A instead of a script.** Kris added a checkbox, **Refresh Day Records** (TC fid 329), to Pipeline A's trigger fields, then changed it on the cards in batches. Each change starts one normal Pipeline A run. Nothing else writes day records, so the backfill follows the exact logic tested in V1–V11. The script below was never written. Keep its description as the fallback. **To refresh any set of cards later**, for example at period close (D1) or after a Task's BU is fixed: filter a report to those cards and use Change values on Refresh Day Records. Checking and unchecking both trigger, so it never needs resetting. Work in batches of about a week (~760 cards) because of the usage allowance (O6).

**Result, checked through the API on 2026-10-15:**

| Check | Result |
|---|---|
| Time Cards with Week Beginning ≥ 2026-08-23 | 4,988 |
| Time Card Days records | 34,916 = 7 × 4,988 |
| Cards with no records or not exactly 7 | 0 |
| Duplicate Day Keys, orphans, records outside the window | 0 |
| Hours, Work Date, Day Key, employee, BU, project, title, Billable? vs the card | All match (26,619.45 hours) |
| R6 (Out of Sync), R7 (Date Drift or Key Mismatch), R8 (Orphans) | All empty (V6) |

Found on the way:
- The first pass missed 83 cards, all created on 2026-09-27 or 2026-10-04 (59 of them locked). A second pass picked them up.
- Card 549541 was on R6 with correct records. Its summed hours were 40.839999… against 40.84, so Day Records Out of Sync (TC 328) now rounds both sides (see 5.2).
- Card 436359 had the Date `0251-05-11`, a typo for 2025, and showed on R6. It's no longer in the window.

**Tool:** `scripts/backfill_time_card_days.py`, to be written after the table exists. It follows the same pattern as the deploy script: `op run --env-file=.qb.env --`, dry run by default, `--apply` to write.

- **Scope:** Time Cards with `Week Ending ≥ 2026-08-26` (`--since`), or every card overlapping one accounting period (`--period 2026-09`, used for the period-close refresh in [9.3](#93-when-a-period-is-final)).
- **Method:** query Time Cards for the same fields Pipeline A reads. Build 7 rows per card, with Day Key computed as an integer (`rid * 10 + day_index`), never via string formatting. Call `POST /v1/records` with `mergeFieldId = Day Key`, in batches of about 500 rows. It writes exactly what Pipeline A writes, so the two are interchangeable.
- **Volume:** about 3k cards, so about 21k rows, or about 45 API calls.
- **Dry run output:** card count, row count, total hours by Accounting Period. Compare these against Time Cards before using `--apply`.
- **Pipeline A** can stay on. Writes to Time Card Days don't trigger it.

---

## 17. Time Cards field audit and cleanup

**Audit date:** 2026-10-14. The audit was read-only, through the API. Time Cards has 154 fields. 18,385 cards were created between 2026-01-01 and the audit date.

**Method.** For each field, count the cards created since 2026-01-01 that have a value. For checkboxes, a value means checked. Fields with no values, or with values on under 1% of those cards, were then checked two more ways:
- the number of cards with a value at any time, and the most recent card created with one;
- what references the field, from `GET /v1/fields/usage/{fid}`. That shows counts of forms, reports, personal reports, fields, relationships, Pipelines and webhooks, but not their names.

**Cleanup status: in progress.** Deleted so far: 25–28, 80, 81, 117, 156, 157, 160, 191, 192 and 203 (2026-10-14; Time Cards now has 141 fields). Everything else is still only proposed. This is the production app, so each group is approved before anyone acts on it. Before deleting a field:
1. Remove it from its forms and reports, and repoint any formula that uses it.
2. Look up any Pipeline that uses it in the Pipelines UI, because the API reports only counts. **The API's "webhooks" count includes a Pipeline's own Quickbase trigger**, so a field watched by a Pipeline trigger shows 1 Pipeline and 1 webhook even when the table's Webhooks page is empty (fid 268, confirmed 2026-10-14).
3. Note the deletion in the Change Log table (`bv54hme8z`).

Deleting a **reference field** (a "Related …" field) deletes its relationship and every lookup that goes through it.

### A. Never used, references are only forms and reports. Proposed: delete

| fid | Field | Kind | Referenced by |
|---|---|---|---|
| ~~25~~ | ~~Related Task3~~ **Deleted 2026-10-14** | reference | 3 fields, 1 form, 1 report, 1 personal report |
| ~~26~~ | ~~Task Title~~ **Deleted 2026-10-14** | lookup (via 25) | 2 forms, 2 reports, 2 personal reports |
| ~~27~~ | ~~Task - Description~~ **Deleted 2026-10-14** | lookup (via 25) | 1 report, 1 personal report |
| ~~28~~ | ~~Task - Status~~ **Deleted 2026-10-14** | lookup (via 25) | 1 report, 1 personal report |
| ~~81~~ | ~~User - ID Number~~ **Deleted 2026-10-14**, along with fid 80 User - Cost Center (most likely a lookup. Over 1% of 2026 cards had a value in it, so it wasn't in the audit list) | lookup | 1 form, 2 personal reports |
| ~~117~~ | ~~User - Department Head2~~ **Deleted 2026-10-14** | lookup | 3 forms, 6 personal reports |
| ~~160~~ | ~~Relationship~~ **Deleted 2026-10-14** | formula | 2 forms, 1 report, 1 personal report |
| ~~191~~ | ~~Task - Related Project2 - Product Name~~ **Deleted 2026-10-14** | lookup | 1 field |
| ~~192~~ | ~~UserEmail~~ **Deleted 2026-10-14** | lookup | none besides its relationship |
| ~~203~~ | ~~Task - Kaizen Title~~ **Deleted 2026-10-14**. Its source, Tasks 133 Kaizen Title, comes through Tasks 132 Related Kaizen, a cross-app link to `bm2z7dk2m` that no task has ever used | lookup | 1 field |
| 274 | Related Department | reference | 2 fields (its lookups) |
| 275 | Department | lookup (via 274) | none besides its relationship |
| 283 | Related User - Project Activity | reference | 5 fields, 1 form |
| 284 | Related User - Project Activity - User Name | lookup (via 283) | 1 form |
| 285 | Related User - Project Activity - Home Department - Manager - User Name | lookup (via 283) | 1 form |
| 291 | Related User - Project Activity - User Location | lookup (via 283) | none besides its relationship |
| 310 | Employees Current Department (formula) | formula | nothing |
| 311 | Employees Current Location (formula) | formula | nothing |
| 312 | Employees Current Discipline (formula) | formula | nothing |

Fields 310–312 reference nothing and have nothing referencing them, so they are the safest place to start.

### B. Never used, but a Pipeline references it. Proposed: find the Pipeline first

| fid | Field | Referenced by |
|---|---|---|
| ~~156~~ | ~~Related Continuous Improvement Project~~ **Deleted 2026-10-14**. Watch the Pipeline that referenced it for failures | 2 fields, 2 forms, 1 personal report, **1 Pipeline** |
| ~~157~~ | ~~Related Continuous Improvement Project - Project Name~~ **Deleted 2026-10-14** | 1 field, 2 reports |

### C. Never used, part of an unfinished or unclear feature. Proposed: decide, then delete or keep

| fid | Field | Referenced by | Question |
|---|---|---|---|
| 268 | Delete Record | **1 Pipeline** (the usage API also counts 1 webhook; see note) | **Keep** (decided 2026-10-14). Part of the delete trigger. Checking it starts the hard delete (O4) |
| 286–290 | Department / Location / Discipline / Project / Business Unit (at entry) | 1 form and **1 Pipeline** each | Which Pipeline was meant to fill these? It has never written a value. Turn it off, then delete (O3) |
| 306 | Unlock Timecard | 1 field (probably the lock formula, fid 307), 1 form, 1 report | **Keep** (decided 2026-10-14). It's in use: it's the way to reopen a locked card ([4](#4-critical-implementation-notes) #5) |

### D. Used in the past, not used in 2026. Proposed: remove from forms, keep the fields

| fid | Field | Kind | Cards ever | Last card with a value | Referenced by |
|---|---|---|---|---|---|
| 20 | Product - Description | lookup | 41 | 2025-05-21 | 4 reports, 5 personal reports |
| 186 | Service Ticket - Product Name | lookup | 267 | 2025-10-28 | 1 field |
| 249 | Related Vaporizer WorkSheet | reference | 45 | 2023-06-08 | 3 fields, 1 form, 1 Pipeline |
| 250 | Vaporizer Sales Order | lookup (via 249) | 43 | 2023-06-08 | 1 form, 1 report |

Deleting 249 would lose which cards were linked to which worksheet. The lookups 20 and 186 hold no data of their own and could be deleted, but they are cheap to keep.

### E. Rarely used in 2026 (under 1%) but still active. Proposed: keep, and ask the owners

| Group | Reference fid | 2026 cards | Cards ever | Last card | Lookups on it |
|---|---|---|---|---|---|
| Engineering Service Request | 142 | 107 | 1,034 | 2026-10-11 | 144, 145, 162, 199 |
| ECR/TDD | 118 | 17 | 5,119 | 2026-09-10 | 119, 121, 122, 150, 262 (and 72 Task - ECR Number: 2 / 7, last 2026-02-08) |
| Service Ticket | 184 | 12 | 434 | 2026-08-16 | 188, 189 |
| VIP Order Worksheet | 247 | 3 | 106 | 2026-07-22 | 248 |
| Document Inquiry | 163 | 2 | 3,465 | 2026-01-11 | 164, 165, 166 |
| Product (lookup only) | n/a | 78 | 1,224 | 2026-10-12 | 21 Product - Status |

Document Inquiry was heavily used before and has almost stopped (2 cards in 2026, the last on 2026-01-11). Ask whether that process moved somewhere else.

---

## Appendix — conventions

- Phase IDs: relationships 3x, lookups 4x, summaries 5x. Never renumber them.
- "TC fid N" means field N on Time Cards (`bhm9822gc`).
- Field IDs for the new table are assigned when it's built. Record them here in v2.
