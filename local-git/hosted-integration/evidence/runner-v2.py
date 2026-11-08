import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import traceback

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "evidence"
EVIDENCE.mkdir(exist_ok=True)
CORE = ROOT / "core.py"
if not CORE.exists():
    shutil.copyfile(ROOT.parent / "harness.py", CORE)
spec = importlib.util.spec_from_file_location("local_git_core", CORE)
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)
REPOSITORY = "joshlf/gherrit-native-stack-experiments-2026-11-08"
API_ROOT = "repos/" + REPOSITORY
PREFIX = "exp/integration/repeat-01"
TRUNK = PREFIX + "/trunk"
NOTICE = "*Authored by an AI agent acting on joshlf's behalf.*"
STATE_PATH = ROOT / "state.json"
STATE = core.read_json(STATE_PATH) if STATE_PATH.exists() else {
    "repository": REPOSITORY, "prefix": PREFIX, "commits": {}, "prs": {}, "groups": {}, "checks": [], "stages": {}}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def save():
    core.atomic_json(STATE_PATH, STATE)


def check(label, actual, expected):
    item = {"label": label, "actual": actual, "expected": expected, "passed": actual == expected, "at": now()}
    STATE["checks"].append(item)
    save()
    if not item["passed"]:
        raise RuntimeError(json.dumps(item, indent=2))


def cmd(argv, cwd=ROOT, input_text=None, allowed=(0,), env=None):
    return core.command(argv, cwd, EVIDENCE / "commands.jsonl", input_text=input_text,
                        allowed=allowed, env=env or core.ENV)


def validate_api(method, path, payload):
    assert path.startswith(API_ROOT + "/")
    if method == "GET":
        return
    known_prs = [value["number"] for value in STATE["prs"].values()]
    if method == "POST" and path == API_ROOT + "/pulls":
        assert payload["head"].startswith(PREFIX + "/") and payload["base"].startswith(PREFIX + "/")
    elif method == "POST" and path == API_ROOT + "/stacks":
        assert all(number in known_prs for number in payload["pull_requests"])
    elif method == "POST" and re.fullmatch(re.escape(API_ROOT) + r"/stacks/\d+/unstack", path):
        assert int(path.split("/")[-2]) in STATE["groups"].values()
    elif method in ["PATCH", "PUT"] and re.fullmatch(re.escape(API_ROOT) + r"/pulls/\d+(?:/merge-async)?", path):
        number = int(path.split("/pulls/")[1].split("/")[0])
        assert number in known_prs
        if method == "PATCH":
            assert set(payload) == {"base"} and payload["base"].startswith(PREFIX + "/")
        else:
            assert path.endswith("/merge-async")
    else:
        raise RuntimeError("Outside authorized API scope: " + method + " " + path)


def api(label, method, path, payload=None):
    assert re.fullmatch(r"[a-zA-Z0-9_-]+", label)
    validate_api(method, path, payload)
    intent = EVIDENCE / (label + ".intent.json")
    receipt = EVIDENCE / (label + ".receipt.json")
    if receipt.exists():
        old = core.read_json(receipt)
        assert (old["method"], old["path"], old["payload"]) == (method, path, payload)
        return old
    if intent.exists():
        raise RuntimeError("Unknown prior dispatch; do not resend: " + label)
    record = {"label": label, "method": method, "path": path, "payload": payload, "start": now(),
              "state": "dispatch_intent", "checkpoint": STATE.get("checkpoint"),
              "source_ranges": STATE.get("source_ranges"), "bindings": STATE["prs"]}
    core.atomic_json(intent, record)
    args = ["gh", "api", "--include", "-H", "X-GitHub-Api-Version: 2026-03-10", "-X", method, path]
    if payload is not None:
        request = EVIDENCE / (label + ".request.json")
        core.atomic_json(request, payload)
        args += ["--input", str(request)]
    result = cmd(args, allowed=(0, 1))
    (EVIDENCE / (label + ".response.txt")).write_text(result.stdout)
    (EVIDENCE / (label + ".stderr.txt")).write_text(result.stderr)
    match = re.search(r"^HTTP/\S+\s+(\d+)", result.stdout)
    parts = re.split(r"\r?\n\r?\n", result.stdout, maxsplit=1)
    body = parts[1] if len(parts) == 2 else ""
    record.update(end=now(), exit=result.returncode, http=int(match.group(1)) if match else None)
    try:
        record["data"] = json.loads(body) if body.strip() else None
    except json.JSONDecodeError:
        record.update(state="unknown_response", parse_error=body)
        core.atomic_json(receipt, record)
        raise RuntimeError("Unparseable response; stop: " + label)
    record["state"] = "http_receipt" if record["http"] else "unknown_response"
    core.atomic_json(receipt, record)
    if not record["http"]:
        raise RuntimeError("No HTTP receipt; stop without retry: " + label)
    if method != "GET":
        time.sleep(1)
    return record


