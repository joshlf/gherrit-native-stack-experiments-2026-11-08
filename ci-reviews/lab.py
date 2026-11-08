#!/usr/bin/env python3
"""Record isolated GitHub CI/review experiments without exposing credentials."""

import datetime
import base64
import json
import pathlib
import subprocess
import sys
import urllib.parse

HERE = pathlib.Path(__file__).resolve().parent
REPO = "joshlf/gherrit-native-stack-experiments-2026-11-08"
REMOTE = f"repos/{REPO}"
CHECKOUT = HERE / "repo"
EVIDENCE = HERE / "evidence"
STATE = HERE / "state.json"
DISCLOSURE = "*Authored by an AI agent acting on joshlf's behalf.*"
TRAILER = "Agent-authored-by: AI agent acting on joshlf's behalf"


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def run(label, args, *, data=None, cwd=HERE, accepted=(0,)):
    started = now()
    result = subprocess.run(args, input=data, text=True, capture_output=True, cwd=cwd)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    stem = EVIDENCE / f"{stamp}-{label}"
    stem.with_suffix(".stdout").write_text(result.stdout)
    stem.with_suffix(".stderr").write_text(result.stderr)
    record = {"started": started, "finished": now(), "argv": args,
              "cwd": str(cwd), "returncode": result.returncode,
              "stdout": str(stem.with_suffix('.stdout').relative_to(HERE)),
              "stderr": str(stem.with_suffix('.stderr').relative_to(HERE))}
    if data is not None:
        request = stem.with_suffix(".request.json")
        request.write_text(data)
        record["request"] = str(request.relative_to(HERE))
    with (EVIDENCE / "commands.jsonl").open("a") as out:
        out.write(json.dumps(record) + "\n")
    if result.returncode not in accepted:
        raise RuntimeError(f"{label} exited {result.returncode}: {result.stderr}")
    return result.stdout


def api(label, endpoint, *, method="GET", body=None, accepted=(0,)):
    args = ["gh", "api", "--method", method, endpoint]
    if body is not None:
        args += ["--input", "-"]
    raw = run(label, args, data=json.dumps(body) if body is not None else None,
              accepted=accepted)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def git(label, *args, accepted=(0,)):
    return run(label, ["git", "-c", "core.hooksPath=/dev/null", *args],
               cwd=CHECKOUT, accepted=accepted).strip()


def save(state):
    STATE.write_text(json.dumps(state, indent=2) + "\n")


def load():
    return json.loads(STATE.read_text()) if STATE.exists() else {"repo": REPO}


def commit(label, message, filename, content, *, amend=False):
    (CHECKOUT / filename).write_text(content)
    git(f"{label}-add", "add", "--", filename)
    git(f"{label}-commit", "-c", "user.name=Josh Liebow-Feeser", "-c",
        "user.email=hello@joshlf.com", "-c", "commit.gpgsign=false", "commit", *(["--amend"] if amend else []),
        "-m", message, "-m", TRAILER)
    return git(f"{label}-sha", "rev-parse", "HEAD")


