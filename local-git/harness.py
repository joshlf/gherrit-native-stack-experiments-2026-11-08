#!/usr/bin/env python3
import argparse
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import traceback


IDENTITY = {"name": "Josh Liebow-Feeser", "email": "hello@joshlf.com"}
TRAILER = "Agent-authored-by: AI agent acting on joshlf's behalf"
ZERO = "0" * 40
ROOT = Path(__file__).resolve().parent
ENV = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null",
           GIT_TERMINAL_PROMPT="0", LC_ALL="C")


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".new")
    with temporary.open("w") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    directory = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def read_json(path):
    return json.loads(Path(path).read_text())


def command(argv, cwd, transcript, input_text=None, env=None, allowed=(0,)):
    result = subprocess.run(argv, cwd=str(cwd), input=input_text, text=True,
                            capture_output=True, env=env or ENV)
    entry = {"argv": list(argv), "cwd": str(cwd), "stdin": input_text,
             "returncode": result.returncode, "stdout": result.stdout,
             "stderr": result.stderr}
    with Path(transcript).open("a") as stream:
        stream.write(json.dumps(entry, sort_keys=True) + "\n")
    if result.returncode not in allowed:
        raise RuntimeError(json.dumps(entry, indent=2))
    return result


@dataclasses.dataclass(frozen=True)
class RevisionRange:
    base: str
    tip: str


@dataclasses.dataclass(frozen=True)
class Layer:
    change_id: str
    incorporated: RevisionRange
    local: RevisionRange
    hosted: RevisionRange


class MergeConflict(Exception):
    pass