def repository():
    path = ROOT / "repo"
    if not (path / ".git").exists():
        cmd(["git", "clone", "--no-checkout", "--single-branch", "--branch", "main",
             "https://github.com/" + REPOSITORY + ".git", str(path)])
    repo = core.FixtureGit(path, initialize=False)
    for key, value in [("user.name", core.IDENTITY["name"]), ("user.email", core.IDENTITY["email"]),
                       ("core.hooksPath", "/dev/null"), ("commit.gpgsign", "false"),
                       ("credential.helper", "!gh auth git-credential")]:
        repo.git("config", "--local", key, value)
    repo.commits.update(STATE["commits"])
    repo.count = len(STATE["commits"])
    return repo


def message(subject, identity):
    return subject + "\n\nChange-Id: " + identity + "\n\n" + core.TRAILER + "\n"


def remember(repo, label, files, parent, text):
    if label in STATE["commits"]:
        sha = STATE["commits"][label]
        assert repo.files(sha) == files and repo.message(sha) == text
        assert repo.git("rev-parse", sha + "^").stdout.strip() == parent
        return sha
    sha = repo.commit(label, files, parent, text)
    STATE["commits"][label] = sha
    save()
    return sha


def pin_outputs(repo):
    STATE["commits"].update(repo.commits)
    save()


def push(repo, label, updates, expected):
    assert updates.keys() == expected.keys()
    for ref in updates:
        assert ref.startswith(("refs/heads/" + PREFIX + "/", "refs/tags/" + PREFIX + "/"))
    intent = EVIDENCE / (label + ".push-intent.json")
    receipt = EVIDENCE / (label + ".push-receipt.json")
    if receipt.exists():
        old = core.read_json(receipt)
        assert (old["updates"], old["expected"]) == (updates, expected)
        check(label + " cached push confirmed", old["exit"], 0)
        return old
    if intent.exists():
        raise RuntimeError("Unknown prior Git dispatch; do not resend: " + label)
    args = ["push", "--atomic"]
    args += ["--force-with-lease=" + ref + ":" + expected[ref] for ref in updates]
    args += ["origin"] + [sha + ":" + ref for ref, sha in updates.items()]
    record = {"label": label, "start": now(), "updates": updates, "expected": expected, "args": args,
              "state": "dispatch_intent", "checkpoint": STATE.get("checkpoint")}
    core.atomic_json(intent, record)
    result = repo.git(*args, allowed=(0, 1, 128))
    record.update(end=now(), exit=result.returncode, stdout=result.stdout, stderr=result.stderr,
                  state="confirmed_git_exit" if result.returncode == 0 else "stop_reconcile")
    core.atomic_json(receipt, record)
    check(label + " atomic push succeeds", result.returncode, 0)
    return record


def create_pr(key, head, base, title):
    response = api("create-" + key, "POST", API_ROOT + "/pulls", {
        "head": head, "base": base, "title": title,
        "body": "Synthetic end-to-end local reconciliation experiment. No review requested.\n\n" + NOTICE})
    check(key + " PR created", response["http"], 201)
    data = response["data"]
    STATE["prs"][key] = {"number": data["number"], "node_id": data["node_id"], "head": head}
    save()


def snapshot(repo, label):
    data = {"at": now(), "prs": {}, "groups": {}}
    for key, binding in STATE["prs"].items():
        response = api(label + "-pr-" + key, "GET", API_ROOT + "/pulls/" + str(binding["number"]))
        check(label + " " + key + " read", response["http"], 200)
        data["prs"][key] = response["data"]
        check(label + " " + key + " retains node identity", response["data"]["node_id"], binding["node_id"])
    for key, number in STATE["groups"].items():
        response = api(label + "-group-" + key, "GET", API_ROOT + "/stacks/" + str(number))
        data["groups"][key] = {"http": response["http"], "data": response["data"]}
    refs = repo.git("ls-remote", "origin", "refs/heads/" + PREFIX + "/*", "refs/tags/" + PREFIX + "/*").stdout
    data["refs"] = {line.split("\t")[1]: line.split("\t")[0] for line in refs.splitlines()}
    core.atomic_json(EVIDENCE / (label + ".snapshot.json"), data)
    for key, pr in data["prs"].items():
        check(label + " " + key + " head matches ref", data["refs"]["refs/heads/" + pr["head"]["ref"]], pr["head"]["sha"])
    return data


