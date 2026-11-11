#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Classify rule-diff risk and retain a bounded source-change history."""
import argparse
import json
from collections import defaultdict
from pathlib import Path

SECTIONS = ("rewrite", "script", "rule")
MAX_HISTORY = 30


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError:
        if default is not None:
            return default
        raise
    if not isinstance(value, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return value


def _names(row, side=None):
    if side:
        row = row.get(side, {})
    names = row.get("sources", [])
    return names if isinstance(names, list) and names else ["unknown"]


def _source_score(name, health):
    record = health.get("source_scores", {}).get(name, {})
    return int(record.get("score", 0))


def _semantic_duplicate_coverage(row, provenance):
    """Return exact, provenance-backed coverage for a removed rewrite."""
    line = row.get("line", "").strip()
    if not line:
        return None
    for exclusion in provenance.get("rewrite_exclusions", []):
        if exclusion.get("status") != "excluded_semantic_duplicate":
            continue
        covered_by = exclusion.get("covered_by")
        if not isinstance(covered_by, str) or not covered_by.strip():
            continue
        source_lines = {
            value.strip() for value in (
                exclusion.get("source_raw_line"),
                exclusion.get("input_line"),
            ) if isinstance(value, str) and value.strip()
        }
        if line in source_lines:
            return {
                "covered_by": covered_by,
                "reason": exclusion.get("reason", ""),
                "source": exclusion.get("source", "unknown"),
            }
    return None


def _classify_event(kind, section, row, health, provenance=None):
    coverage = (
        _semantic_duplicate_coverage(row, provenance or {})
        if kind == "removed" and section == "rewrite" else None
    )
    if kind == "action_changed":
        level = "high"
        reason = "规则动作发生变化，可能改变请求/响应处理结果"
        names = sorted(set(_names(row, "before") + _names(row, "after")))
    elif kind == "removed" and coverage:
        level = "low"
        reason = (
            "已由来源追溯证明为同动作语义重复项；保留覆盖规则："
            + coverage["covered_by"]
        )
        names = _names(row)
    elif kind == "removed":
        level = "high"
        reason = "已有规则被移除，可能造成广告重新出现或保护范围缩小"
        names = _names(row)
    else:
        level = "medium"
        reason = "出现新规则，需要确认匹配范围、动作和误伤边界"
        names = _names(row)

    scores = {name: _source_score(name, health) for name in names}
    weak = [name for name, score in scores.items() if score and score < 70]
    if weak and level == "medium":
        level = "high"
        reason += "；来源可靠性评分偏低：" + ", ".join(weak)
    return {
        "risk": level, "change_type": kind, "section": section,
        "sources": names, "source_scores": scores, "reason": reason,
        "semantic_duplicate_coverage": coverage,
        "before": row.get("before") if kind == "action_changed" else (
            row if kind == "removed" else None),
        "after": row.get("after") if kind == "action_changed" else (
            row if kind == "added" else None),
    }


def build_risk(diff, health, source_report, previous_history, run_id="", provenance=None):
    events = []
    source_counts = defaultdict(lambda: {
        "added": 0, "removed": 0, "action_changed": 0,
    })
    section_summary = {}
    for section in SECTIONS:
        result = diff.get("sections", {}).get(section, {})
        section_summary[section] = {}
        for kind in ("added", "removed", "action_changed"):
            rows = result.get(kind, [])
            section_summary[section][kind] = len(rows)
            for row in rows:
                event = _classify_event(kind, section, row, health, provenance)
                events.append(event)
                for source in event["sources"]:
                    source_counts[source][kind] += 1

    totals = {level: sum(event["risk"] == level for event in events)
              for level in ("high", "medium", "low")}
    status = "high" if totals["high"] else ("medium" if totals["medium"] else "low")
    source_trends = {
        name: dict(counts) for name, counts in sorted(source_counts.items())
    }
    revisions = diff.get("current_upstream_revisions", {})
    snapshot = {
        "run_id": str(run_id),
        "upstream_revisions": {
            name: (record.get("commit") or record.get("upstream_commit")
                   or record.get("commit_sha") or "")
            for name, record in sorted(revisions.items())
            if isinstance(record, dict)
        },
        "change_counts": section_summary,
        "source_changes": source_trends,
        "risk_counts": totals,
    }
    history = previous_history.get("snapshots", [])
    if not isinstance(history, list):
        raise ValueError("history snapshots must be a list")
    if snapshot not in history:
        history = history + [snapshot]
    history = history[-MAX_HISTORY:]

    source_rollup = defaultdict(lambda: {
        "snapshots_seen": 0, "added": 0, "removed": 0, "action_changed": 0,
    })
    for item in history:
        for name, counts in item.get("source_changes", {}).items():
            rollup = source_rollup[name]
            rollup["snapshots_seen"] += 1
            for kind in ("added", "removed", "action_changed"):
                rollup[kind] += int(counts.get(kind, 0))
    trend = {name: dict(values) for name, values in sorted(source_rollup.items())}

    report = {
        "schema_version": 1,
        "run_id": str(run_id),
        "overall_risk": status,
        "risk_counts": totals,
        "change_counts": section_summary,
        "source_trends_last_30_snapshots": trend,
        "events": events,
        "upstream_revision_changes": diff.get("upstream_revision_changes", []),
        "source_health_status": health.get("status", "unknown"),
        "source_health_score": health.get("average_source_reliability_score"),
        "source_health_warnings": health.get("warnings", []),
        "source_health_blockers": health.get("blockers", []),
        "safety_notes": [
            "Risk labels prioritize review; they do not prove a rule is wrong.",
            "Additions are medium risk by default; unverified removals and action changes are high risk.",
            "A removed Rewrite is downgraded only when exact provenance marks it as an excluded semantic duplicate and names a retained covering matcher.",
            "No rule, MITM hostname, priority, or plugin output is modified.",
            "Source trend counts are bounded to the latest 30 successful snapshots.",
        ],
    }
    history_out = {
        "schema_version": 1,
        "retention_snapshots": MAX_HISTORY,
        "snapshots": history,
        "source_trends_last_30_snapshots": trend,
    }
    return report, history_out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diff", required=True)
    parser.add_argument("--health", required=True)
    parser.add_argument("--source-report", required=True)
    parser.add_argument("--provenance", required=True,
                        help="current provenance report for exact semantic-duplicate coverage")
    parser.add_argument("--previous-history", required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--risk-out", required=True)
    parser.add_argument("--history-out", required=True)
    args = parser.parse_args()
    diff = load_json(args.diff)
    health = load_json(args.health)
    sources = load_json(args.source_report)
    provenance = load_json(args.provenance)
    previous = load_json(args.previous_history, {"schema_version": 1, "snapshots": []})
    risk, history = build_risk(
        diff, health, sources, previous, args.run_id, provenance
    )
    Path(args.risk_out).write_text(json.dumps(risk, ensure_ascii=False, indent=2,
                                             sort_keys=True) + "\n", encoding="utf-8")
    Path(args.history_out).write_text(json.dumps(history, ensure_ascii=False, indent=2,
                                                 sort_keys=True) + "\n", encoding="utf-8")
    print("[rule-risk] overall=%s high=%d medium=%d low=%d snapshots=%d" % (
        risk["overall_risk"], risk["risk_counts"]["high"],
        risk["risk_counts"]["medium"], risk["risk_counts"]["low"],
        len(history["snapshots"])))


if __name__ == "__main__":
    main()
