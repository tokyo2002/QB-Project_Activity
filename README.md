# Project Activity (Chart Quickbase)

Working repo for customizations to Chart's **Project Activity** Quickbase app. The app tracks projects, tasks and employee time cards.

| | |
|---|---|
| Realm | `chartindustries.quickbase.com` |
| App | Project Activity, `bg86uwfcw` |
| Key tables | Employees `bhm98v33q`, Time Cards `bhm9822gc` (~550k records), Projects `bpaz4pr6u`, Tasks `biwfb28d9` |

This is the **production** app. Read-only exploration through the API is fine. Any change to tables, fields, reports or roles should be agreed first and done deliberately, either by hand in Quickbase or by a reviewed script.

## Workstreams

Each workstream has its own folder and a notes file that tracks its status, decisions and open issues.

| Workstream | Folder | Notes |
|---|---|---|
| My Hours dashboard (code pages 42, 43, 44) | [`dashboard/`](dashboard/) | [`dashboard/dashboard.md`](dashboard/dashboard.md) |
| Pipelines: Time Card Days for accounting-period hours | [`pipelines/`](pipelines/) | [`pipelines/pipelines.md`](pipelines/pipelines.md) |

To add a workstream, give it a folder with its own `<name>.md` notes file, add a row here, and put any scripts it needs in `scripts/`.

## Setup

1. Install the [1Password CLI](https://developer.1password.com/docs/cli/) (`op`) and sign in.
2. Copy `.qb.env.example` to `.qb.env`. The copy is gitignored. Point its `op://` references at your Quickbase app token and user token.
3. Check that a reference resolves:
   ```sh
   op read "op://<vault>/<item>/<field>"
   ```

Every command that talks to Quickbase runs through `op run`, so tokens are never written to disk:

```sh
op run --env-file=.qb.env -- python3 scripts/<script>.py
```

## Layout

```
.qb.env.example      template for the local, gitignored .qb.env
dashboard/           My Hours dashboard code pages (see dashboard/dashboard.md)
pipelines/           Pipeline build sheets and exported YAML (see pipelines/pipelines.md)
scripts/             tools that talk to Quickbase (each has usage notes in its header)
```

## Conventions

- **Git is the record.** Edit files here, deploy with a script, and commit after each deploy. Don't edit code pages in Quickbase's page editor. The deploy script's drift check catches it if someone does.
- **No secrets in the repo.** `.qb.env` is gitignored. Code pages keep the `__QB_APP_TOKEN__` placeholder, and the deploy script swaps in the real token when it uploads.
- **Code pages must be pure ASCII.** Quickbase turns non-ASCII characters into a "�" diamond. Use HTML entities in markup and `\u` escapes in JavaScript. The deploy script refuses to upload a page that isn't ASCII.