def fetch(repo, label):
    repo.git("fetch", "--no-tags", "origin", "+refs/heads/" + PREFIX + "/*:refs/remotes/observed/*")
    core.atomic_json(EVIDENCE / (label + ".fetched.json"), {"at": now(), "refs": repo.git("show-ref").stdout})


def merge(repo, key, label, sha):
    body = {"merge_method": "squash", "merge_action": "direct_merge", "sha": sha}
    endpoint = API_ROOT + "/pulls/" + str(STATE["prs"][key]["number"]) + "/merge-async"
    response = api(label + "-request", "PUT", endpoint, body)
    check(label + " request accepted", response["http"], 202)
    data = response["data"]
    check(label + " initial state pending", data["status"], "pending")
    details = data["details"]
    check(label + " receipt matches requested intent", {k: details[k] for k in ["merge_method", "merge_action", "expected_head_sha"]},
          {"merge_method": "squash", "merge_action": "direct_merge", "expected_head_sha": sha})
    uuid = details["uuid"]
    for index in range(30):
        poll = api(label + "-poll-" + str(index), "GET", endpoint + "/" + uuid)
        check(label + " poll HTTP", poll["http"], 200)
        status = poll["data"]["status"]
        if status != "pending":
            check(label + " actually merged", status, "merged")
            return poll["data"]
        time.sleep(2)
    raise RuntimeError("Pending merge retained; stop without later mutations: " + label)


def runtime(repo, label, sha, expected_success):
    directory = EVIDENCE / (label + "-tree")
    directory.mkdir(exist_ok=True)
    for path, content in repo.files(sha).items():
        if path.startswith("integration_case/"):
            target = directory / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
    result = cmd([sys.executable, "-c", "from integration_case.consumer import consume; assert consume() == 'retained'"],
                 cwd=directory, allowed=(0, 1), env=dict(core.ENV, PYTHONDONTWRITEBYTECODE="1"))
    core.atomic_json(EVIDENCE / (label + ".runtime.json"), {"sha": sha, "exit": result.returncode,
        "stdout": result.stdout, "stderr": result.stderr, "expected_success": expected_success})
    check(label + " executable dependency", result.returncode == 0, expected_success)


def setup(repo):
    seed = repo.git("rev-parse", "refs/remotes/origin/main").stdout.strip()
    check("authorized main seed", seed.startswith("ed86001d"), True)
    STATE["seed"] = seed
    base_files = repo.files(seed)
    p = remember(repo, "integration_P", dict(base_files, **{"integration_case/__init__.py": ""}), seed,
                 message("Prepare isolated integration fixture", "integration-P"))
    a_files = dict(repo.files(p), **{"integration_case/model.py": "class Record:\n    def __init__(self):\n        self.legacy = 'ready'\n"})
    a = remember(repo, "integration_A_v1", a_files, p, message("Introduce the original record", "integration-A"))
    b_files = dict(repo.files(a), **{"integration_case/consumer.py": "from .model import Record\n\ndef consume():\n    return Record().legacy\n"})
    b = remember(repo, "integration_B_v1", b_files, a, message("Consume the original record", "integration-B"))
    la_files = dict(repo.files(a), **{"integration_case/model.py": a_files["integration_case/model.py"] + "        self.field = 'retained'\n"})
    la = remember(repo, "integration_A_local", la_files, p, message("Introduce the record and pending field", "integration-A"))
    lb_files = dict(repo.files(la), **{"integration_case/consumer.py": "from .model import Record\n\ndef consume():\n    return Record().field\n"})
    lb = remember(repo, "integration_B_local", lb_files, la, message("Consume the retained field", "integration-B"))
    STATE["source_ranges"] = {"A": {"incorporated": {"base": p, "tip": a}, "local": {"base": p, "tip": la}},
                               "B": {"incorporated": {"base": a, "tip": b}, "local": {"base": la, "tip": lb}}}
    save()
    refs = {"refs/heads/" + TRUNK: p, "refs/heads/" + PREFIX + "/A": a, "refs/heads/" + PREFIX + "/B": b,
            "refs/tags/" + PREFIX + "/authored/A/v1": a, "refs/tags/" + PREFIX + "/authored/B/v1": b}
    push(repo, "first-publication", refs, {ref: "" for ref in refs})
    create_pr("A", PREFIX + "/A", TRUNK, "Integration experiment: original A")
    create_pr("B", PREFIX + "/B", PREFIX + "/A", "Integration experiment: canonical B")
    response = api("register-original", "POST", API_ROOT + "/stacks", {"pull_requests": [STATE["prs"][key]["number"] for key in ["A", "B"]]})
    check("original group created", response["http"], 201)
    STATE["groups"]["original"] = response["data"]["number"]
    save()
    snap = snapshot(repo, "original-published")
    check("original exact membership", [x["number"] for x in snap["groups"]["original"]["data"]["pull_requests"]],
          [STATE["prs"][key]["number"] for key in ["A", "B"]])
    runtime(repo, "unpublished-dependent-source", lb, True)
    STATE["checkpoint"] = {"authored": {"A": {"base": p, "tip": a}, "B": {"base": a, "tip": b}},
                           "incorporated": {"A": {"base": p, "tip": a}, "B": {"base": a, "tip": b}}}
    save()


