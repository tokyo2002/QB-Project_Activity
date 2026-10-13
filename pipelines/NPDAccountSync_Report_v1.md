# NPD Account Sync — one remote API call per unique AFE / subledger number

Build sheet, **v1** · 2026-10-12 · App: Project Activity (`bg86uwfcw`) · Production

**Status: Implemented** (user confirmed 2026-10-12). Verified first run at 2026-10-13 00:38 UTC: all 9 First Use AFE/Subledger records synced with no errors; the duplicates (records 39, 42, 43) were left blank. Export the Pipeline YAML into this folder as `npd-account-sync.yaml`.

## 0. Changelog

| Version | Date | Change |
|---|---|---|
| v1 | 2026-10-12 | First design. Mark the first use of each number with a checkbox, search on it, loop over the results, call the API once per number, write the result back. |

## 1. Design model (read first)

**Goal.** Run on a schedule. For every NPD project, call a remote API once for each **unique** AFE or subledger account number on that project, and write the response back to Quickbase.

**Source.** NPD Investments (`bv6kbiwnp`). Each record has:
- **Account type** (fid 9): Subledger, AFE, Work Order or Other.
- **Account Number** (fid 10, text).
- **Related NPD Project** (fid 11), pointing to NPD Project Tracking `bvaesxd8r`.

A project can have the same number on several records. Project 66 has TG0083 three times. Blank numbers exist too: 3 of the 16 AFE and Subledger records today.

**Approach.** Do the duplicate check in Quickbase, not in Jinja:

1. A checkbox formula on NPD Investments, **First Use of Account Number**. It's true only on the earliest record (lowest Record ID#) for each *project + type + number*. Blank numbers are always false.
2. The Pipeline searches for `First Use = true AND type is AFE or Subledger`. That returns **exactly one record per unique value per project**.
3. A For each loop calls the API once per record and writes the response to **that record**.

**Why not do it in Jinja?** Pipelines' For each steps only loop over records returned by a search. Looping over a list built in Jinja needs the JSON Handler channel as a workaround, which is fragile. With a checkbox doing the duplicate check, the Pipeline itself is simple, has no cap on how many values it handles, and a report on the checkbox shows exactly which values it will call.

### 1.1 Terms that look alike

| Term | Meaning |
|---|---|
| Account type (fid 9) | The category: AFE / Subledger / Work Order / Other. The user called this "count type" |
| AFE Numbers (fid 176), Generic Subledger Numbers (fid 177) | Display formulas on NPD Project Tracking: a comma list per project. **Not used by this Pipeline** |
| First Use of Account Number | New. Marks which single record represents a project + type + number |

## 4. Critical implementation notes

1. **Write the response only to the First Use record, never to its duplicates.** If the same spend figure lands on all three TG0083 records, any summary field that rolls up to the project (e.g. *Total CAPEX/AFE Spend*, fid 175) counts it three times.
2. **Which record is First Use can change.** If the earliest record is deleted or its number edited, a different record becomes First Use on the next evaluation. On the next scheduled run it gets the response, but the old record keeps its stale value. Clear the response fields where `First Use = false` (Pipeline step **f**).
3. **Apostrophes break the duplicate check.** An account number containing `'` breaks that record's query (none do today). If that ever matters, escape them in the formula.
4. **The duplicate check matches exact text.** "200913.602600  Subledger RD0033" and "200913.602600 Sub Ledger RD0033" (project 133) are two values, so they make two API calls. That's a data cleanup job, not something for the formula.
5. **Blank numbers are skipped**, so no API call is made with an empty account number.

## 5. Table specifications

### 5.1 NPD Investments *(existing; add fields)*

| Field | Type | Tag | Value / formula |
|---|---|---|---|
| **First Use of Account Number** (**fid 13**) | Formula – Checkbox | Derived | **Implemented 2026-10-12.** Formula below. Checks 11 of 16 AFE and Subledger records (6 AFE, 5 Subledger); a search on `{13.EX.true}` returns those 11 |
| *API response field(s)* | *TBD* | Written by the Pipeline | **O1**: what the API returns and where to store it |
| API Last Synced (**fid 16**) | Date/Time | Written by the Pipeline | **Implemented 2026-10-12.** `{{ time.now }}`, set only on success. Shows when each value was last refreshed |
| API Sync Error (**fid 14**) | Text | Written by the Pipeline | **Implemented 2026-10-12.** Blank on success; otherwise the HTTP status and message |
| Account Number Valid (**fid 17**) | Formula – Checkbox | Derived | **Implemented 2026-10-12.** `RegexMatch(Trim([Account Number]), "^([A-Z]{2}[0-9]{4}|[0-9]{8})$")`: two capital letters + four digits, or exactly eight digits. Case-sensitive; blank is not valid. On 2026-10-12, 3 numbered records fail: 4 (test value), 27 `280021` and 28 `280678` (probably missing leading zeros) |

