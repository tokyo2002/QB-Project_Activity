"""Deploy the dashboard code page(s) to the Project Activity Quickbase app.

Adds or replaces code pages only (XML API API_AddReplaceDBPage) — no table,
field, or record changes.

    # status (default): compare each local file with the live page; uploads nothing
    op run --env-file=.qb.env -- python3 scripts/deploy_dashboard_codepages.py

    # upload changed pages (all pages, or only the named ones)
    op run --env-file=.qb.env -- python3 scripts/deploy_dashboard_codepages.py --deploy
    op run --env-file=.qb.env -- python3 scripts/deploy_dashboard_codepages.py --deploy my-hours-bootstrap.html

    # a page was edited in Quickbase: copy the live version into the local file to review
    op run --env-file=.qb.env -- python3 scripts/deploy_dashboard_codepages.py --pull my-hours-dashboard.html

    # overwrite a page that was edited in Quickbase, discarding those edits
    op run --env-file=.qb.env -- python3 scripts/deploy_dashboard_codepages.py --deploy --force my-hours-dashboard.html

Drift check: after each upload the script records a fingerprint of what it sent in
dashboard/.codepages.json. Before uploading again it fetches the live page; if the
live page no longer matches that fingerprint, someone changed it in Quickbase and the
upload is refused (use --pull to review those changes, or --force to discard them).

The first upload creates the page and records its page ID, so later runs replace
the same page.
"""
import hashlib
import json
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "dashboard" / ".codepages.json"
TOKEN_PLACEHOLDER = "__QB_APP_TOKEN__"

# local file -> Quickbase page name
PAGES = {
    "dashboard/my-hours-dashboard.html": "my-hours-dashboard.html",
    "dashboard/my-hours-bootstrap.html": "my-hours-bootstrap.html",
    "dashboard/my-hours-echarts.html": "my-hours-echarts.html",
}


def env(name):
    value = os.environ.get(name, "")
    if not value or value.startswith("op://"):
        sys.exit(f"{name} is not resolved — run this through `op run --env-file=.qb.env --`.")
    return value


def normalize(text):
    # Quickbase stores pages with CRLF line endings and may trim whitespace.
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").strip().split("\n"))


def fingerprint(text):
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def xml_api(realm, app_id, action, payload):
    req = urllib.request.Request(
        f"https://{realm}/db/{app_id}",
        data=f"<qdbapi>{payload}</qdbapi>".encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/xml", "QUICKBASE-ACTION": action},
    )
    with urllib.request.urlopen(req) as resp:
        root = ET.fromstring(resp.read())
    if root.findtext("errcode") != "0":
        sys.exit(f"{action}: {root.findtext('errtext')} — {root.findtext('errdetail') or ''}")
    return root


def get_page(realm, app_id, user_token, page_id):
    root = xml_api(realm, app_id, "API_GetDBPage", f"<usertoken>{user_token}</usertoken><pageID>{page_id}</pageID>")
    # The body comes back as escaped text with each line break marked by a <BR/> element.
    return "".join(root.find("pagebody").itertext())


def add_replace_page(realm, app_id, user_token, name, body, page_id=None):
    if "]]>" in body:
        sys.exit(f"{name}: page body contains ']]>' and cannot be wrapped in CDATA.")
    target = f"<pageid>{page_id}</pageid>" if page_id else f"<pagename>{name}</pagename>"
    root = xml_api(realm, app_id, "API_AddReplaceDBPage",
                   f"<usertoken>{user_token}</usertoken>{target}<pagetype>1</pagetype>"
                   f"<pagebody><![CDATA[{body}]]></pagebody>")
    return root.findtext("pageID")


def load_state():
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    # Older format stored just the page ID.
    return {k: (v if isinstance(v, dict) else {"pageId": v}) for k, v in state.items()}