def first_import(repo):
    old_a = STATE["source_ranges"]["A"]["incorporated"]["tip"]
    STATE["first_landing"] = merge(repo, "A", "land-old-A", old_a)
    save()
    observe_first_import(repo, "old-A-landed")


def resume_first_import(repo):
    assert STATE["first_landing"]["status"] == "merged"
    observe_first_import(repo, "old-A-landed-recovery-01")


def observe_first_import(repo, label):
    old_a = STATE["source_ranges"]["A"]["incorporated"]["tip"]
    one = snapshot(repo, label + "-first")
    time.sleep(2)
    two = snapshot(repo, label + "-second")
    check("A terminal after native landing", two["prs"]["A"]["merged"], True)
    check("canonical B remains open", (two["prs"]["B"]["state"], two["prs"]["B"]["merged"]), ("open", False))
    check("two finite samples agree on B and trunk", (one["prs"]["B"]["head"]["sha"], one["refs"]["refs/heads/" + TRUNK]),
          (two["prs"]["B"]["head"]["sha"], two["refs"]["refs/heads/" + TRUNK]))
    fetch(repo, "old-A-landed")
    s = two["refs"]["refs/heads/" + TRUNK]
    hb = two["prs"]["B"]["head"]["sha"]
    check("native B comparison parent is actual trunk", two["prs"]["B"]["base"]["sha"], s)
    check("landed A exact tree", repo.files(s), repo.files(old_a))
    check("rewritten hosted B exact tree", repo.files(hb), repo.files(STATE["source_ranges"]["B"]["incorporated"]["tip"]))
    pending = repo.merge("landed_A_pending_delta", old_a, s, STATE["source_ranges"]["A"]["local"]["tip"])
    f = repo.commit_tree("integration_F", repo.git("rev-parse", pending + "^{tree}").stdout.strip(), s,
                         message("Add the retained field after A landed", "integration-F"))
    original = STATE["source_ranges"]["B"]
    layers = [core.Layer("B", core.RevisionRange(**original["incorporated"]), core.RevisionRange(**original["local"]), core.RevisionRange(s, hb))]
    output = repo.integrate("actual_hosted_first_import", layers, f)
    b = output[0]["accepted_local"]["tip"]
    check("F owns only its added field", repo.git("diff", "--name-only", s, f).stdout.splitlines(), ["integration_case/model.py"])
    check("B owns only its consumer change", repo.git("diff", "--name-only", f, b).stdout.splitlines(), ["integration_case/consumer.py"])
    check("B is directly above F", repo.git("rev-parse", b + "^").stdout.strip(), f)
    check("B message preserved exactly", repo.message(b), repo.message(original["local"]["tip"]))
    runtime(repo, "first-import-B-after-F", b, True)
    runtime(repo, "negative-B-without-F", output[0]["integrated"], False)
    STATE["first_import"] = {"hosted_trunk": s, "hosted_B": {"base": s, "tip": hb},
                             "F": {"base": s, "tip": f}, "B": {"base": f, "tip": b}, "algorithm": output}
    pin_outputs(repo)