def create_chain(key, *, bot=False, stacked_ci=False, server_lower=False, signed_source=None, signed_upper=None):
    state = load()
    if key in state:
        raise RuntimeError(f"Refusing to recreate recorded chain {key}")
    stem = f"exp/ci/{key}"
    chain = {"trunk": f"{stem}/trunk", "lower": f"{stem}/lower", "upper": f"{stem}/upper"}
    if signed_upper and not signed_source:
        raise RuntimeError("A signed upper source requires an explicit signed lower source")
    git(f"{key}-fetch", "fetch", "origin", "main")
    chain["seed_sha"] = git(f"{key}-seed", "rev-parse", "origin/main")
    trunk_sha = chain["seed_sha"]
    if signed_source:
        source_commit = api(f"{key}-signed-source", f"{REMOTE}/git/commits/{signed_source}")
        if not source_commit["verification"]["verified"] or len(source_commit["parents"]) != 1:
            raise RuntimeError("Expected a verified, single-parent signed source commit")
        chain["signed_source"] = source_commit
        trunk_sha = source_commit["parents"][0]["sha"]
        git(f"{key}-fetch-signed-source", "fetch", "origin", signed_source)
    chain["original_trunk_sha"] = trunk_sha
    git(f"{key}-trunk", "checkout", "-b", chain["trunk"], trunk_sha)
    if stacked_ci:
        source = (CHECKOUT / ".github/workflows/trunk-filter.yml").read_text()
        content = source.replace("name: trunk-filter", "name: stacked-trunk").replace(
            "  trunk-filter:", "  stacked-trunk:").replace(
            "types: [opened, synchronize, reopened]", "types: [opened, synchronize, reopened, stacked]")
        if content == source or "types: [opened, synchronize, reopened, stacked]" not in content:
            raise RuntimeError("Shared seed no longer matches inspected workflow variant")
        chain["variant_trunk_sha"] = commit(f"{key}-stacked-ci", "Add stacked-event trunk-filter experiment workflow",
             ".github/workflows/stacked-trunk.yml", content)
    git(f"{key}-lower", "checkout", "-b", chain["lower"])
    if signed_source:
        git(f"{key}-reset-signed-source", "reset", "--hard", signed_source)
        chain["lower_sha"] = signed_source
    elif server_lower:
        git(f"{key}-seed-refs", "push", "--atomic", "origin", chain["trunk"], chain["lower"])
        response = api(f"{key}-server-lower", f"{REMOTE}/contents/{key}-lower.txt", method="PUT", body={
            "branch": chain["lower"], "message": f"Add {key} server-authored lower fixture\n\n{TRAILER}",
            "content": base64.b64encode(f"Synthetic {key} lower layer.\n".encode()).decode(),
            "author": {"name": "Josh Liebow-Feeser", "email": "hello@joshlf.com"}})
        chain["server_lower_commit"] = response["commit"]
        chain["lower_sha"] = response["commit"]["sha"]
        git(f"{key}-fetch-server-lower", "fetch", "origin", chain["lower"])
        git(f"{key}-reset-server-lower", "reset", "--hard", chain["lower_sha"])
        verification = api(f"{key}-verify-server-lower", f"{REMOTE}/git/commits/{chain['lower_sha']}")["verification"]
        chain["server_lower_verification"] = verification
        if not verification["verified"]:
            save({**state, key: chain})
            print(json.dumps(chain, indent=2))
            return
    else:
        chain["lower_sha"] = commit(f"{key}-lower", f"Add {key} lower experiment layer",
                                        f"{key}-lower.txt", f"Synthetic {key} lower layer.\n")
    git(f"{key}-upper", "checkout", "-b", chain["upper"])
    if signed_upper:
        upper_commit = api(f"{key}-signed-upper-source", f"{REMOTE}/git/commits/{signed_upper}")
        if not upper_commit["verification"]["verified"] or [p["sha"] for p in upper_commit["parents"]] != [signed_source]:
            raise RuntimeError("Expected a verified upper source directly atop the selected signed lower")
        chain["signed_upper_source"] = upper_commit
        git(f"{key}-fetch-signed-upper-source", "fetch", "origin", signed_upper)
        git(f"{key}-reset-signed-upper-source", "reset", "--hard", signed_upper)
        chain["upper_sha"] = signed_upper
    else:
        chain["upper_sha"] = commit(f"{key}-upper", f"Add {key} upper experiment layer",
                                        f"{key}-upper.txt", f"Synthetic {key} upper layer.\n")
    save({**state, key: chain})
    git(f"{key}-push", "push", "--atomic", "origin", chain["trunk"], chain["lower"], chain["upper"])
    if not bot:
        for position, base in (("lower", "trunk"), ("upper", "lower")):
            pr = api(f"{key}-{position}-create-pr", f"{REMOTE}/pulls", method="POST", body={
                "head": chain[position], "base": chain[base],
                "title": f"Experiment CI {key}: {position} layer",
                "body": f"Synthetic authorized experiment for CI scheduling and native stack metadata.\n\n{DISCLOSURE}"})
            chain[f"{position}_pr"] = pr["number"]
            save({**state, key: chain})
    else:
        chain["bot_prs_pending"] = True
        save({**state, key: chain})
    print(json.dumps({k:v for k,v in chain.items() if k not in ("signed_source", "signed_upper_source")}, indent=2))


