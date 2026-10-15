# NPD Account Sync

Runs on a schedule and calls a remote API once for each unique AFE or subledger number per NPD project, then writes the result back to Quickbase. Project Activity app (`bg86uwfcw`), table NPD Investments (`bv6kbiwnp`).

**Status:** Live (2026-10-12). Build sheet: [`NPDAccountSync_Report_v1.md`](NPDAccountSync_Report_v1.md). Export the Pipeline YAML into this folder as `npd-account-sync.yaml`.

NPD Investments fields: 13 First Use of Account Number, 14 API Sync Error, 16 API Last Synced, 17 Account Number Valid. Reports: 6 Values to call, 7 Errors, 8 Data cleanup.
