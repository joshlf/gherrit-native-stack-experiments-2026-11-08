#!/usr/bin/env python3
"""Extract review-state evidence from the retained live experiment responses."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"


def response(key, label, position, resource):
    matches = sorted(EVIDENCE.glob(f"*-{key}-{label}-{position}-{resource}.stdout"))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one recorded response for {key}/{label}/{position}/{resource}")
    return matches[0], json.loads(matches[0].read_text())


def stage(key, label):
    snapshot = json.loads((EVIDENCE / f"snapshot-{key}-{label}.json").read_text())
    result = {"started": snapshot["started"], "finished": snapshot["finished"]}
    for position in ("lower", "upper"):
        path, pr = response(key, label, position, "gh-pr")
        reviews_path, reviews = response(key, label, position, "reviews")
        timeline_path, timeline = response(key, label, position, "timeline")
        result[position] = {"number": pr["number"], "head": pr["headRefOid"],
            "base": pr["baseRefName"], "review_decision": pr["reviewDecision"],
            "merge_state": pr["mergeStateStatus"],
            "reviews": [{k: r.get(k) for k in ("id", "state", "commit_id", "submitted_at")} for r in reviews],
            "dismissals": [{"created_at": e["created_at"], **e["dismissed_review"]}
                            for e in timeline if e.get("event") == "review_dismissed"],
            "source_files": [str(p.relative_to(HERE)) for p in (path, reviews_path, timeline_path)]}
    return result


spec = {
    "review-nohint": ["approved", "trunk-advanced-before-rebase", "rebased", "later-after-rebase",
                      "reapproved-before-prefix", "native-prefix", "native-prefix-later"],
    "review-hint": ["approved", "trunk-advanced-before-rebase", "rebased", "substantive",
                    "reapproved-before-prefix", "native-prefix", "native-prefix-later"],
    "review-native": ["approved", "landed-prefix", "later-after-prefix", "native-prefix-later"],
}
result = {key: {label: stage(key, label) for label in labels} for key, labels in spec.items()}
assert result["review-nohint"]["rebased"]["upper"]["review_decision"] == "REVIEW_REQUIRED"
assert result["review-hint"]["rebased"]["upper"]["review_decision"] == "APPROVED"
assert result["review-hint"]["substantive"]["upper"]["review_decision"] == "REVIEW_REQUIRED"
assert result["review-native"]["landed-prefix"]["upper"]["review_decision"] == "REVIEW_REQUIRED"
assert result["review-nohint"]["native-prefix"]["upper"]["review_decision"] == "REVIEW_REQUIRED"
assert result["review-hint"]["native-prefix"]["upper"]["review_decision"] == "APPROVED"
(EVIDENCE / "review-stage-summary.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({key: {label: values["upper"]["review_decision"] for label, values in stages.items()}
                  for key, stages in result.items()}, indent=2))