def main():
    args = sys.argv[1:]
    deploy, force, pull = "--deploy" in args, "--force" in args, "--pull" in args
    flags = {"--deploy", "--force", "--pull"}
    bad_flags = [a for a in args if a.startswith("--") and a not in flags]
    if bad_flags:
        sys.exit(f"Unknown option(s): {' '.join(bad_flags)}")
    if deploy and pull:
        sys.exit("Use either --deploy or --pull, not both.")
    if force and not deploy:
        sys.exit("--force only applies with --deploy.")
    only = [a for a in args if not a.startswith("--")]
    unknown = set(only) - set(PAGES.values())
    if unknown:
        sys.exit(f"Unknown page name(s): {', '.join(sorted(unknown))}. Known: {', '.join(PAGES.values())}")
    if pull and not only:
        sys.exit("--pull needs the page name(s) to pull, e.g. --pull my-hours-dashboard.html")

    realm = env("CHART_QUICKBASE_REALM_HOSTNAME")
    app_id = env("CHART_QUICKBASE_APP_DBID")
    app_token = env("CHART_QUICKBASE_APP_TOKEN")
    user_token = env("CHART_QUICKBASE_USER_TOKEN")

    state = load_state()
    blocked = []
    for src, name in PAGES.items():
        if only and name not in only:
            continue
        local = (ROOT / src).read_text(encoding="utf-8")
        # Quickbase mangles non-ASCII in code pages (shows as U+FFFD); use entities / \u escapes.
        bad = sorted({c for c in local if ord(c) > 127})
        if bad:
            sys.exit(f"{src}: non-ASCII characters {bad!r} — replace with HTML entities or \\u escapes.")
        if TOKEN_PLACEHOLDER not in local:
            sys.exit(f"{src}: app token placeholder not found.")

        entry = state.setdefault(name, {})
        page_id = entry.get("pageId")
        local_fp = fingerprint(local)

        if not page_id:
            if pull:
                sys.exit(f"{name}: not deployed yet, nothing to pull.")
            status, live_fp, drift = "new page, not yet in Quickbase", None, False
        else:
            live = get_page(realm, app_id, user_token, page_id).replace(app_token, TOKEN_PLACEHOLDER)
            live_fp = fingerprint(live)
            baseline = entry.get("deployedSha256")
            if baseline is None and live_fp == local_fp:
                entry["deployedSha256"] = baseline = live_fp  # first run of the drift check: adopt as baseline
            if pull:
                (ROOT / src).write_text(normalize(live) + "\n", encoding="utf-8")
                entry["deployedSha256"] = live_fp
                print(f"{name}: copied live page {page_id} into {src} — review with `git diff {src}`")
                continue
            drift = baseline is None or live_fp != baseline
            if drift:
                status = ("CHANGED IN QUICKBASE since the last deploy" if baseline
                          else "live page differs from local and there's no record of the last deploy")
            elif live_fp == local_fp:
                status = "in sync"
            else:
                status = "local changes ready to deploy"

        label = f"{name} (page {page_id})" if page_id else name
        if not deploy:
            print(f"{label}: {status}")
            continue
        if drift and not force:
            print(f"{label}: {status} — NOT uploaded. Review with --pull {name}, or overwrite with --deploy --force {name}.")
            blocked.append(name)
            continue
        if page_id and live_fp == local_fp:
            entry["deployedSha256"] = local_fp
            print(f"{label}: already up to date, skipped")
            continue
        page_id = add_replace_page(realm, app_id, user_token, name, local.replace(TOKEN_PLACEHOLDER, app_token), page_id)
        entry.update(pageId=page_id, deployedSha256=local_fp)
        print(f"{name}: {'overwrote Quickbase edits on ' if drift else 'deployed to '}page {page_id}"
              f" -> https://{realm}/db/{app_id}?a=dbpage&pageID={page_id}")

    STATE.write_text(json.dumps(state, indent=2) + "\n")
    if blocked:
        sys.exit(1)


if __name__ == "__main__":
    main()