def publish_rebuilt(repo):
    imported = STATE["first_import"]
    response = api("release-original", "POST", API_ROOT + "/stacks/" + str(STATE["groups"]["original"]) + "/unstack")
    check("release original eligible members", response["http"], 204)
    released = snapshot(repo, "released-original")
    check("B released from old native group", released["prs"]["B"].get("stack"), None)
    check("A remains terminal after release", released["prs"]["A"]["merged"], True)
    check("B already parked at trunk after native prefix", released["prs"]["B"]["base"]["ref"], TRUNK)
    core.atomic_json(EVIDENCE / "parking-observation.json", {"at": now(), "base": TRUNK,
        "effect": "none_required", "reason": "Native prefix landing already placed B at the trunk; confirmed after release."})
    f, b = imported["F"]["tip"], imported["B"]["tip"]
    refs = {"refs/heads/" + PREFIX + "/F": f, "refs/heads/" + PREFIX + "/B": b,
            "refs/tags/" + PREFIX + "/authored/F/v1": f, "refs/tags/" + PREFIX + "/authored/B/v2": b}
    expected = {ref: "" for ref in refs}
    expected["refs/heads/" + PREFIX + "/B"] = released["refs"]["refs/heads/" + PREFIX + "/B"]
    push(repo, "rebuilt-coupled-heads-and-archives", refs, expected)
    create_pr("F", PREFIX + "/F", TRUNK, "Integration experiment: new-ID follow-up F")
    response = api("final-base-canonical-B", "PATCH", API_ROOT + "/pulls/" + str(STATE["prs"]["B"]["number"]), {"base": PREFIX + "/F"})
    check("B final base set to F", response["http"], 200)
    final_bases = snapshot(repo, "final-adjacent-bases")
    check("B final base adjacency", final_bases["prs"]["B"]["base"]["sha"], f)
    response = api("register-rebuilt", "POST", API_ROOT + "/stacks", {"pull_requests": [STATE["prs"][key]["number"] for key in ["F", "B"]]})
    check("rebuilt F-B group registered", response["http"], 201)
    STATE["groups"]["rebuilt"] = response["data"]["number"]
    save()
    confirmed = snapshot(repo, "rebuilt-publication-confirmed")
    check("rebuilt exact membership", [p["number"] for p in confirmed["groups"]["rebuilt"]["data"]["pull_requests"]],
          [STATE["prs"][key]["number"] for key in ["F", "B"]])
    check("A remains terminal after rebuilt publication", confirmed["prs"]["A"]["merged"], True)
    for key in ["A", "B"]:
        check(key + " v1 archive retained exactly", confirmed["refs"]["refs/tags/" + PREFIX + "/authored/" + key + "/v1"],
              STATE["source_ranges"][key]["incorporated"]["tip"])
    later_files = dict(repo.files(b))
    later_files["integration_case/consumer.py"] += "\ndef pending_note():\n    return 'later local edit'\n"
    later = remember(repo, "integration_B_after_capture", later_files, f, repo.message(b))
    STATE["later_local"] = {"base": f, "tip": later}
    STATE["checkpoint"] = {"authored": {"F": imported["F"], "B": imported["B"]},
                           "incorporated": {"F": imported["F"], "B": imported["B"]},
                           "accepted_local": {"F": imported["F"], "B": imported["B"]},
                           "confirmed_at": now(), "snapshot": "rebuilt-publication-confirmed"}
    check("captured export checkpoint excludes later edit", STATE["checkpoint"]["authored"]["B"]["tip"] == later, False)
    check("later local edit remains pending", repo.git("diff", "--name-only", b, later).stdout.splitlines(), ["integration_case/consumer.py"])
    save()


