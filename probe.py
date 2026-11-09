import hashlib
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener


REPOSITORY = "joshlf/gherrit-native-stack-experiments-2026-11-08"
REPOSITORY_ID = 1450723431
PREFIX = "exh-1109-causal-rb-app-001"
RUNNER_REF = "refs/heads/" + PREFIX + "/runner"
SAFE_HEADERS = {
    "date", "content-type", "x-github-request-id", "x-accepted-github-permissions",
    "x-oauth-scopes", "x-accepted-oauth-scopes", "x-github-api-version-selected",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class PremiseError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PremiseError(message)


def write_new(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def sanitize(value, token):
    if isinstance(value, dict):
        return {key: "<redacted>" if re.search(r"(?i)authorization|cookie|(?:access|refresh|auth|session)[_-]?token|password|secret", key) else sanitize(item, token) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item, token) for item in value]
    if isinstance(value, str):
        value = value.replace(token, "<redacted>") if token else value
        return re.sub(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b", "<redacted>", value)
    return value


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        return None


def request_once(method, path, payload, token, output):
    require(method in {"GET", "PUT"}, "unsupported_method")
    require(path.startswith(("/repositories/1450723431", "/repos/" + REPOSITORY + "/")), "foreign_request_path")
    if method == "PUT":
        require(re.fullmatch(r"/repositories/1450723431/stacks/[1-9][0-9]*/rebase", path), "not_the_numeric_rebase_route")
    body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
    record = {"method": method, "path": path, "payload": payload, "started_utc": now()}
    req = Request("https://api.github.com" + path, data=body, method=method, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10",
        "User-Agent": "gherrit-synthetic-rebase-app-probe",
        "Content-Type": "application/json",
    })
    try:
        try:
            response = build_opener(NoRedirect).open(req, timeout=30)
        except HTTPError as error:
            response = error
        with response:
            record["status"] = response.status
            record["headers"] = {key.lower(): value for key, value in response.headers.items() if key.lower() in SAFE_HEADERS}
            raw = response.read(262145)
            if len(raw) > 262144:
                record["body_omitted"] = "response_over_256KiB; exact bytes not retained"
            else:
                try:
                    record["body"] = json.loads(raw)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    record["body"] = raw.decode("utf-8", errors="replace")
    except (URLError, TimeoutError, OSError, HTTPException) as error:
        record["transport_error_class"] = type(error).__name__
        record["disposition"] = "unknown_if_PUT; no_retry"
    record["ended_utc"] = now()
    record = sanitize(record, token)
    write_new(output, record)
    return record


def require_body(record, status=200):
    require(record.get("status") == status and isinstance(record.get("body"), dict), "read_premise_failed")
    return record["body"]


def validate_config(config, env, event, config_bytes, code_bytes):
    require(config.get("schema") == "native-rebase-app-one-shot-v1" and config.get("root_reviewed") is True, "unreviewed_config")
    require(config.get("repository") == REPOSITORY and config.get("repository_id") == REPOSITORY_ID, "foreign_repository")
    require(config.get("prefix") == PREFIX and config.get("runner_ref") == RUNNER_REF, "foreign_ref_scope")
    require(env.get("GITHUB_REPOSITORY") == REPOSITORY and env.get("GITHUB_REF") == RUNNER_REF, "foreign_runner")
    require(env.get("GITHUB_EVENT_NAME") == "push" and env.get("GITHUB_RUN_ATTEMPT") == "1" and env.get("GITHUB_ACTOR") == "joshlf", "not_first_root_push_run")
    require(event.get("created") is True and event.get("deleted") is False and event.get("before") == "0" * 40, "not_create_only_push")
    require(event.get("after") == env.get("GITHUB_SHA") and re.fullmatch(r"[0-9a-f]{40}", env.get("GITHUB_SHA", "")), "event_commit_mismatch")
    require(event.get("repository", {}).get("id") == REPOSITORY_ID, "event_repository_mismatch")
    require(sha256(config_bytes) == env.get("PROBE_CONFIG_SHA256"), "config_hash_mismatch")
    require(sha256(code_bytes) == config.get("probe_sha256"), "probe_source_mismatch")
    require(isinstance(config.get("stack_number"), int) and config["stack_number"] > 653 and isinstance(config.get("stack_node_id"), str) and config["stack_node_id"], "missing_fresh_stack_identity")
    require(config.get("trunk", {}).get("ref") == PREFIX + "/trunk" and re.fullmatch(r"[0-9a-f]{40}", config["trunk"].get("sha", "")), "invalid_trunk")
    members = config.get("members", [])
    require(len(members) in {2, 3}, "expected_two_or_three_members")
    require(len({member["number"] for member in members}) == len(members), "duplicate_member")
    for index, member in enumerate(members):
        require(isinstance(member["number"], int) and member["number"] > 653 and isinstance(member.get("node_id"), str) and member["node_id"], "invalid_fresh_member_identity")
        require(member["head_ref"] == PREFIX + "/" + "ABC"[index], "foreign_member_ref")
        require(member["base_ref"] == (PREFIX + "/trunk" if index == 0 else members[index - 1]["head_ref"]), "nonadjacent_member")
        require(re.fullmatch(r"[0-9a-f]{40}", member.get("head_oid", "")), "invalid_expected_head")
    return {"expected_head_oid_by_pr_number": {str(member["number"]): member["head_oid"] for member in members}}


def run(config_path, directory):
    directory.mkdir(exist_ok=False)
    token = os.environ.get("GH_TOKEN", "")
    require(bool(token), "missing_actions_token")
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_bytes())
    payload = validate_config(config, os.environ, event, config_bytes, Path(__file__).read_bytes())
    metadata = {key: os.environ[key] for key in ["GITHUB_REPOSITORY", "GITHUB_REF", "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_ACTOR"]}
    write_new(directory / "context.json", {"event": "create-only push", "runner": metadata, "authentication": "Actions repository-scoped installation token; value never retained", "requested_permissions": {"contents": "write", "pull-requests": "write"}, "config_sha256": sha256(config_bytes), "probe_sha256": sha256(Path(__file__).read_bytes())})
    def get(label, path):
        return require_body(request_once("GET", path, None, token, directory / (label + ".json")))
    repository = get("repository", "/repositories/" + str(REPOSITORY_ID))
    require(repository.get("id") == REPOSITORY_ID and repository.get("full_name") == REPOSITORY, "live_repository_mismatch")
    base_path = "/repos/" + REPOSITORY
    stack = get("stack", base_path + "/stacks/" + str(config["stack_number"]))
    require(stack.get("number") == config["stack_number"] and stack.get("node_id") == config["stack_node_id"] and stack.get("open") is True and stack.get("base", {}).get("ref") == config["trunk"]["ref"], "live_stack_identity_mismatch")
    require([item["number"] for item in stack.get("pull_requests", [])] == [member["number"] for member in config["members"]], "live_membership_mismatch")
    trunk = get("trunk", base_path + "/git/ref/heads/" + quote(config["trunk"]["ref"], safe="/"))
    require(trunk.get("object", {}).get("sha") == config["trunk"]["sha"], "live_trunk_mismatch")
    for index, member in enumerate(config["members"]):
        pr = get("pr-" + str(index), base_path + "/pulls/" + str(member["number"]))
        require(pr.get("number") == member["number"] and pr.get("node_id") == member["node_id"] and pr.get("state") == "open", "live_pr_identity_or_lifecycle_mismatch")
        require(pr.get("head", {}).get("repo", {}).get("id") == REPOSITORY_ID and pr.get("base", {}).get("repo", {}).get("id") == REPOSITORY_ID, "foreign_live_pr_repository")
        require(pr.get("head", {}).get("ref") == member["head_ref"] and pr["head"].get("sha") == member["head_oid"] and pr.get("base", {}).get("ref") == member["base_ref"], "live_pr_vector_mismatch")
        ref = get("ref-" + str(index), base_path + "/git/ref/heads/" + quote(member["head_ref"], safe="/"))
        require(ref.get("object", {}).get("sha") == member["head_oid"], "live_git_head_mismatch")
    route = "/repositories/" + str(REPOSITORY_ID) + "/stacks/" + str(config["stack_number"]) + "/rebase"
    write_new(directory / "attempt.json", {"utc": now(), "method": "PUT", "path": route, "payload": payload, "source": metadata, "retry": "forbidden; reconcile unknown outcomes without re-dispatch"})
    result = request_once("PUT", route, payload, token, directory / "put-result.json")
    if result.get("status", 0) in range(200, 300):
        request_once("GET", route, None, token, directory / "one-status-read.json")
    print(json.dumps({"scope": PREFIX, "put_status": result.get("status"), "unknown_transport": "transport_error_class" in result, "retry_performed": False, "completion_inferred": False}))


if __name__ == "__main__":
    try:
        run(Path(sys.argv[1]), Path(sys.argv[2]))
    except (ValueError, KeyError, OSError, TypeError) as error:
        print(json.dumps({"probe_stopped": type(error).__name__, "reason": str(error) if isinstance(error, PremiseError) else type(error).__name__, "request_must_not_be_retried": True}))
        sys.exit(1)