class FixtureGit:
    def __init__(self, root, initialize=True):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.transcript = self.root.parent / (self.root.name + "-commands.jsonl")
        self.count = 0
        self.commits = {}
        self.merges = []
        if initialize:
            self.git("init", "--initial-branch=source")
            for key, value in [("user.name", IDENTITY["name"]),
                               ("user.email", IDENTITY["email"]),
                               ("core.hooksPath", "/dev/null"),
                               ("commit.gpgsign", "false"),
                               ("tag.gpgsign", "false")]:
                self.git("config", "--local", key, value)

    def git(self, *args, input_text=None, env=None, allowed=(0,)):
        return command(["git"] + list(args), self.root, self.transcript,
                       input_text=input_text, env=env, allowed=allowed)

    def tree(self, files):
        index = self.root.parent / (self.root.name + "-scratch-index")
        if index.exists():
            index.unlink()
        environment = dict(ENV, GIT_INDEX_FILE=str(index))
        self.git("read-tree", "--empty", env=environment)
        for path, content in sorted(files.items()):
            blob = self.git("hash-object", "-w", "--stdin", input_text=content).stdout.strip()
            self.git("update-index", "--add", "--cacheinfo", "100644", blob, path,
                     env=environment)
        return self.git("write-tree", env=environment).stdout.strip()

    def commit(self, label, files, parent=None, message=None):
        return self.commit_tree(label, self.tree(files), parent, message)

    def commit_tree(self, label, tree, parent=None, message=None):
        self.count += 1
        text = message or (label.replace("_", " ") + "\n\n" + TRAILER + "\n")
        environment = dict(ENV, GIT_AUTHOR_DATE="2000-01-01T00:%02d:%02d+0000" %
                           (self.count // 60, self.count % 60),
                           GIT_COMMITTER_DATE="2000-01-01T00:%02d:%02d+0000" %
                           (self.count // 60, self.count % 60))
        args = ["commit-tree", tree]
        if parent:
            args += ["-p", parent]
        commit = self.git(*args, input_text=text, env=environment).stdout.strip()
        self.git("update-ref", "refs/fixtures/" + label, commit)
        self.commits[label] = commit
        return commit

    def files(self, commit):
        paths = self.git("ls-tree", "-r", "--name-only", commit).stdout.splitlines()
        return {path: self.git("show", commit + ":" + path).stdout for path in paths}

    def message(self, commit):
        raw = self.git("cat-file", "commit", commit).stdout
        return raw.split("\n\n", 1)[1]

    def range_snapshot(self, revision):
        return {"base": revision.base, "tip": revision.tip,
                "base_tree": self.git("rev-parse", revision.base + "^{tree}").stdout.strip(),
                "tip_tree": self.git("rev-parse", revision.tip + "^{tree}").stdout.strip(),
                "files": self.files(revision.tip), "message": self.message(revision.tip),
                "patch": self.git("diff", "--no-ext-diff", "--binary",
                                  revision.base, revision.tip).stdout,
                "signature": self.git("show", "-s", "--format=%G?", revision.tip).stdout.strip()}

    def merge(self, label, base, local, other):
        result = self.git("merge-tree", "--write-tree", "--merge-base=" + base,
                          local, other, allowed=(0, 1))
        tree = result.stdout.splitlines()[0]
        evidence = {"label": label, "base": base, "local": local, "other": other,
                    "tree": tree, "returncode": result.returncode,
                    "stdout": result.stdout, "stderr": result.stderr}
        self.merges.append(evidence)
        conflict_artifact = self.root.parent / (label + "-merge.json")
        atomic_json(conflict_artifact, evidence)
        if result.returncode:
            self.git("update-ref", "refs/conflict-trees/" + label, tree)
            raise MergeConflict(label)
        return self.commit_tree(label, tree, local)

    def normalize(self, label, revision, comparison_parent):
        return self.merge(label, revision.base, comparison_parent, revision.tip)

    def integrate(self, label, layers, output_parent):
        result = []
        for layer in layers:
            prefix = label + "_" + layer.change_id
            ni = self.normalize(prefix + "_I", layer.incorporated, layer.hosted.base)
            nl = self.normalize(prefix + "_L", layer.local, layer.hosted.base)
            integrated = self.merge(prefix + "_integrated", ni, nl, layer.hosted.tip)
            replay = self.merge(prefix + "_replay", layer.hosted.base,
                                output_parent, integrated)
            output = self.commit_tree(prefix + "_accepted",
                                      self.git("rev-parse", replay + "^{tree}").stdout.strip(),
                                      output_parent, self.message(layer.local.tip))
            result.append({"change_id": layer.change_id,
                           "incorporated": dataclasses.asdict(layer.hosted),
                           "accepted_local": {"base": output_parent, "tip": output},
                           "normalized_I": ni, "normalized_L": nl,
                           "integrated": integrated})
            output_parent = output
        return result

    def save_inventory(self, target):
        atomic_json(target, {"refs": self.git("show-ref").stdout,
                             "commits": {label: self.range_snapshot(RevisionRange(
                                 self.git("rev-parse", commit + "^", allowed=(0, 128)).stdout.strip()
                                 if self.git("rev-list", "--parents", "-n", "1", commit).stdout.count(" ")
                                 else commit, commit))
                                         for label, commit in self.commits.items()},
                             "merges": self.merges})


class Suite:
    def __init__(self, run):
        self.run = run
        self.checks = []
        self.details = {}

    def equal(self, label, actual, expected):
        passed = actual == expected
        self.checks.append({"label": label, "passed": passed,
                            "actual": actual, "expected": expected})
        if not passed:
            raise AssertionError(label + ": " + repr(actual) + " != " + repr(expected))

    def truth(self, label, actual):
        self.equal(label, bool(actual), True)

    def conflict(self, label, action):
        try:
            action()
        except MergeConflict as conflict:
            self.equal(label, str(conflict), label)
        else:
            self.equal(label, "no conflict", label)


def changed(files, **updates):
    return dict(files, **updates)


def source_snapshot(repo):
    index = repo.root / ".git" / "index"
    workfiles = {}
    for path in repo.root.rglob("*"):
        if ".git" not in path.parts and path.is_file():
            workfiles[str(path.relative_to(repo.root))] = path.read_bytes().hex()
    return {"source": repo.git("rev-parse", "refs/heads/source").stdout.strip(),
            "index": index.read_bytes().hex(), "workfiles": workfiles,
            "status": repo.git("status", "--porcelain=v1").stdout}


def integration_cases(suite):
    repo = FixtureGit(suite.run / "integration-repo")
    base_files = {"a.txt": "0\n", "b.txt": "0\n", "x.txt": "0\n",
                  "y.txt": "0\n", "q.txt": "0\n", "r.txt": "0\n",
                  "trunk.txt": "old trunk\n", "api.txt": "base api\n",
                  "consumer.txt": "base consumer\n"}
    p = repo.commit("P", base_files)
    ia = repo.commit("I_A", changed(base_files, **{"a.txt": "1\n"}), p)
    ib = repo.commit("I_B", changed(repo.files(ia), **{"b.txt": "1\n"}), ia)
    la = repo.commit("L_A", changed(repo.files(ia), **{"y.txt": "1\n"}), p)
    lb = repo.commit("L_B", changed(repo.files(la), **{"b.txt": "1\n", "r.txt": "1\n"}), la)
    ha1 = repo.commit("H1_A", changed(repo.files(ia), **{"x.txt": "1\n"}), p)
    hb1 = repo.commit("H1_B", changed(repo.files(ha1), **{"b.txt": "1\n", "q.txt": "1\n"}), ha1)
    first = repo.integrate("first", [Layer("A", RevisionRange(p, ia), RevisionRange(p, la), RevisionRange(p, ha1)),
                                      Layer("B", RevisionRange(ia, ib), RevisionRange(la, lb), RevisionRange(ha1, hb1))], p)
    a1, b1 = [row["accepted_local"]["tip"] for row in first]
    suite.equal("first A retains pending y", repo.files(a1)["y.txt"], "1\n")
    suite.equal("first B owns exactly b q r", repo.git("diff", "--name-only", a1, b1).stdout.splitlines(),
                ["b.txt", "q.txt", "r.txt"])
    suite.equal("A message preserved exactly", repo.message(a1), repo.message(la))
    suite.equal("B message preserved exactly", repo.message(b1), repo.message(lb))
    suite.equal("fixture signing choice is explicit unsigned", repo.git("show", "-s", "--format=%G?", b1).stdout.strip(), "N")
    ha2 = repo.commit("H2_A", changed(repo.files(ha1), **{"x.txt": "2\n"}), p)
    hb2 = repo.commit("H2_B", changed(repo.files(ha2), **{"b.txt": "1\n", "q.txt": "2\n"}), ha2)
    second = repo.integrate("second", [Layer("A", RevisionRange(p, ha1), RevisionRange(p, a1), RevisionRange(p, ha2)),
                                       Layer("B", RevisionRange(ha1, hb1), RevisionRange(a1, b1), RevisionRange(ha2, hb2))], p)
    a2, b2 = [row["accepted_local"]["tip"] for row in second]
    suite.equal("second import x2", repo.files(a2)["x.txt"], "2\n")
    suite.equal("second import pending y survives", repo.files(a2)["y.txt"], "1\n")
    suite.equal("second B owns exactly b q r", repo.git("diff", "--name-only", a2, b2).stdout.splitlines(),
                ["b.txt", "q.txt", "r.txt"])
    suite.equal("second B retains local r and hosted q", {k: repo.files(b2)[k] for k in ["q.txt", "r.txt"]},
                {"q.txt": "2\n", "r.txt": "1\n"})
    suite.conflict("wrong_submitted_baseline_A_integrated", lambda: repo.integrate("wrong_submitted_baseline", [
        Layer("A", RevisionRange(p, ia), RevisionRange(p, a1), RevisionRange(p, ha2))], p))
    wrong_checkpoint = repo.integrate("wrong_accepted_baseline", [
        Layer("A", RevisionRange(p, a1), RevisionRange(p, a1), RevisionRange(p, ha2))], p)
    suite.equal("negative accepted-local baseline loses y", repo.files(wrong_checkpoint[0]["accepted_local"]["tip"])["y.txt"], "0\n")
    la3 = repo.commit("later_lower_only_A", changed(repo.files(a2), **{"y.txt": "2\n"}), p)
    lb3 = repo.commit("later_lower_only_B", changed(repo.files(la3), **{"b.txt": "1\n", "q.txt": "2\n", "r.txt": "1\n"}), la3,
                      repo.message(b2))
    third = repo.integrate("lower_only", [Layer("A", RevisionRange(p, ha2), RevisionRange(p, la3), RevisionRange(p, ha2)),
                                          Layer("B", RevisionRange(ha2, hb2), RevisionRange(la3, lb3), RevisionRange(ha2, hb2))], p)
    a3, b3 = [row["accepted_local"]["tip"] for row in third]
    suite.equal("lower-only amendment remains in A", repo.files(a3)["y.txt"], "2\n")
    suite.equal("lower-only amendment survives B", repo.files(b3)["y.txt"], "2\n")
    suite.equal("lower-only change does not enter B patch", repo.git("diff", "--name-only", a3, b3).stdout.splitlines(),
                ["b.txt", "q.txt", "r.txt"])
    wrong_b = third[1]["integrated"]
    suite.equal("negative skip-replay resets lower y", repo.files(wrong_b)["y.txt"], "0\n")
    suite.truth("negative skip-replay puts y deletion in B patch", "y.txt" in repo.git("diff", "--name-only", a3, wrong_b).stdout.splitlines())
    repeated = repo.integrate("unchanged_import", [Layer("A", RevisionRange(p, ha2), RevisionRange(p, a3), RevisionRange(p, ha2)),
                                                 Layer("B", RevisionRange(ha2, hb2), RevisionRange(a3, b3), RevisionRange(ha2, hb2))], p)
    suite.equal("unchanged import final tree", repo.files(repeated[-1]["accepted_local"]["tip"]), repo.files(b3))
    multi_b_first = repo.commit("hosted_multi_B_first", changed(repo.files(ha2), **{"b.txt": "1\n"}), ha2)
    multi_b_tip = repo.commit("hosted_multi_B_tip", changed(repo.files(multi_b_first), **{"q.txt": "3\n"}), multi_b_first)
    multi_result = repo.integrate("hosted_multi_range", [
        Layer("A", RevisionRange(p, ha2), RevisionRange(p, a3), RevisionRange(p, ha2)),
        Layer("B", RevisionRange(ha2, hb2), RevisionRange(a3, b3), RevisionRange(ha2, multi_b_tip))], p)
    multi_a, multi_b = [row["accepted_local"]["tip"] for row in multi_result]
    suite.equal("hosted B range contains two commits", int(repo.git("rev-list", "--count", ha2 + ".." + multi_b_tip).stdout), 2)
    suite.equal("multi-commit hosted range preserves local r", repo.files(multi_b)["r.txt"], "1\n")
    suite.equal("multi-commit hosted range imports q3", repo.files(multi_b)["q.txt"], "3\n")
    suite.equal("multi-commit hosted range preserves B ownership", repo.git("diff", "--name-only", multi_a, multi_b).stdout.splitlines(),
                ["b.txt", "q.txt", "r.txt"])
    captured = RevisionRange(p, a3)
    later = repo.commit("local_after_captured_submit", changed(repo.files(a3), **{"r.txt": "later pending edit\n"}), p)
    completed = {"authored_submission": dataclasses.asdict(captured),
                 "incorporated": dataclasses.asdict(captured),
                 "accepted_local": dataclasses.asdict(captured)}
    suite.equal("confirmed submission keeps captured tip", completed["authored_submission"]["tip"], a3)
    suite.equal("later edit remains pending against captured export", repo.git("diff", "--name-only", a3, later).stdout.splitlines(), ["r.txt"])
    suite.equal("negative live-wholesale checkpoint hides later edit", repo.git("diff", "--name-only", later, later).stdout, "")
    suite.details["captured_submission"] = {"completed_checkpoint": completed, "later_local": later,
                                             "pending_patch": repo.git("diff", a3, later).stdout}
    new_parent = repo.commit("new_trunk_parent", changed(base_files, **{"trunk.txt": "new trunk\n"}), p)
    moved_a = repo.commit("rebased_H_A", changed(repo.files(new_parent), **{"a.txt": "1\n", "x.txt": "2\n"}), new_parent,
                          repo.message(ha2))
    drifted = repo.integrate("parent_drift", [Layer("A", RevisionRange(p, ha2), RevisionRange(p, a3), RevisionRange(new_parent, moved_a))], new_parent)
    drift_tip = drifted[0]["accepted_local"]["tip"]
    suite.equal("parent drift preserves local y", repo.files(drift_tip)["y.txt"], "2\n")
    suite.equal("parent drift uses new trunk", repo.files(drift_tip)["trunk.txt"], "new trunk\n")
    suite.equal("tip-to-tip comparison includes unrelated trunk", repo.git("diff", "--name-only", ha2, moved_a).stdout.splitlines(), ["trunk.txt"])
    suite.equal("old exact patch excludes trunk", repo.git("diff", "--name-only", p, ha2).stdout.splitlines(), ["a.txt", "x.txt"])
    suite.equal("new exact patch excludes trunk", repo.git("diff", "--name-only", new_parent, moved_a).stdout.splitlines(), ["a.txt", "x.txt"])
    suite.equal("range-diff recognizes unchanged authored patch", repo.git("range-diff", "--no-color", p + ".." + ha2, new_parent + ".." + moved_a).stdout.count(" = "), 1)
    reset_local = repo.commit("deliberate_reset_local_A", repo.files(ha2), p)
    reset = repo.integrate("explicit_reset", [Layer("A", RevisionRange(p, ha2), RevisionRange(p, reset_local), RevisionRange(p, ha2))], p)
    suite.equal("explicit accepted reset can remove pending y", repo.files(reset[0]["accepted_local"]["tip"])["y.txt"], "0\n")
    conflicting_local = repo.commit("conflicting_local_A", changed(repo.files(ia), **{"x.txt": "local conflict\n"}), p)
    suite.conflict("same_line_conflict_A_integrated", lambda: repo.integrate("same_line_conflict", [
        Layer("A", RevisionRange(p, ia), RevisionRange(p, conflicting_local), RevisionRange(p, ha1))], p))
    upstream = repo.commit("normalization_upstream_conflict", changed(base_files, **{"a.txt": "upstream conflict\n"}), p)
    suite.conflict("normalization_conflict", lambda: repo.normalize("normalization_conflict", RevisionRange(p, ia), upstream))
    replay_local = repo.commit("replay_local", changed(base_files, **{"b.txt": "local lower conflict\n"}), p)
    suite.conflict("replay_conflict", lambda: repo.merge("replay_conflict", p, replay_local, ib))
    suite.details["integration"] = {"first": first, "second": second, "lower_only": third,
                                     "unchanged_import": repeated, "parent_drift": drifted,
                                     "accepted_reset": reset, "hosted_multi_commit_range": multi_result}
    repo.save_inventory(suite.run / "integration-inventory.json")
    return repo, {"base": p, "captured": la, "result": a1, "source_advance": later,
                  "incorporated": RevisionRange(p, ha1), "base_files": base_files}


def landed_followup_case(suite, repo, inputs):
    p = inputs["base"]
    a = repo.commit("published_A", changed(repo.files(p), **{"api.txt": "base api\nold field\n"}), p)
    b = repo.commit("published_B", changed(repo.files(a), **{"consumer.txt": "use old field\n"}), a)
    local_a = repo.commit("amended_A", changed(repo.files(a), **{"api.txt": "base api\nold field\nnew field\n"}), p)
    local_b = repo.commit("amended_B", changed(repo.files(local_a), **{"consumer.txt": "use old field and new field\n"}), local_a)
    squashed = repo.commit("squash_landed_A", repo.files(a), p, "Land reviewed A\n\n" + TRAILER + "\n")
    hosted_b = repo.commit("native_rebased_B", changed(repo.files(squashed), **{"consumer.txt": "use old field\n"}), squashed,
                           repo.message(b))
    followup_tree = repo.merge("landed_A_pending_delta", a, squashed, local_a)
    followup = repo.commit_tree("new_ID_F", repo.git("rev-parse", followup_tree + "^{tree}").stdout.strip(), squashed,
                                "Add the pending API field\n\nChange-Id: F\n\n" + TRAILER + "\n")
    out = repo.integrate("landed_suffix", [Layer("B", RevisionRange(a, b), RevisionRange(local_a, local_b), RevisionRange(squashed, hosted_b))], followup)
    tip = out[0]["accepted_local"]["tip"]
    suite.truth("squashed landing has different SHA from published A", squashed != a)
    suite.equal("squash landing is not recognized by old A ancestry", repo.git("merge-base", "--is-ancestor", a, squashed, allowed=(1,)).returncode, 1)
    suite.equal("landed amendment F owns only api", repo.git("diff", "--name-only", squashed, followup).stdout.splitlines(), ["api.txt"])
    suite.equal("B after F owns only consumer", repo.git("diff", "--name-only", followup, tip).stdout.splitlines(), ["consumer.txt"])
    suite.equal("B has F as its direct parent", repo.git("rev-parse", tip + "^").stdout.strip(), followup)
    suite.equal("F is before dependent B", ["F", out[0]["change_id"]], ["F", "B"])
    suite.equal("B message remains the local authored message", repo.message(tip), repo.message(local_b))
    suite.truth("B's parent supplies required new field", "new field" in repo.files(followup)["api.txt"])
    suite.truth("negative append-only B parent lacks required field", "new field" not in repo.files(squashed)["api.txt"])
    suite.details["landed_followup"] = {"lifecycle_input": {"A": "merged", "B": "open"},
        "bindings": {"A": {"canonical_pr": "fixture-pr-A", "terminal": True},
                     "B": {"canonical_pr": "fixture-pr-B"}, "F": {"new_id": True}},
        "published": {"A": {"base": p, "tip": a}, "B": {"base": a, "tip": b}},
        "local": {"A": {"base": p, "tip": local_a}, "B": {"base": local_a, "tip": local_b}},
        "landed": squashed, "hosted_B": {"base": squashed, "tip": hosted_b},
        "continuation_order": [{"id": "F", "base": squashed, "tip": followup},
                               {"id": "B", "base": followup, "tip": tip}],
        "provider_structural_effects": "not attempted"}


def shared_file_case(suite):
    repo = FixtureGit(suite.run / "shared-file-repo")
    lines = ["context %02d\n" % i for i in range(45)]
    for position in [0, 10, 20, 30, 40]:
        lines[position] = "field%02d=0\n" % position
    def contents(values):
        result = list(lines)
        for position, value in values.items():
            result[position] = "field%02d=%s\n" % (position, value)
        return {"shared.txt": "".join(result)}
    p = repo.commit("shared_P", contents({}))
    ia = repo.commit("shared_I_A", contents({0: 1}), p)
    ib = repo.commit("shared_I_B", contents({0: 1, 20: 1}), ia)
    la = repo.commit("shared_L_A", contents({0: 1, 10: 1}), p)
    lb = repo.commit("shared_L_B", contents({0: 1, 10: 1, 20: 2}), la)
    ha = repo.commit("shared_H_A", contents({0: 1, 30: 1}), p)
    hb = repo.commit("shared_H_B", contents({0: 1, 20: 1, 30: 1, 40: 1}), ha)
    first = repo.integrate("shared_first", [
        Layer("A", RevisionRange(p, ia), RevisionRange(p, la), RevisionRange(p, ha)),
        Layer("B", RevisionRange(ia, ib), RevisionRange(la, lb), RevisionRange(ha, hb))], p)
    a1, b1 = [row["accepted_local"]["tip"] for row in first]
    suite.equal("shared-file first exact A tree", repo.files(a1), contents({0: 1, 10: 1, 30: 1}))
    suite.equal("shared-file first exact B tree", repo.files(b1), contents({0: 1, 10: 1, 20: 2, 30: 1, 40: 1}))
    later_a = repo.commit("shared_later_A", contents({0: 1, 10: 2, 30: 1}), p)
    later_b = repo.commit("shared_later_B", contents({0: 1, 10: 2, 20: 2, 30: 1, 40: 1}), later_a)
    second = repo.integrate("shared_lower_only", [
        Layer("A", RevisionRange(p, ha), RevisionRange(p, later_a), RevisionRange(p, ha)),
        Layer("B", RevisionRange(ha, hb), RevisionRange(later_a, later_b), RevisionRange(ha, hb))], p)
    a2, b2 = [row["accepted_local"]["tip"] for row in second]
    suite.equal("shared-file lower-only exact A tree", repo.files(a2), contents({0: 1, 10: 2, 30: 1}))
    suite.equal("shared-file lower-only exact B tree", repo.files(b2), contents({0: 1, 10: 2, 20: 2, 30: 1, 40: 1}))
    b_patch = repo.git("diff", "--unified=0", a2, b2).stdout
    suite.truth("shared-file B patch excludes lower amendment hunk", "field10" not in b_patch)
    suite.truth("shared-file B patch contains B's own amended hunk", "+field20=2" in b_patch)
    suite.details["shared_file"] = {"first": first, "second": second, "second_B_patch": b_patch}
    repo.save_inventory(suite.run / "shared-file-inventory.json")


def ordinary_git_cases(suite):
    repo = FixtureGit(suite.run / "ordinary-git-repo")
    base_files = {"a.txt": "0\n", "x.txt": "0\n", "y.txt": "0\n", "trunk.txt": "old trunk\n"}
    p = repo.commit("ordinary_P", base_files)
    message = "Introduce A\n\nChange-Id: A\n\n" + TRAILER + "\n"
    a = repo.commit("ordinary_A", changed(base_files, **{"a.txt": "1\n"}), p, message)
    newp = repo.commit("ordinary_new_trunk", changed(base_files, **{"trunk.txt": "new trunk\n"}), p)
    repo.git("update-ref", "refs/heads/source", a)
    repo.git("switch", "source")
    (repo.root / "y.txt").write_text("1\n")
    repo.git("add", "y.txt")
    repo.git("commit", "--amend", "--no-edit")
    amended = repo.git("rev-parse", "HEAD").stdout.strip()
    repo.git("update-ref", "refs/fixtures/ordinary_amended_A", amended)
    repo.commits["ordinary_amended_A"] = amended
    suite.truth("ordinary amend changes commit identity", amended != a)
    suite.equal("ordinary amend preserves message and ID", repo.message(amended), message)
    repo.git("rebase", "--onto", newp, p, "source")
    rebased = repo.git("rev-parse", "HEAD").stdout.strip()
    repo.git("update-ref", "refs/fixtures/ordinary_rebased_A", rebased)
    repo.commits["ordinary_rebased_A"] = rebased
    suite.truth("ordinary rebase changes commit identity", rebased != amended)
    suite.equal("ordinary rebase preserves message and ID", repo.message(rebased), message)
    hosted = repo.commit("ordinary_hosted_A", changed(repo.files(newp), **{"a.txt": "1\n", "x.txt": "1\n"}), newp, message)
    imported = repo.integrate("ordinary_import", [Layer("A", RevisionRange(p, a), RevisionRange(newp, rebased), RevisionRange(newp, hosted))], newp)
    imported_tip = imported[0]["accepted_local"]["tip"]
    suite.equal("ordinary amend and rebase import exact tree", repo.files(imported_tip),
                changed(base_files, **{"a.txt": "1\n", "x.txt": "1\n", "y.txt": "1\n", "trunk.txt": "new trunk\n"}))
    repo.git("revert", "--no-commit", rebased)
    repo.git("commit", "--file=-", input_text="Revert the local A change\n\nChange-Id: R\n\n" + TRAILER + "\n")
    reverted = repo.git("rev-parse", "HEAD").stdout.strip()
    repo.git("update-ref", "refs/fixtures/ordinary_revert_R", reverted)
    repo.commits["ordinary_revert_R"] = reverted
    suite.equal("ordinary revert is retained as new R after A", repo.git("rev-parse", reverted + "^").stdout.strip(), rebased)
    suite.equal("ordinary revert restores new-trunk tree", repo.files(reverted), repo.files(newp))
    repo.git("reset", "--hard", a)
    suite.equal("ordinary deliberate reset chooses old A", repo.git("rev-parse", "HEAD").stdout.strip(), a)
    suite.equal("ordinary reset does not delete retained R", repo.git("rev-parse", "refs/fixtures/ordinary_revert_R").stdout.strip(), reverted)
    suite.equal("reset differences from accepted input remain visible", repo.git("diff", "--name-only", imported_tip, a).stdout.splitlines(),
                ["trunk.txt", "x.txt", "y.txt"])
    suite.details["ordinary_git"] = {"base": p, "original": a, "amended": amended,
        "new_parent": newp, "rebased": rebased, "hosted": hosted,
        "accepted": imported, "revert_new_id_R": reverted, "reset_to": a,
        "mapping_limit": "The fixture explicitly supplies its one-commit A mapping and treats revert R as a new change. It does not implement automatic mapping or authorize remote withdrawal on reset."}
    repo.save_inventory(suite.run / "ordinary-git-inventory.json")


def continuation_case(suite, repo, inputs):
    repo.git("update-ref", "refs/heads/source", inputs["captured"])
    repo.git("switch", "source")
    (repo.root / "x.txt").write_text("staged author edit\n")
    repo.git("add", "x.txt")
    (repo.root / "y.txt").write_text("unstaged author edit\n")
    (repo.root / "untracked.txt").write_text("untracked author work\n")
    captured = inputs["captured"]
    old_checkpoint = {"source_tip": captured, "kind": "old source checkpoint"}
    atomic_json(suite.run / "old-source-checkpoint.json", old_checkpoint)
    source_advance = repo.commit("source_advanced_during_sync", changed(repo.files(captured), **{"trunk.txt": "concurrent committed source\n"}), captured)
    repo.git("update-ref", "refs/heads/source", source_advance, captured)
    before = source_snapshot(repo)
    intent = {"state": "planned", "source_ref": "refs/heads/source", "captured_source": captured,
              "result": inputs["result"], "continuation": "refs/heads/continuation",
              "incorporated": dataclasses.asdict(inputs["incorporated"])}
    atomic_json(suite.run / "continuation-intent.json", intent)
    repo.git("update-ref", intent["continuation"], intent["result"], ZERO)
    checkpoint = dict(intent, state="accepted")
    atomic_json(suite.run / "continuation-checkpoint.json", checkpoint)
    after = source_snapshot(repo)
    suite.equal("continuation acceptance preserves all source workspace bytes", after, before)
    suite.equal("source U retained after acceptance", after["source"], source_advance)
    suite.equal("continuation R reflects captured T result", repo.git("rev-parse", intent["continuation"]).stdout.strip(), inputs["result"])
    suite.equal("old source checkpoint remains unchanged", read_json(suite.run / "old-source-checkpoint.json"), old_checkpoint)
    absence = repo.git("update-ref", intent["continuation"], source_advance, ZERO, allowed=(128,))
    suite.truth("fresh-ref absence guard rejects existing ref", "reference already exists" in absence.stderr)
    suite.equal("occupied continuation is not overwritten", repo.git("rev-parse", intent["continuation"]).stdout.strip(), inputs["result"])
    blocked = repo.git("switch", "continuation", allowed=(1,))
    suite.truth("ordinary Git protects dirty/staged checkout", "would be overwritten" in blocked.stderr)
    suite.equal("blocked selection preserves source workspace", source_snapshot(repo), before)
    negative_root = suite.run / "negative-reset-repo"
    shutil.copytree(repo.root, negative_root)
    negative = FixtureGit(negative_root, initialize=False)
    negative_before = source_snapshot(negative)
    negative.git("reset", "--hard", inputs["result"])
    negative_after = source_snapshot(negative)
    suite.truth("negative reset displaces source ref", negative_before["source"] != negative_after["source"])
    suite.truth("negative reset displaces staged index", negative_before["index"] != negative_after["index"])
    suite.truth("negative reset discards dirty tracked file", negative_before["workfiles"]["y.txt"] != negative_after["workfiles"]["y.txt"])
    suite.equal("negative reset still leaves untracked file", negative_after["workfiles"]["untracked.txt"], negative_before["workfiles"]["untracked.txt"])
    suite.details["continuation"] = {"captured_T": captured, "advanced_U": source_advance,
                                      "accepted_R": inputs["result"], "before": before, "after": after,
                                      "blocked_checkout": blocked.stderr,
                                      "occupied_ref_rejection": absence.stderr,
                                      "negative_reset_before": negative_before,
                                      "negative_reset_after": negative_after}


PREFIXES = ["before_planned", "planned", "dispatched", "provider_applied",
            "acknowledged", "ref_created", "checkpoint_installed", "complete"]


def pause_at(job, prefix, selected):
    if prefix == selected:
        atomic_json(Path(job["directory"]) / "paused.json", {"prefix": prefix, "pid": os.getpid()})
        while True:
            signal.pause()


def transfer_authority(directory):
    required = ["bindings.json", "accepted-checkpoint.json", "pending-operations.json"]
    missing = [name for name in required if not (directory / name).exists()]
    unresolved = []
    if not missing:
        for record in read_json(directory / "pending-operations.json")["operations"]:
            operation_path = directory / record["record"]
            if not operation_path.exists():
                missing.append(record["record"])
            else:
                operation = read_json(operation_path)
                if operation["state"] != "complete":
                    unresolved.append({"id": operation["id"], "state": operation["state"]})
    return {"evidence_complete": not missing, "mutation_authority": not missing and not unresolved,
            "missing": missing, "unresolved": unresolved,
            "status": "recovery_required" if missing else "blocked_pending_operation" if unresolved else "eligible_for_scope_checks"}


def worker(job_path, selected=None, reconcile=False):
    job = read_json(job_path)
    directory = Path(job["directory"])
    op_path = directory / "operation.json"
    checkpoint_path = directory / "continuation-checkpoint.json"
    repo = FixtureGit(job["repo"], initialize=False)
    pause_at(job, "before_planned", selected)
    if not op_path.exists():
        operation = {"id": job["operation_id"], "state": "planned",
                     "captured_source": job["captured_source"], "result": job["result"],
                     "incorporated": job["incorporated"], "continuation": job["continuation"],
                     "effect": {"kind": "local-provider-emulator-write", "scope": ["fixture-head-A", "fixture-pr-A"],
                                "request": {"operation_id": job["operation_id"], "desired_head": job["result"]}}}
        atomic_json(op_path, operation)
    operation = read_json(op_path)
    pause_at(job, "planned", selected)
    if operation["state"] == "planned":
        operation["state"] = "indeterminate"
        atomic_json(op_path, operation)
        pause_at(job, "dispatched", selected)
        provider = read_json(job["provider"])
        provider["requests"].append(operation["effect"]["request"])
        provider["head"] = operation["result"]
        provider["receipt"] = {"operation_id": operation["id"], "head": operation["result"]}
        atomic_json(job["provider"], provider)
        pause_at(job, "provider_applied", selected)
        operation["state"] = "acknowledged"
        operation["receipt"] = provider["receipt"]
        atomic_json(op_path, operation)
    elif operation["state"] == "indeterminate":
        provider = read_json(job["provider"])
        expected = {"operation_id": operation["id"], "head": operation["result"]}
        if not reconcile or provider.get("receipt") != expected:
            atomic_json(directory / "recovery-result.json", {"status": "blocked_unknown_no_resend",
                "operation_id": operation["id"], "provider_request_count": len(provider["requests"]),
                "reason": "Absence or matching desired head alone does not authorize another dispatch."})
            return 3
        operation["state"] = "acknowledged"
        operation["receipt"] = expected
        operation["reconciliation"] = "Explicit receipt attribution in the sole-writer local emulator only"
        atomic_json(op_path, operation)
    pause_at(job, "acknowledged", selected)
    if operation["state"] == "acknowledged":
        existing = repo.git("show-ref", "--verify", "--hash", operation["continuation"], allowed=(0, 128)).stdout.strip()
        if not existing:
            repo.git("update-ref", operation["continuation"], operation["result"], ZERO)
        elif existing != operation["result"]:
            atomic_json(directory / "recovery-result.json", {"status": "blocked_ref_collision", "actual": existing})
            return 4
        pause_at(job, "ref_created", selected)
        checkpoint = {"operation_id": operation["id"], "continuation": operation["continuation"],
                      "result": operation["result"], "captured_source": operation["captured_source"],
                      "incorporated": operation["incorporated"]}
        if checkpoint_path.exists() and read_json(checkpoint_path) != checkpoint:
            return 5
        atomic_json(checkpoint_path, checkpoint)
        pause_at(job, "checkpoint_installed", selected)
        operation["state"] = "complete"
        atomic_json(op_path, operation)
    pause_at(job, "complete", selected)
    atomic_json(directory / "recovery-result.json", {"status": "complete", "operation_id": operation["id"]})
    return 0


def spawn_and_kill(job_path, prefix):
    job = read_json(job_path)
    marker = Path(job["directory"]) / "paused.json"
    out = Path(job["directory"]) / "child.stdout"
    err = Path(job["directory"]) / "child.stderr"
    with out.open("w") as stdout, err.open("w") as stderr:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "worker",
                                  str(job_path), "--pause", prefix], stdout=stdout,
                                 stderr=stderr, env=ENV)
        deadline = time.monotonic() + 15
        while not marker.exists():
            if child.poll() is not None:
                raise RuntimeError("Child exited before pause: " + err.read_text())
            if time.monotonic() > deadline:
                child.kill()
                child.wait()
                raise RuntimeError("Child did not reach " + prefix)
            time.sleep(0.01)
        child.kill()
        returncode = child.wait()
    evidence = {"prefix": prefix, "pid": child.pid, "returncode": returncode,
                "signal": "SIGKILL", "marker": read_json(marker)}
    atomic_json(Path(job["directory"]) / "interruption.json", evidence)
    return evidence


def recovery_cases(suite, source_repo, inputs):
    rows = []
    for prefix in PREFIXES:
        directory = suite.run / "faults" / prefix
        directory.mkdir(parents=True)
        repo_path = directory / "repo"
        shutil.copytree(source_repo.root, repo_path)
        job = {"directory": str(directory), "repo": str(repo_path),
               "operation_id": "fixture-operation-" + prefix,
               "captured_source": inputs["captured"], "result": inputs["result"],
               "incorporated": dataclasses.asdict(inputs["incorporated"]),
               "continuation": "refs/heads/recovery-" + prefix,
               "provider": str(directory / "provider.json")}
        atomic_json(directory / "job.json", job)
        atomic_json(directory / "provider.json", {"requests": [], "head": inputs["incorporated"].tip})
        atomic_json(directory / "old-source-checkpoint.json", {"captured_source": inputs["captured"]})
        atomic_json(directory / "bindings.json", {"A": {"canonical_pr": "fixture-pr-A", "head": "fixture-head-A"}})
        atomic_json(directory / "accepted-checkpoint.json", {
            "source": {"tip": inputs["captured"]}, "incorporated": dataclasses.asdict(inputs["incorporated"]),
            "accepted_local": {"base": inputs["base"], "tip": inputs["result"]}})
        atomic_json(directory / "pending-operations.json", {
            "operations": [{"id": job["operation_id"], "record": "operation.json"}]})
        interruption = spawn_and_kill(directory / "job.json", prefix)
        suite.equal("real child killed at " + prefix, interruption["returncode"], -signal.SIGKILL)
        before = {"operation": read_json(directory / "operation.json") if (directory / "operation.json").exists() else None,
                  "provider": read_json(directory / "provider.json"),
                  "checkpoint": read_json(directory / "continuation-checkpoint.json") if (directory / "continuation-checkpoint.json").exists() else None}
        atomic_json(directory / "before-recovery.json", before)
        recovery = command([sys.executable, str(Path(__file__).resolve()), "worker", str(directory / "job.json")],
                           directory, directory / "recovery-commands.jsonl", allowed=(0, 3))
        unknown = prefix in ["dispatched", "provider_applied"]
        suite.equal("recovery outcome at " + prefix, recovery.returncode, 3 if unknown else 0)
        provider_after = read_json(directory / "provider.json")
        expected_requests = 0 if prefix == "dispatched" else 1
        suite.equal("no duplicate effect at " + prefix, len(provider_after["requests"]), expected_requests)
        suite.equal("old checkpoint not advanced at " + prefix, read_json(directory / "old-source-checkpoint.json"),
                    {"captured_source": inputs["captured"]})
        if not unknown:
            suite.equal("complete exact continuation checkpoint at " + prefix,
                        read_json(directory / "continuation-checkpoint.json")["result"], inputs["result"])
        else:
            suite.equal("unknown does not install checkpoint at " + prefix, (directory / "continuation-checkpoint.json").exists(), False)
        rows.append({"prefix": prefix, "interruption": interruption, "before": before,
                     "after_operation": read_json(directory / "operation.json"),
                     "after_provider": provider_after, "recovery_returncode": recovery.returncode})
    suite.details["fault_prefixes"] = rows
    pending = suite.run / "faults" / "provider_applied"
    full = suite.run / "replacement-full-transfer"
    shutil.copytree(pending, full)
    full_job = read_json(full / "job.json")
    full_job.update(directory=str(full), repo=str(full / "repo"))
    atomic_json(full / "job.json", full_job)
    full_admission = transfer_authority(full)
    atomic_json(full / "transfer-admission.json", full_admission)
    suite.equal("full transfer retains required evidence", full_admission["evidence_complete"], True)
    suite.equal("full transfer retains actual accepted local result", read_json(full / "accepted-checkpoint.json")["accepted_local"]["tip"], inputs["result"])
    suite.equal("full transfer withholds overlapping mutation authority", full_admission["mutation_authority"], False)
    suite.equal("full transfer identifies the indeterminate operation", full_admission["unresolved"],
                [{"id": "fixture-operation-provider_applied", "state": "indeterminate"}])
    before_requests = len(read_json(full_job["provider"])["requests"])
    full_recovery = command([sys.executable, str(Path(__file__).resolve()), "worker", str(full / "job.json")],
                            full, full / "transfer-commands.jsonl", allowed=(3,))
    suite.equal("full transfer retains unknown-not-resend guard", full_recovery.returncode, 3)
    suite.equal("full transfer sends no second request", len(read_json(full_job["provider"])["requests"]), before_requests)
    reconciled = command([sys.executable, str(Path(__file__).resolve()), "worker", str(full / "job.json"), "--reconcile-receipt"],
                         full, full / "transfer-commands.jsonl")
    suite.equal("explicit uniquely attributable emulator receipt permits recovery", reconciled.returncode, 0)
    suite.equal("receipt reconciliation does not resend", len(read_json(full_job["provider"])["requests"]), 1)
    bindings_only = suite.run / "replacement-bindings-only"
    bindings_only.mkdir()
    atomic_json(bindings_only / "bindings.json", {"A": {"canonical_pr": "fixture-pr-A", "head": "fixture-head-A"}})
    admission = transfer_authority(bindings_only)
    atomic_json(bindings_only / "admission-result.json", admission)
    suite.equal("bindings-only transfer rejects mutation authority", admission["mutation_authority"], False)
    suite.equal("bindings-only transfer identifies missing checkpoint and pending evidence", admission["missing"],
                ["accepted-checkpoint.json", "pending-operations.json"])
    suite.details["transfer"] = {"full_transfer": str(full), "bindings_only_admission": admission,
                                  "full_transfer_admission": full_admission,
                                  "external_emulator_store": full_job["provider"],
                                  "limits": "The transfer checklist is cooperative prototype policy, not a fence against edited/deleted records."}


def run_suite():
    run = ROOT / "runs" / (time.strftime("%Y%m%dT%H%M%S") + "-" + str(time.time_ns()))
    run.mkdir(parents=True)
    shutil.copyfile(Path(__file__).resolve(), run / "harness.py")
    suite = Suite(run)
    atomic_json(run / "environment.json", {"python": sys.version, "identity": IDENTITY,
        "git": subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.strip(),
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "claim": "Local real-Git fixture and local-provider-emulator policy evidence only"})
    status = "passed"
    try:
        repo, inputs = integration_cases(suite)
        shared_file_case(suite)
        ordinary_git_cases(suite)
        landed_followup_case(suite, repo, inputs)
        continuation_case(suite, repo, inputs)
        recovery_cases(suite, repo, inputs)
        repo.save_inventory(run / "final-inventory.json")
        fsck = repo.git("fsck", "--full", "--no-reflogs")
        suite.equal("real Git object integrity", fsck.returncode, 0)
    except Exception:
        status = "failed"
        (run / "failure.txt").write_text(traceback.format_exc())
    result = {"status": status, "run": str(run), "check_count": len(suite.checks),
              "passed_count": sum(row["passed"] for row in suite.checks),
              "checks": suite.checks, "details": suite.details}
    atomic_json(run / "results.json", result)
    atomic_json(ROOT / "latest-run.json", {"run": str(run), "status": status})
    print(json.dumps({"status": status, "run": str(run), "checks": len(suite.checks)}))
    return 0 if status == "passed" else 1


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode", required=True)
    subparsers.add_parser("run")
    child = subparsers.add_parser("worker")
    child.add_argument("job")
    child.add_argument("--pause", choices=PREFIXES)
    child.add_argument("--reconcile-receipt", action="store_true")
    args = parser.parse_args()
    if args.mode == "worker":
        return worker(args.job, args.pause, args.reconcile_receipt)
    return run_suite()


if __name__ == "__main__":
    sys.exit(main())