def snapshot(key, label):
    state = load()
    chain = state[key]
    result = {"started": now(), "label": label}
    for position in ("lower", "upper"):
        prnum = chain.get(f"{position}_pr")
        if not prnum:
            continue
        pr = api(f"{key}-{label}-{position}-pr", f"{REMOTE}/pulls/{prnum}")
        result[position] = pr
        run(f"{key}-{label}-{position}-gh-pr", ["gh", "pr", "view", str(prnum), "--repo", REPO,
            "--json", "number,headRefOid,baseRefName,reviewDecision,mergeStateStatus,statusCheckRollup,latestReviews"])
        run(f"{key}-{label}-{position}-required-checks", ["gh", "pr", "checks", str(prnum), "--repo", REPO,
            "--required", "--json", "name,state,bucket,workflow,event,link"], accepted=(0,1,8))
        for resource in ("reviews", "commits"):
            api(f"{key}-{label}-{position}-{resource}", f"{REMOTE}/pulls/{prnum}/{resource}")
        api(f"{key}-{label}-{position}-timeline", f"{REMOTE}/issues/{prnum}/timeline?per_page=100")
        api(f"{key}-{label}-{position}-checks", f"{REMOTE}/commits/{pr['head']['sha']}/check-runs?per_page=100")
        if pr.get("merge_commit_sha"):
            api(f"{key}-{label}-{position}-merge-commit", f"{REMOTE}/git/commits/{pr['merge_commit_sha']}", accepted=(0,1))
    api(f"{key}-{label}-runs", f"{REMOTE}/actions/runs?per_page=100")
    api(f"{key}-{label}-refs", f"{REMOTE}/git/matching-refs/heads/exp/ci/{key}/")
    api(f"{key}-{label}-stacks", f"{REMOTE}/stacks?per_page=100")
    api(f"{key}-{label}-protection", f"{REMOTE}/branches/{urllib.parse.quote(chain['trunk'], safe='')}/protection", accepted=(0,1))
    git(f"{key}-{label}-fetch", "fetch", "origin")
    git(f"{key}-{label}-graph", "log", "--graph", "--decorate", "--format=fuller", "--all", "--max-count=40")
    result["finished"] = now()
    (EVIDENCE / f"snapshot-{key}-{label}.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({p: {"number": v["number"], "sha": v["head"]["sha"], "base": v["base"]["ref"], "stack": v.get("stack")} for p,v in result.items() if isinstance(v,dict) and "head" in v}, indent=2))


def register(key):
    state = load()
    chain = state[key]
    if "stack" in chain:
        raise RuntimeError("Already recorded a stack; reconcile instead of retrying")
    body = {"pull_requests": [chain["lower_pr"], chain["upper_pr"]]}
    (HERE / "control" / f"{key}-register-intent.json").write_text(json.dumps({"at": now(), "body": body}, indent=2))
    stack = api(f"{key}-register", f"{REMOTE}/stacks", method="POST", body=body)
    chain["stack"] = stack
    save(state)
    print(json.dumps(stack, indent=2))


def protect(key, *, signed=False):
    chain = load()[key]
    body = {"required_status_checks": None, "enforce_admins": False,
            "required_pull_request_reviews": {"dismiss_stale_reviews": True,
                 "require_code_owner_reviews": False, "required_approving_review_count": 1,
                 "require_last_push_approval": False}, "restrictions": None}
    endpoint = f"{REMOTE}/branches/{urllib.parse.quote(chain['trunk'], safe='')}/protection"
    (HERE / "control" / f"{key}-protection-intent.json").write_text(json.dumps({"at": now(), "endpoint": endpoint, "body": body, "signed": signed}, indent=2))
    result = api(f"{key}-protect", endpoint, method="PUT", body=body)
    if signed:
        api(f"{key}-protect-signed", f"{endpoint}/required_signatures", method="POST")
    print(json.dumps(result, indent=2))


def discover_bot_prs(key):
    state = load()
    chain = state[key]
    for position in ("lower", "upper"):
        prs = api(f"{key}-{position}-discover", f"{REMOTE}/pulls?state=open&head=joshlf:{chain[position]}")
        if len(prs) != 1 or prs[0]["user"]["login"] != "github-actions[bot]":
            raise RuntimeError(f"Expected exactly one github-actions bot PR for {position}")
        chain[f"{position}_pr"] = prs[0]["number"]
    chain.pop("bot_prs_pending", None)
    save(state)
    print(json.dumps(chain, indent=2))


def approve(key):
    chain = load()[key]
    for position in ("lower", "upper"):
        prnum = chain[f"{position}_pr"]
        pr = api(f"{key}-{position}-pre-approve", f"{REMOTE}/pulls/{prnum}")
        if pr["user"]["login"] != "github-actions[bot]":
            raise RuntimeError("Only distinct-author synthetic bot PRs are eligible")
        api(f"{key}-{position}-approve", f"{REMOTE}/pulls/{prnum}/reviews", method="POST", body={
            "commit_id": pr["head"]["sha"], "event": "APPROVE",
            "body": f"Approval for the synthetic review-retention experiment only.\n\n{DISCLOSURE}"})


def rebase_chain(key, hint):
    state = load()
    chain = state[key]
    if chain.get("rebased"):
        raise RuntimeError("Refusing duplicate rebase; use a separate experiment chain")
    git(f"{key}-before-fetch", "fetch", "origin")
    old_lower = git(f"{key}-old-lower", "rev-parse", f"origin/{chain['lower']}")
    old_upper = git(f"{key}-old-upper", "rev-parse", f"origin/{chain['upper']}")
    old_trunk = git(f"{key}-old-trunk", "rev-parse", f"origin/{chain['trunk']}")
    for position, base, head in (("lower", old_trunk, old_lower), ("upper", old_lower, old_upper)):
        git(f"{key}-{position}-before-patch", "diff", "--binary", base, head)
        git(f"{key}-{position}-before-commit", "show", "--format=fuller", "--stat", head)
    git(f"{key}-advance-trunk", "checkout", chain["trunk"])
    git(f"{key}-advance-trunk-reset", "reset", "--hard", old_trunk)
    new_trunk = commit(f"{key}-advance-trunk", f"Advance {key} experiment trunk",
                       f"{key}-trunk.txt", "Unrelated trunk advance for a patch-preserving rebase.\n")
    git(f"{key}-push-trunk", "push", "origin", f"HEAD:refs/heads/{chain['trunk']}")
    snapshot(key, "trunk-advanced-before-rebase")
    git(f"{key}-checkout-lower", "checkout", chain["lower"])
    git(f"{key}-rebase-lower", "-c", "user.name=Josh Liebow-Feeser", "-c", "user.email=hello@joshlf.com",
        "-c", "commit.gpgsign=false", "rebase", "--onto", new_trunk, old_trunk)
    new_lower = git(f"{key}-new-lower", "rev-parse", "HEAD")
    git(f"{key}-checkout-upper", "checkout", chain["upper"])
    git(f"{key}-rebase-upper", "-c", "user.name=Josh Liebow-Feeser", "-c", "user.email=hello@joshlf.com",
        "-c", "commit.gpgsign=false", "rebase", "--onto", new_lower, old_lower)
    new_upper = git(f"{key}-new-upper", "rev-parse", "HEAD")
    for position, old_base, old_head, base, head in (("lower", old_trunk, old_lower, new_trunk, new_lower), ("upper", old_lower, old_upper, new_lower, new_upper)):
        before = git(f"{key}-{position}-rebase-patch-before", "diff", "--binary", old_base, old_head)
        after = git(f"{key}-{position}-rebase-patch-after", "diff", "--binary", base, head)
        if before != after:
            raise RuntimeError(f"{position} patch changed; refusing unchanged-rebase experiment")
    args = (["-c", "push.pushOption=pull.stacked"] if hint else []) + ["push", "--atomic",
        f"--force-with-lease=refs/heads/{chain['lower']}:{old_lower}",
        f"--force-with-lease=refs/heads/{chain['upper']}:{old_upper}", "origin", chain["lower"], chain["upper"]]
    intent = {"at": now(), "old_trunk": old_trunk, "new_trunk": new_trunk,
              "old_lower": old_lower, "new_lower": new_lower, "old_upper": old_upper,
              "new_upper": new_upper, "pull_stacked": hint, "argv": args}
    (HERE / "control" / f"{key}-rebase-intent.json").write_text(json.dumps(intent, indent=2))
    git(f"{key}-force-rebase", *args)
    chain["rebased"] = intent
    save(state)
    print(json.dumps(intent, indent=2))


def substantive(key):
    state = load()
    chain = state[key]
    git(f"{key}-substantive-fetch", "fetch", "origin", chain["upper"])
    expected = git(f"{key}-substantive-old-sha", "rev-parse", f"origin/{chain['upper']}")
    git(f"{key}-substantive-checkout", "checkout", chain["upper"])
    git(f"{key}-substantive-reset", "reset", "--hard", expected)
    changed = commit(f"{key}-substantive", f"Change {key} upper experiment content",
                     f"{key}-upper.txt", "Substantively changed synthetic upper layer.\n", amend=True)
    git(f"{key}-substantive-push", "-c", "push.pushOption=pull.stacked", "push", "origin",
        f"--force-with-lease=refs/heads/{chain['upper']}:{expected}",
        f"HEAD:refs/heads/{chain['upper']}")
    chain["substantive"] = {"old": expected, "new": changed, "at": now()}
    save(state)


def merge_prefix(key, merge_method="squash"):
    state = load()
    chain = state[key]
    if "merge_request" in chain:
        raise RuntimeError("Recorded merge request exists; poll it rather than resubmit")
    pr = api(f"{key}-merge-preflight", f"{REMOTE}/pulls/{chain['lower_pr']}")
    if merge_method not in ("merge", "squash", "rebase"):
        raise RuntimeError("Unsupported merge method")
    body = {"merge_method": merge_method, "merge_action": "default", "sha": pr["head"]["sha"]}
    (HERE / "control" / f"{key}-merge-intent.json").write_text(json.dumps({"at": now(), "body": body}, indent=2))
    response = api(f"{key}-merge-submit", f"{REMOTE}/pulls/{chain['lower_pr']}/merge-async", method="PUT", body=body)
    chain["merge_request"] = response
    save(state)
    print(json.dumps(response, indent=2))


def poll_merge(key):
    chain = load()[key]
    request = chain["merge_request"]
    uuid = request.get("details", {}).get("uuid")
    if not uuid:
        raise RuntimeError("No pending request UUID")
    print(json.dumps(api(f"{key}-merge-poll", f"{REMOTE}/pulls/{chain['lower_pr']}/merge-async/{uuid}"), indent=2))


def dispatch_bot_prs(key):
    chain = load()[key]
    for position, base in (("lower", "trunk"), ("upper", "lower")):
        body = {"ref": "main", "inputs": {"operation": "create-pr", "head": chain[position],
            "base": chain[base], "title": f"Experiment CI {key}: {position} review layer",
            "body": f"Synthetic bot-authored PR for the authorized review-retention experiment.\n\n{DISCLOSURE}"}}
        (HERE / "control" / f"{key}-{position}-bot-dispatch-intent.json").write_text(json.dumps({"at": now(), "body": body}, indent=2))
        api(f"{key}-{position}-bot-dispatch", f"{REMOTE}/actions/workflows/automation.yml/dispatches", method="POST", body=body)


def protect_ci(key, context="trunk-filter"):
    chain = load()[key]
    endpoint = f"{REMOTE}/branches/{urllib.parse.quote(chain['trunk'], safe='')}/protection"
    body = {"required_status_checks": {"strict": False, "contexts": [context]},
            "enforce_admins": True, "required_pull_request_reviews": None, "restrictions": None}
    (HERE / "control" / f"{key}-ci-protection-intent.json").write_text(json.dumps({"at": now(), "endpoint": endpoint, "body": body}, indent=2))
    print(json.dumps(api(f"{key}-ci-protect", endpoint, method="PUT", body=body), indent=2))


def dispatch_check(key, position):
    chain = load()[key]
    body = {"ref": chain[position]}
    (HERE / "control" / f"{key}-{position}-check-dispatch-intent.json").write_text(json.dumps({"at": now(), "body": body}, indent=2))
    api(f"{key}-{position}-check-dispatch", f"{REMOTE}/actions/workflows/trunk-filter.yml/dispatches", method="POST", body=body)


def touch_upper(key):
    chain = load()[key]
    git(f"{key}-touch-upper-checkout", "checkout", chain["upper"])
    git(f"{key}-touch-upper-commit", "-c", "user.name=Josh Liebow-Feeser", "-c",
        "user.email=hello@joshlf.com", "-c", "commit.gpgsign=false", "commit", "--allow-empty",
        "-m", "Trigger a registered-stack synchronization experiment", "-m", TRAILER)
    git(f"{key}-touch-upper-push", "push", "origin", chain["upper"])


def collect_runs(key):
    chain = load()[key]
    runs = api(f"{key}-collect-runs", f"{REMOTE}/actions/runs?per_page=100")["workflow_runs"]
    summaries = []
    for item in runs:
        if item["head_branch"] not in (chain["lower"], chain["upper"]):
            continue
        run_id = item["id"]
        api(f"{key}-run-{run_id}-detail", f"{REMOTE}/actions/runs/{run_id}")
        api(f"{key}-run-{run_id}-jobs", f"{REMOTE}/actions/runs/{run_id}/jobs")
        if item["status"] == "completed":
            destination = EVIDENCE / "actions" / str(run_id)
            if not destination.exists():
                run(f"{key}-run-{run_id}-download", ["gh", "run", "download", str(run_id), "--repo", REPO, "--dir", str(destination)])
            run(f"{key}-run-{run_id}-log", ["gh", "run", "view", str(run_id), "--repo", REPO, "--log"])
        summaries.append({k: item[k] for k in ("id", "name", "event", "head_branch", "head_sha", "status", "conclusion", "created_at")})
    print(json.dumps(summaries, indent=2))


def protect_signatures(key):
    chain = load()[key]
    endpoint = f"{REMOTE}/branches/{urllib.parse.quote(chain['trunk'], safe='')}/protection"
    body = {"required_status_checks": None, "enforce_admins": True,
            "required_pull_request_reviews": None, "restrictions": None}
    (HERE / "control" / f"{key}-signature-protection-intent.json").write_text(json.dumps({"at": now(), "endpoint": endpoint, "body": body, "required_signatures": True}, indent=2))
    api(f"{key}-signature-protection", endpoint, method="PUT", body=body)
    print(json.dumps(api(f"{key}-signature-requirement", f"{endpoint}/required_signatures", method="POST"), indent=2))


def self_approval_rejection(key):
    chain = load()[key]
    pr = api(f"{key}-self-approval-preflight", f"{REMOTE}/pulls/{chain['lower_pr']}")
    if pr["user"]["login"] != "joshlf":
        raise RuntimeError("Expected a joshlf-authored synthetic PR")
    print(json.dumps(api(f"{key}-self-approval-rejection", f"{REMOTE}/pulls/{chain['lower_pr']}/reviews", method="POST", body={
        "commit_id": pr["head"]["sha"], "event": "APPROVE",
        "body": f"Synthetic experiment to record the own-PR approval restriction.\n\n{DISCLOSURE}"}, accepted=(1,)), indent=2))


def enforce_admins(key):
    chain = load()[key]
    endpoint = f"{REMOTE}/branches/{urllib.parse.quote(chain['trunk'], safe='')}/protection/enforce_admins"
    (HERE / "control" / f"{key}-enforce-admins-intent.json").write_text(json.dumps({"at": now(), "endpoint": endpoint}, indent=2))
    api(f"{key}-enforce-admins", endpoint, method="POST")


def compare_native(key, before_label, after_label):
    before = json.loads((EVIDENCE / f"snapshot-{key}-{before_label}.json").read_text())["upper"]
    after = json.loads((EVIDENCE / f"snapshot-{key}-{after_label}.json").read_text())["upper"]
    old, new = before["head"]["sha"], after["head"]["sha"]
    old_parent, new_parent = before["base"]["sha"], after["base"]["sha"]
    old_diff = git(f"{key}-native-upper-before-patch", "diff", "--binary", old_parent, old)
    new_diff = git(f"{key}-native-upper-after-patch", "diff", "--binary", new_parent, new)
    a = api(f"{key}-native-old-upper-commit", f"{REMOTE}/git/commits/{old}")
    b = api(f"{key}-native-new-upper-commit", f"{REMOTE}/git/commits/{new}")
    result = {"at": now(), "before_label": before_label, "after_label": after_label,
              "old_upper": old, "new_upper": new, "old_parent": old_parent, "new_parent": new_parent,
              "patch_bytes_equal": old_diff == new_diff, "tree_equal": a["tree"]["sha"] == b["tree"]["sha"],
              "author_equal": a["author"] == b["author"], "message_equal": a["message"] == b["message"],
              "old_verified": a["verification"]["verified"], "new_verified": b["verification"]["verified"],
              "new_verification_reason": b["verification"]["reason"], "new_committer": b["committer"]}
    (EVIDENCE / f"{key}-native-comparison.json").write_text(json.dumps(result, indent=2) + "\n")
    if not all(result[k] for k in ("patch_bytes_equal", "tree_equal", "author_equal", "message_equal")):
        raise RuntimeError("Native rewrite changed an asserted unchanged-layer property")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    command, *args = sys.argv[1:]
    if command == "create-chain":
        signed_source = args[args.index("--signed-source") + 1] if "--signed-source" in args else None
        signed_upper = args[args.index("--signed-upper") + 1] if "--signed-upper" in args else None
        create_chain(args[0], bot="--bot" in args, stacked_ci="--stacked-ci" in args, server_lower="--server-lower" in args, signed_source=signed_source, signed_upper=signed_upper)
    elif command == "snapshot":
        snapshot(*args)
    elif command == "register":
        register(*args)
    elif command == "protect":
        protect(args[0], signed="--signed" in args)
    elif command == "discover-bot-prs":
        discover_bot_prs(*args)
    elif command == "approve":
        approve(*args)
    elif command == "rebase":
        rebase_chain(args[0], hint="--hint" in args)
    elif command == "substantive":
        substantive(*args)
    elif command == "merge-prefix":
        merge_prefix(*args)
    elif command == "poll-merge":
        poll_merge(*args)
    elif command == "dispatch-bot-prs":
        dispatch_bot_prs(*args)
    elif command == "protect-ci":
        protect_ci(*args)
    elif command == "dispatch-check":
        dispatch_check(*args)
    elif command == "touch-upper":
        touch_upper(*args)
    elif command == "collect-runs":
        collect_runs(*args)
    elif command == "protect-signatures":
        protect_signatures(*args)
    elif command == "self-approval-rejection":
        self_approval_rejection(*args)
    elif command == "enforce-admins":
        enforce_admins(*args)
    elif command == "compare-native":
        compare_native(*args)
    else:
        raise SystemExit(f"Unknown command: {command}")