```
var text q = "{11.EX." & ToText([Related NPD Project]) & "}AND{9.EX.'" & [Account type] & "'}AND{10.EX.'" & [Account Number] & "'}AND{3.LT." & ToText([Record ID#]) & "}";
Trim([Account Number]) <> "" and Size(GetRecords($q)) = 0
```

## 10. Reports

| # | Name | Table | Filter | Purpose |
|---|---|---|---|---|
| R1 | Account Sync – Values to call (**report 6**, built; 11 rows on 2026-10-12: 6 AFE, 5 Subledger) | NPD Investments | First Use = true AND Account type is AFE or Subledger | Exactly what the Pipeline will loop over. Its row count is the number of API calls per run |
| R2 | Account Sync – Errors (**report 7**, built) | NPD Investments | API Sync Error is not blank | Values whose last call failed |
| R3 | Account Sync – Data cleanup (**report 8**, built) | NPD Investments | Account type is AFE or Subledger AND Account Number is blank | Investments that will never be called |

## 11. Build order

1. ~~Add **First Use of Account Number** to NPD Investments.~~ Done: fid 13, 2026-10-12.
2. ~~Build report **R1** and confirm it lists one row per unique project + type + number.~~ Done: report 6, 11 rows (6 AFE, 5 Subledger), confirmed by the user 2026-10-12.
3. Add the response field(s) (O1). ~~**API Last Synced** and **API Sync Error**~~ done: fids 16 and 14, both with field comments.
4. Build the Pipeline ([15](#15-pipeline)). First run it manually with step **b** limited to a single project.
5. Turn on the schedule.
6. ~~Build reports R2 and R3.~~ Done: reports 7 and 8.

## 12. Open items and declined options

| ID | Status | Item |
|---|---|---|
| O1 | **Open** | API details: base URL, authentication, request shape (the type is a parameter), response fields, and which Quickbase fields receive them |
| O2 | **Open** | Schedule: time of day and frequency (nightly?). Also check the API's rate limit against the R1 row count |
| O4 | **Open** | Should step **b** also require `{17.EX.true}`, so invalid numbers are never sent to the API? And should report 8 (Data cleanup) widen to `Account Number blank OR Account Number Valid = false`? |
| O3 | **Open** | Should NPD projects that are closed or cancelled be skipped? If so, add a project-status lookup and filter on it in step **b** |
| X1 | Declined | *Remove duplicates in Jinja and loop with JSON Handler.* Fragile, and harder to see what will run |
| X2 | Declined | *Combined Text summary.* It removes duplicates, but caps at somewhere around 25–150 values and can't drive a loop |
| X3 | Declined | *Use fields 176/177 as the source.* Splitting a comma list back into values just to loop over it would be a step backward |

## 14. Validation checklist

| # | Check | Expected |
|---|---|---|
| V1 | R1 row count vs a manual count of unique project + type + number (blanks excluded) | Equal |
| V2 | Project 66 | One TG0083 call; the response lands only on its First Use record |
| V3 | Delete the First Use TG0083 record (in a test copy), then re-run | A different TG0083 record becomes First Use and gets the response. The old value isn't left on a non-First Use record |
| V4 | Make the API fail (e.g. a bad token) | API Sync Error is filled in; the Pipeline continues with the next value |
| V5 | Run twice in a row | The same number of calls each time; responses are overwritten, nothing is duplicated |

## 15. Pipeline

**"NPD Account Sync"**. Store the exported YAML here as `pipelines/npd-account-sync.yaml`.

| Step | Type | Configuration |
|---|---|---|
| **a. Trigger** | Schedule | Nightly (O2) |
| **b. Search** | Quickbase → Search Records, NPD Investments | **Built 2026-10-12; returns 11 records (matches report 6).** Advanced query: `{13.EX.true}AND({9.EX.'AFE'}OR{9.EX.'Subledger'})` |
| **c. Loop** | For each record in b | |
| **c1. Call API** | Webhooks / HTTP → Make Request | URL and body built with Jinja from the loop record, e.g. `account={{ b.account_number | trim | urlencode }}&type={{ b.account_type | lower }}`. Auth header from O1 |
| **c2. Branch** | Condition | Response status is 2xx? |
| **c3. Success** | Quickbase → Update Record, NPD Investments, Record ID# = `{{ b.id }}` | Response field(s) ← `{{ c1.json.<field> }}` (O1). API Last Synced ← `{{ time.now }}`. API Sync Error ← blank |
| **c4. Failure** | Quickbase → Update Record (same record) | API Sync Error ← `{{ c1.status_code }} {{ c1.text | truncate(200) }}` |
| **f. Clear stale values** | Quickbase → Search Records + For each → Update | `First Use = false` AND a response field is not blank → clear the response fields (note 4.2) |

Jinja field names (`b.account_number`, `c1.json…`) are the slugs Pipelines generates. Check them against the field picker when building.