def second_import(repo):
    imported = STATE["first_import"]
    STATE["second_landing"] = merge(repo, "F", "land-F", imported["F"]["tip"])
    save()
    first = snapshot(repo, "F-landed-first")
    time.sleep(2)
    hosted = snapshot(repo, "F-landed-second")
    check("F terminal after native landing", hosted["prs"]["F"]["merged"], True)
    check("B canonical review still open after second landing", (hosted["prs"]["B"]["state"], hosted["prs"]["B"]["merged"]), ("open", False))
    check("two finite second samples agree", (first["prs"]["B"]["head"]["sha"], first["refs"]["refs/heads/" + TRUNK]),
          (hosted["prs"]["B"]["head"]["sha"], hosted["refs"]["refs/heads/" + TRUNK]))
    fetch(repo, "F-landed")
    s = hosted["refs"]["refs/heads/" + TRUNK]
    hb = hosted["prs"]["B"]["head"]["sha"]
    check("second B comparison parent is trunk", hosted["prs"]["B"]["base"]["sha"], s)
    check("second landed trunk equals F tree", repo.files(s), repo.files(imported["F"]["tip"]))
    old = core.RevisionRange(**imported["B"])
    observed = core.RevisionRange(s, hb)
    no_pending = repo.integrate("second_no_pending", [core.Layer("B", old, old, observed)], s)
    pending = repo.integrate("second_with_pending", [core.Layer("B", old, core.RevisionRange(**STATE["later_local"]), observed)], s)
    no_tip = no_pending[0]["accepted_local"]["tip"]
    pending_tip = pending[0]["accepted_local"]["tip"]
    check("no-pending import equals hosted tree", repo.files(no_tip), repo.files(hb))
    check("no-pending import preserves hosted message", repo.message(no_tip), repo.message(hb))
    check("pending import retains only later local edit", repo.git("diff", "--name-only", hb, pending_tip).stdout.splitlines(), ["integration_case/consumer.py"])
    check("pending note content survives", "later local edit" in repo.files(pending_tip)["integration_case/consumer.py"], True)
    runtime(repo, "second-import-with-pending", pending_tip, True)
    for name, tip, accepted in [("no-pending", hb, {"base": s, "tip": hb}),
                                ("with-pending", pending_tip, pending[0]["accepted_local"])]:
        ref = "refs/heads/local-continuation-" + name
        intent = {"at": now(), "ref": ref, "tip": tip, "incorporated": {"base": s, "tip": hb},
                  "accepted_local": accepted, "authored_submission": imported["B"]}
        core.atomic_json(EVIDENCE / (name + "-continuation-intent.json"), intent)
        repo.git("update-ref", ref, tip, core.ZERO)
        core.atomic_json(EVIDENCE / (name + "-continuation-checkpoint.json"), intent)
    check("no-pending continuation uses exact hosted range", repo.git("rev-parse", "refs/heads/local-continuation-no-pending").stdout.strip(), hb)
    check("last authored export remains exact captured B", STATE["checkpoint"]["authored"]["B"], imported["B"])
    final = snapshot(repo, "final-observation-only")
    check("import made no additional remote ref/archive changes", final["refs"], hosted["refs"])
    STATE["second_import"] = {"hosted": {"base": s, "tip": hb}, "no_pending": no_pending,
                              "with_pending": pending, "no_op_decision": "Accept exact confirmed hosted range; no remote write or new authored archive needed",
                              "native_handoff_limit": "Two finite agreeing samples and successful later writes are observations, not provider settlement proof."}
    pin_outputs(repo)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["setup", "first-import", "resume-first-import", "publish-rebuilt", "second-import"])
    args = parser.parse_args()
    core.atomic_json(ROOT / "environment.json", {"at": now(), "repository": REPOSITORY, "prefix": PREFIX,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "core_sha256": hashlib.sha256(CORE.read_bytes()).hexdigest(), "identity": core.IDENTITY})
    if STATE["stages"].get(args.stage) == "complete":
        print(json.dumps({"stage": args.stage, "status": "already_complete", "prs": STATE["prs"], "groups": STATE["groups"]}))
        return 0
    repo = repository()
    try:
        {"setup": setup, "first-import": first_import, "resume-first-import": resume_first_import, "publish-rebuilt": publish_rebuilt,
         "second-import": second_import}[args.stage](repo)
        STATE["stages"][args.stage] = "complete"
        STATE["commits"].update(repo.commits)
        save()
        repo.save_inventory(EVIDENCE / (args.stage + "-inventory.json"))
        print(json.dumps({"stage": args.stage, "status": "complete", "prs": STATE["prs"], "groups": STATE["groups"],
                          "checks": len(STATE["checks"])}))
        return 0
    except Exception:
        STATE["stages"][args.stage] = "stopped"
        STATE["commits"].update(repo.commits)
        save()
        failure = EVIDENCE / (args.stage + "-failure-" + str(time.time_ns()) + ".txt")
        failure.write_text(traceback.format_exc())
        print(json.dumps({"stage": args.stage, "status": "stopped", "failure": str(failure)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
