#!/usr/bin/env python3
"""Deterministic semantic diff for generated Loon rule provenance reports."""

import argparse
import ast
import json
import re
from collections import defaultdict


def load_report(path):
    with open(path, encoding="utf-8") as handle:
        report = json.load(handle)
    if not isinstance(report, dict):
        raise ValueError("provenance report must be a JSON object")
    if "schema_version" not in report:
        raise ValueError("unsupported provenance report: schema_version missing")
    for key in ("rewrite", "script", "rule_events", "upstream_revisions"):
        if key not in report:
            raise ValueError("provenance report missing required field: " + key)
    return report


def _rewrite_identity(record):
    try:
        key = ast.literal_eval(record.get("canonical_key", ""))
        if isinstance(key, tuple) and len(key) == 3:
            return (key[0], key[1]), repr(key[2])
    except (ValueError, SyntaxError, TypeError):
        pass
    # Unknown canonical formats are compared exactly, never guessed semantically.
    return ("raw-line", record.get("output_line", "")), "unknown"


def _split_top_level(line):
    parts, start, depth = [], 0, 0
    quote, escaped = None, False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            parts.append(line[start:index].strip())
            start = index + 1
    parts.append(line[start:].strip())
    return parts


def _rule_identity(record):
    line = record.get("output_line", "").strip()
    parts = _split_top_level(line)
    if len(parts) >= 3 and parts[-1]:
        return tuple(parts[:-1]), parts[-1]
    return ("raw-line", line), "unknown"


def _source_names(record, section):
    if section == "rule":
        return sorted({record.get("source", "unknown")})
    return sorted({item.get("source", "unknown") for item in record.get("sources", [])})


def _entry(record, section):
    return {
        "section": section,
        "line": record.get("output_line", ""),
        "sources": _source_names(record, section),
    }


def _diff_records(old_records, new_records, section, identity_fn):
    old_groups, new_groups = defaultdict(list), defaultdict(list)
    for record in old_records:
        identity, action = identity_fn(record)
        old_groups[identity].append((action, record))
    for record in new_records:
        identity, action = identity_fn(record)
        new_groups[identity].append((action, record))

    added, removed, action_changed = [], [], []
    for identity in sorted(set(old_groups) | set(new_groups), key=repr):
        before, after = old_groups.get(identity, []), new_groups.get(identity, [])
        before_by_action = defaultdict(list)
        after_by_action = defaultdict(list)
        for action, record in before:
            before_by_action[action].append(record)
        for action, record in after:
            after_by_action[action].append(record)

        # First cancel semantically identical entries, including repeated records.
        for action in set(before_by_action) & set(after_by_action):
            count = min(len(before_by_action[action]), len(after_by_action[action]))
            del before_by_action[action][:count]
            del after_by_action[action][:count]

        before_left = [(action, record) for action, rows in before_by_action.items() for record in rows]
        after_left = [(action, record) for action, rows in after_by_action.items() for record in rows]

        # Infer an action change only when the matcher has exactly one unmatched
        # old and one unmatched new form. Ambiguous multi-action matchers stay
        # as explicit additions/removals instead of being guessed.
        if len(before_left) == 1 and len(after_left) == 1:
            old_action, old_record = before_left[0]
            new_action, new_record = after_left[0]
            action_changed.append({
                "section": section,
                "before": _entry(old_record, section),
                "after": _entry(new_record, section),
            })
        else:
            removed.extend(_entry(record, section) for _, record in before_left)
            added.extend(_entry(record, section) for _, record in after_left)

    return {
        "added": sorted(added, key=lambda row: row["line"]),
        "removed": sorted(removed, key=lambda row: row["line"]),
        "action_changed": sorted(action_changed, key=lambda row: row["after"]["line"]),
    }


def build_diff(previous, current):
    sections = {
        "rewrite": _diff_records(previous["rewrite"], current["rewrite"], "rewrite", _rewrite_identity),
        "script": _diff_records(previous["script"], current["script"], "script", _rewrite_identity),
        "rule": _diff_records(
            [row for row in previous["rule_events"] if row.get("status") == "included"],
            [row for row in current["rule_events"] if row.get("status") == "included"],
            "rule", _rule_identity,
        ),
    }
    old_revisions = previous.get("upstream_revisions", {})
    new_revisions = current.get("upstream_revisions", {})
    revision_changes = []
    for source in sorted(set(old_revisions) | set(new_revisions)):
        old_value = old_revisions.get(source, {})
        new_value = new_revisions.get(source, {})
        old_commit = old_value.get("commit") or old_value.get("upstream_commit")
        new_commit = new_value.get("commit") or new_value.get("upstream_commit")
        if old_commit != new_commit:
            revision_changes.append({
                "source": source,
                "previous_commit": old_commit,
                "current_commit": new_commit,
            })

    summary = {}
    for section, result in sections.items():
        summary[section] = {
            "added": len(result["added"]),
            "removed": len(result["removed"]),
            "action_changed": len(result["action_changed"]),
        }
    summary["total_changes"] = sum(
        value for counts in summary.values() if isinstance(counts, dict)
        for value in counts.values()
    )
    return {
        "schema_version": 1,
        "comparison": "previous rule-provenance.json vs current generated rule-provenance.json",
        "previous_upstream_revisions": old_revisions,
        "current_upstream_revisions": new_revisions,
        "upstream_revision_changes": revision_changes,
        "summary": summary,
        "sections": sections,
        "safety_notes": [
            "This is a deterministic text/semantic comparison, not proof of runtime behavior.",
            "Action changes are inferred only for a unique matcher with one unmatched old and one unmatched new action.",
            "Ambiguous multi-action matchers are reported as additions/removals, not guessed as action changes.",
            "No rule, MITM hostname, or plugin output is modified by this report.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", required=True, help="previous committed provenance JSON")
    parser.add_argument("--current", required=True, help="newly generated provenance JSON")
    parser.add_argument("--out", required=True, help="output JSON path")
    args = parser.parse_args()
    previous = load_report(args.previous)
    current = load_report(args.current)
    report = build_diff(previous, current)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    print("[rule-diff] added=%d removed=%d action_changed=%d" % (
        sum(v["added"] for k, v in report["summary"].items() if isinstance(v, dict)),
        sum(v["removed"] for k, v in report["summary"].items() if isinstance(v, dict)),
        sum(v["action_changed"] for k, v in report["summary"].items() if isinstance(v, dict)),
    ))


if __name__ == "__main__":
    main()
