# My Hours dashboard

A personal dashboard that shows each person their own hours for this week and last week, and their time cards. It runs as Quickbase code pages in the Project Activity app (`bg86uwfcw`).

## Status

Live, with three versions side by side for comparison. None has been chosen as the final one yet.

| Page | File | Styling | Charts | Live URL |
|---|---|---|---|---|
| 42 | `my-hours-dashboard.html` | Custom CSS | Hand-built SVG | [page 42](https://chartindustries.quickbase.com/db/bg86uwfcw?a=dbpage&pageID=42) |
| 43 | `my-hours-bootstrap.html` | Bootstrap 5.3 + Bootstrap Icons | Apache ECharts 5 (donut for projects) | [page 43](https://chartindustries.quickbase.com/db/bg86uwfcw?a=dbpage&pageID=43) |
| 44 | `my-hours-echarts.html` | Custom CSS | Apache ECharts 5 (bars for projects) | [page 44](https://chartindustries.quickbase.com/db/bg86uwfcw?a=dbpage&pageID=44) |

The app home (`/nav/app/bg86uwfcw`) currently opens page 42.

## What each page shows

- **Header:** a greeting with the time of day and first name, the week range, and the person's title, department and location. Buttons for App home, the Auto / Light / Dark theme toggle, and Refresh.
- **Hours cards:** this week's hours with a ring showing progress toward a 40-hour week, last week's hours with the change between weeks, and this week's average per day, days logged and project count.
- **Time cards:** tabs for "My current time cards" and "My last week's time cards", plus an Open report button that opens the report in a new tab. Double-clicking a row, or pressing Enter on it, opens that time card in **edit** mode in a new tab.
- **Daily hours chart:** Sunday to Saturday, this week next to last week. The scale always goes to at least 8 hours and only grows when a day goes over 8.
- **Where this week went:** hours by project, with each project's share of the week.

## Data it depends on

Don't rename, delete or change these without updating the pages.

| What | Where |
|---|---|
| Current Week's Hours / Last Week's Hours | Employees `bhm98v33q`, summary fields **53** / **54**, on the Employees ↔ Time Cards relationship |
| Name, title, department, location | Employees fields 47, 7, 40, 35. The person's user field is **8** |
| Current time cards | Time Cards `bhm9822gc`, report **6** "My Current Time Cards" |
| Last week's time cards | Time Cards report **24** "My Last Week's Time Cards" |
| Time card columns | Fields 3 (Record ID#), 300 Project Name, 137 Time Card Title, Sunday to Saturday 23/10/11/12/13/14/24, 6 Total Regular Hours |

The pages read each report's own filter, columns and sort, then run that query with Record ID# added. The report run API leaves Record ID# out, and the pages need it for double-click to edit. Changes you make to either report in Quickbase still carry through to the dashboard.

## Deploying

```sh
op run --env-file=.qb.env -- python3 scripts/deploy_dashboard_codepages.py                  # status only
op run --env-file=.qb.env -- python3 scripts/deploy_dashboard_codepages.py --deploy         # upload changed pages
op run --env-file=.qb.env -- python3 scripts/deploy_dashboard_codepages.py --deploy my-hours-echarts.html
```

Commit after every deploy. `.codepages.json` records each page's ID and a fingerprint of what was last deployed. The drift check uses that fingerprint to spot edits made directly in Quickbase. In that case, `--pull <page>` copies the live version into the local file for review, and `--deploy --force <page>` overwrites it. Full usage is in the script's header.

## Testing

- **Sample data:** open a page file locally, or add `?demo=1` to the URL.
- **View as someone else:** add `&viewAs=person@chartindustries.com` to a live page URL. Only app administrators can use it. The page shows that person's hours and time cards, read with your permissions, and a blue "Test mode" banner. "Open report in Quickbase" still opens *your* report.
- **Real permissions:** sign in as a regular user in a separate Chrome profile or Guest window. `viewAs` doesn't test permissions.

## Decisions

- **Summary fields, not a formula query, for weekly hours.** A `GetRecords` / `SumValues` formula over Time Cards was rejected by Quickbase as "will take too long to process", even when it filtered on the stored Date field. Employees field 51 "Current Week Hours", the original formula field, is still empty and unused.
- **ECharts for the daily chart, bars for projects.** The daily bar chart is clearer in ECharts. For hours by project, horizontal bars read better than the donut on page 43.
- **At-least-8-hour scale** on the daily chart, so a normal workday always fills the same height.
- **Theme choice is saved per browser**, separately for each page, rather than in a Quickbase field, so no table changes were needed.
- **"View as" is admin-only.** The page checks `API_GetUserRole` for Administrator (access id 1) before using it.

## Prototypes (local only, not deployed)

Both use the Inspinia 5 theme (WrapBootstrap). The theme lives in `Wrapbootstrap/`, which is gitignored and used as reference only. The prototypes load its CSS, icon font and ECharts from that folder, so they only render on this machine. To deploy one, host the theme's `app.min.css` and `vendors.min.css` (icons), the icon font and `echarts.min.js` as code pages, and point the page at them. Also add the page to the deploy script.

| File | What it is |
|---|---|
| `my-hours-inspinia.html` | Page 43 restyled on Inspinia. Same data and behavior. |
| `accounting-period.html` | Hours by accounting period (26th to 25th), split by BU and project, with a Final/Provisional status and CSV export. Uses sample data until the Time Card Days table exists (`pipelines/TimeCardDays_Report_v2.md`). |

## Known issues

- **The Projects count differs between pages.** Pages 42 and 44 count a project whose time card has 0 hours; page 43 doesn't. The plan is to make 42 and 44 match 43.
- **Your own account (Kris Tenney) has no Employees record,** so the live pages show zeros for you. Use `viewAs` to see real data.
- **Pages 43 and 44 load libraries from cdn.jsdelivr.net.** If that site is blocked, their charts don't load, and 43 also loses its styling. Page 42 has no outside dependencies.
- **Dark mode inside a Quickbase dashboard widget** would look out of place, because Quickbase's own UI is light only.
- **The view-as denial for non-admins hasn't been tested** with a real non-admin account.

## Ideas / next

- [ ] Pick a final version (probably 44) and retire the others
- [ ] Make the Projects count on 42 and 44 match 43
- [ ] Embedded mode for a Quickbase dashboard widget: always light, less padding
- [ ] Move the shared styles into a stylesheet code page if more dashboards follow
- [ ] Host ECharts as a code page in the app instead of loading it from the CDN
- [ ] Test once as a real non-admin user

## History

- **2026-10-08:** Explored the app and tables (read only). The Current Week Hours formula was rejected for performance, so the user added summary fields 53 and 54. Page 42 deployed, then iterated on: encoding fix, button changes, card order, double-click to edit, theme toggle.
- **2026-10-08:** Page 43 (Bootstrap + ECharts) and page 44 (custom CSS + ECharts) added. App home button on all pages.
- **2026-10-09:** Added Inspinia prototypes (`my-hours-inspinia.html`, `accounting-period.html`), local only.
- **2026-10-09:** Admin-only `viewAs` test mode on all pages. At-least-8-hour daily scale on all pages. Git repository and deploy drift check set up (initial commit `993cc2f`).
