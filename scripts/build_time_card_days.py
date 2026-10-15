"""Build the Time Card Days table in the Project Activity Quickbase app.

Carries out build-order steps 1-7 of time-card-days/TimeCardDays_Report_v2.md:
the table, its fields, relationship 3a (Time Cards -> Time Card Days) with
lookups 4a/4b and summaries 5a/5b, the formula fields, and "Day Records Out
of Sync" on Time Cards. Creates things only; it never edits or deletes an
existing field, and it writes no records.

    # dry run (default): show what exists and what would be created; changes nothing
    op run --env-file=.qb.env -- python3 scripts/build_time_card_days.py

    # create whatever is missing
    op run --env-file=.qb.env -- python3 scripts/build_time_card_days.py --apply

Safe to re-run: the table is matched by name and fields by label, so a run that
stopped partway picks up where it left off. Every field ID is written to
time-card-days/time_card_days_fields.json for the build sheet and Pipeline A.

Not possible through the API. Do these by hand afterwards (the script lists them):
  - deleting day records with their card: Quickbase has no cascade delete, so this is
    Pipeline work (build sheet critical note #7 and section 15)
  - Day Key display: no thousands separator; optionally make it the key field
  - roles (build sheet section 13)
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "time-card-days" / "time_card_days_fields.json"

TIME_CARDS = "bhm9822gc"
TABLE = {
    "name": "Time Card Days",
    "description": "One record per time card per weekday, for accounting-period hours. "
                   "Written only by Pipeline A and scripts/backfill_time_card_days.py. "
                   "Design: time-card-days/TimeCardDays_Report_v2.md in the Project Activity repo.",
    "singleRecordName": "Time Card Day",
    "pluralRecordName": "Time Card Days",
}

# Step 3: authoritative (A) and snapshot (S) fields, build sheet 5.1.
DATA_FIELDS = [
    ("Day Key", "numeric", {"decimalPlaces": 0}),
    ("Day Index", "numeric", {"decimalPlaces": 0}),
    ("Work Date", "date", {}),
    ("Hours", "numeric", {"decimalPlaces": 2}),
    ("Employee", "user", {}),
    ("BU Code", "text", {}),
    ("BU Name", "text", {}),
    ("BU Full Name", "text", {}),
    ("Legacy BU", "text", {}),
    ("Project Name", "text", {}),
    ("Project Type", "text", {}),
    ("Time Card Title", "text", {}),
    ("Time Card Type", "text", {}),
    ("Hyderabad Project", "text", {}),
    ("Billable?", "checkbox", {}),
    ("Snapshot Written", "timestamp", {}),
]

# Steps 4-5 and 7: relationship 3a, lookups 4a/4b (Time Cards fid -> label), summaries 5a/5b.
REFERENCE_LABEL = "Related Time Card"
LOOKUPS = {3: "TC - Record ID#", 8: "TC - Week Beginning", 307: "TC - Timecard Locked"}
SUMMARY_HOURS = "Day Records - Hours"
SUMMARY_COUNT = "Day Records - Count"

# Accounting period of a date variable $d, named by the month it ends in (build sheet 9.1).
PERIOD_MONTH = "var date p = If(Day($d) >= 26, AdjustMonth(FirstDayOfMonth($d), 1), FirstDayOfMonth($d));\n"
PERIOD_NAME = 'ToText(Year($p)) & "-" & PadLeft(ToText(Month($p)), 2, "0")'

# Step 6: formula fields on Time Card Days, in dependency order.
FORMULA_FIELDS = [
    ("Accounting Period", "text", "var date d = [Work Date];\n" + PERIOD_MONTH + PERIOD_NAME),
    ("Period Start", "date", "var date d = [Work Date];\n" + PERIOD_MONTH + "AdjustMonth($p, -1) + Days(25)"),
    ("Period End", "date", "var date d = [Work Date];\n" + PERIOD_MONTH + "$p + Days(24)"),
    ("In Current Period", "checkbox",
     "var date d = Today();\n" + PERIOD_MONTH + "[Accounting Period] = " + PERIOD_NAME),
    ("In Last Period", "checkbox",
     # Formula variable names must be letters only: Quickbase rejects $t0 / $p0 as a syntax error.
     "var date t = Today();\n"
     "var date pc = If(Day($t) >= 26, AdjustMonth(FirstDayOfMonth($t), 1), FirstDayOfMonth($t));\n"
     "var date d = AdjustMonth($pc, -1);\n" + PERIOD_MONTH + "[Accounting Period] = " + PERIOD_NAME),
    ("BU (report)", "text", 'If(Trim([BU Full Name]) = "", "(no BU)", [BU Full Name])'),
    ("Date Drift", "checkbox",
     "IsNull([Work Date]) or [Work Date] <> [TC - Week Beginning] + Days([Day Index])"),
    ("Key Mismatch", "checkbox",
     "IsNull([Day Index]) or [Day Index] < 0 or [Day Index] > 6 "
     "or [Day Key] <> [Related Time Card] * 10 + [Day Index]"),
    ("Provisional", "checkbox", "not [TC - Timecard Locked]"),
    # Quickbase has no cascade delete: true means the card is gone and Pipeline B has yet to sweep this record.
    # Test the lookup for 0, not IsNull: a numeric lookup with no parent reads as 0 (blank counts as zero).
    ("Orphan", "checkbox", "[TC - Record ID#] = 0"),
]

# Step 7: on Time Cards, after the summaries exist.
OUT_OF_SYNC = (
    "Day Records Out of Sync", "checkbox",
    "[Week Ending] >= Date(2026,8,26) and "
    "([Day Records - Count] <> 7 or Round([Total Hours], 0.01) <> Round([Day Records - Hours], 0.01))",
)

MANUAL_STEPS = [
    "Relationship Time Cards -> Time Card Days: don't add 'Add Time Card Day' buttons or embedded add forms.",
    "Quickbase has no cascade delete (critical note #7): add the day-record delete step to the Delete Record "
    "(fid 268) Pipeline, and build Pipeline B, the nightly orphan sweep (build sheet 15).",
    "Day Key: in field properties, turn off the thousands separator. Optionally make it the table's key field.",
    "Roles (build sheet 13): Accounting view; no Add/Modify on Time Card Days for anyone but Admin.",
    "Copy the field IDs from time-card-days/time_card_days_fields.json into the build sheet.",
]


class QB:
    def __init__(self, apply):
        self.apply = apply
        self.headers = {
            "QB-Realm-Hostname": env("CHART_QUICKBASE_REALM_HOSTNAME"),
            "Authorization": "QB-USER-TOKEN " + env("CHART_QUICKBASE_USER_TOKEN"),
            "Content-Type": "application/json",
        }
        self.app_id = env("CHART_QUICKBASE_APP_DBID")

    def call(self, method, path, body=None):
        req = urllib.request.Request(
            "https://api.quickbase.com/v1/" + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=self.headers, method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            sys.exit(f"{method} {path} failed ({e.code}): {e.read().decode()[:500]}\n"
                     "Nothing after this step was done. Fix the cause and re-run; finished steps are skipped.")

    def fields(self, table_id):
        return {f["label"]: f for f in self.call("GET", f"fields?tableId={table_id}")}


def env(name):
    value = os.environ.get(name, "")
    if not value or value.startswith("op://"):
        sys.exit(f"{name} is not resolved — run this through `op run --env-file=.qb.env --`.")
    return value


def step(qb, what, exists, create):
    """Print one plan line; run create() only with --apply and only if missing."""
    if exists:
        print(f"  exists   {what}")
        return exists
    print(f"  {'create  ' if qb.apply else 'would add'} {what}")
    return create() if qb.apply else None


def main():
    apply = "--apply" in sys.argv[1:]
    qb = QB(apply)
    print(("APPLY" if apply else "DRY RUN") + f": Time Card Days in app {qb.app_id}\n")

    tc_fields = qb.fields(TIME_CARDS)
    missing = [fid for fid in (7, 8, 183, 307) if fid not in {f["id"] for f in tc_fields.values()}]
    if missing:
        sys.exit(f"Time Cards is missing source field(s) {missing}; the design needs them.")

    print("Step 1: table")
    tables = {t["name"]: t["id"] for t in qb.call("GET", f"tables?appId={qb.app_id}")}
    table_id = step(qb, f"table '{TABLE['name']}'", tables.get(TABLE["name"]),
                    lambda: qb.call("POST", f"tables?appId={qb.app_id}", TABLE)["id"])
    days = qb.fields(table_id) if table_id else {}

    print("Step 2-3: data and snapshot fields")
    for label, ftype, props in DATA_FIELDS:
        step(qb, f"{label} ({ftype})", days.get(label, {}).get("id"),
             lambda: qb.call("POST", f"fields?tableId={table_id}",
                             {"label": label, "fieldType": ftype, "properties": props})["id"])
    if apply:
        days = qb.fields(table_id)
    key = days.get("Day Key")
    step(qb, "Day Key set Unique + Required", key and key.get("unique") and key.get("required"),
         lambda: qb.call("POST", f"fields/{key['id']}?tableId={table_id}", {"unique": True, "required": True}))

    print("Step 4-5, 7a: relationship 3a with lookups 4a/4b and summaries 5a/5b")
    rels = qb.call("GET", f"tables/{table_id}/relationships")["relationships"] if table_id else []
    rel = next((r for r in rels if r["parentTableId"] == TIME_CARDS), None)
    step(qb, f"Time Cards -> Time Card Days, reference '{REFERENCE_LABEL}', "
             f"lookups {list(LOOKUPS)}, summaries '{SUMMARY_HOURS}' (sum of Hours), '{SUMMARY_COUNT}'",
         rel and rel["id"],
         lambda: qb.call("POST", f"tables/{table_id}/relationship", {
             "parentTableId": TIME_CARDS,
             "foreignKeyField": {"label": REFERENCE_LABEL},
             "lookupFieldIds": list(LOOKUPS),
             "summaryFields": [
                 {"summaryFid": days["Hours"]["id"], "label": SUMMARY_HOURS, "accumulationType": "SUM"},
                 {"label": SUMMARY_COUNT, "accumulationType": "COUNT"},
             ],
         }))
    # Quickbase names new lookups "<parent record name> - <field>"; rename them to the build sheet's names.
    if apply:
        days = qb.fields(table_id)
    for src, label in LOOKUPS.items():
        current = next((f for f in days.values() if f.get("mode") == "lookup"
                        and f["properties"].get("lookupTargetFieldId") == src), None)
        step(qb, f"rename lookup of Time Cards fid {src} to '{label}'",
             current and current["label"] == label and current["id"],
             lambda: qb.call("POST", f"fields/{current['id']}?tableId={table_id}", {"label": label}))

    print("Step 6: formula fields")
    if apply:
        days = qb.fields(table_id)
    for label, ftype, formula in FORMULA_FIELDS:
        step(qb, f"{label} (formula {ftype})", days.get(label, {}).get("id"),
             lambda: qb.call("POST", f"fields?tableId={table_id}",
                             {"label": label, "fieldType": ftype, "properties": {"formula": formula}})["id"])

    print("Step 7b: Time Cards")
    if apply:
        tc_fields = qb.fields(TIME_CARDS)
    label, ftype, formula = OUT_OF_SYNC
    step(qb, f"{label} (formula {ftype}) on Time Cards", tc_fields.get(label, {}).get("id"),
         lambda: qb.call("POST", f"fields?tableId={TIME_CARDS}",
                         {"label": label, "fieldType": ftype, "appearsByDefault": False,
                          "properties": {"formula": formula}})["id"])
    # Keep the new Time Cards fields out of reports that use "default columns", so users see no change.
    if apply:
        tc_fields = qb.fields(TIME_CARDS)
    for label in (SUMMARY_HOURS, SUMMARY_COUNT, OUT_OF_SYNC[0]):
        f = tc_fields.get(label)
        step(qb, f"'{label}' on Time Cards: not a default report column",
             f and not f.get("appearsByDefault") and f["id"],
             lambda: qb.call("POST", f"fields/{f['id']}?tableId={TIME_CARDS}", {"appearsByDefault": False}))

    if not apply:
        print("\nDry run only. Re-run with --apply to create the missing items.")
        return

    days = qb.fields(table_id)
    tc_fields = qb.fields(TIME_CARDS)
    state = {
        "table": {"name": TABLE["name"], "id": table_id},
        "time_card_days": {label: f["id"] for label, f in sorted(days.items(), key=lambda kv: kv[1]["id"])},
        "time_cards": {label: tc_fields[label]["id"]
                       for label in (SUMMARY_HOURS, SUMMARY_COUNT, OUT_OF_SYNC[0]) if label in tc_fields},
    }
    STATE.write_text(json.dumps(state, indent=2) + "\n")
    print(f"\nDone. Table {table_id}. Field IDs written to {STATE.relative_to(ROOT)}.")
    print("\nStill to do by hand:")
    for i, item in enumerate(MANUAL_STEPS, 1):
        print(f"  {i}. {item}")


if __name__ == "__main__":
    main()
