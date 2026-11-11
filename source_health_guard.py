#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Score upstream source health and hold unusually destructive generated updates."""
import argparse
import json
from pathlib import Path

REQUIRED_SOURCES = ("Amap", "thelongdarkorg", "aoomee", "zmjde", "GuaZiVideoAds")
SECTIONS = ("rewrite", "script", "rule")


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return value


def _source_count(record):
    return int(record.get("rule_lines", record.get("entries", 0)) or 0)


def _valid_revision(record):
    revision = record.get("commit") or record.get("upstream_commit")
    return isinstance(revision, str) and len(revision) == 40 and all(
        char in "0123456789abcdef" for char in revision.lower())


def provenance_coverage(report):
    total = missing = 0
    for section in ("rewrite", "script"):
        rows = report.get(section, [])
        if not isinstance(rows, list):
            raise ValueError("provenance %s must be a list" % section)
        total += len(rows)
        missing += sum(not row.get("sources") for row in rows)
    events = report.get("rule_events", [])
    if not isinstance(events, list):
        raise ValueError("provenance rule_events must be a list")
    included = [row for row in events if row.get("status") == "included"]
    total += len(included)
    missing += sum(not row.get("source") for row in included)
    return {"entries": total, "missing_source": missing,
            "coverage_percent": round((total - missing) * 100 / total, 4) if total else 0.0}


def _section_counts(report):
    summary = report.get("summary", {})
    return {
        "rewrite": int(summary.get("rewrite_output_entries", len(report.get("rewrite", [])))),
        "script": int(summary.get("script_output_entries", len(report.get("script", [])))),
        "rule": int(summary.get("rule_output_entries", sum(
            row.get("status") == "included" for row in report.get("rule_events", [])))),
    }


def build_health(previous_sources, current_sources, previous_provenance,
                 current_provenance, diff):
    missing = [name for name in REQUIRED_SOURCES if name not in current_sources]
    if missing:
        raise ValueError("current source report missing required sources: " + ", ".join(missing))

    coverage = provenance_coverage(current_provenance)
    source_scores = {}
    warnings, blockers = [], []
    for name in REQUIRED_SOURCES:
        current = current_sources[name]
        old = previous_sources.get(name, {})
        score, evidence = 0, {}
        # Source reports use byte counts for single-file feeds and rule_lines
        # for cloned plugin collections. Either validated measure is sufficient.
        byte_count = int(current.get("bytes", 0) or 0)
        content_count = _source_count(current)
        if content_count > 0 and (byte_count > 0 or "rule_lines" in current):
            score += 30
            evidence["content_volume"] = (
                "present_bytes_and_entries" if byte_count > 0
                else "present_rule_lines"
            )
        else:
            evidence["content_volume"] = "missing"
            blockers.append("%s has no validated content volume" % name)
        if _valid_revision(current) or name == "GuaZiVideoAds" or (
                name == "Amap" and _valid_revision(current)):
            score += 25
            evidence["revision_identity"] = "present"
        else:
            # Some single-file sources do not expose immutable commit metadata.
            score += 10
            evidence["revision_identity"] = "not_available"
            warnings.append("%s has no immutable upstream commit identity" % name)
        if name == "Amap":
            assets = current.get("assets", {})
            if len(assets) == 4 and all(
                    isinstance(item.get("sha256"), str) and len(item["sha256"]) == 64
                    for item in assets.values()):
                score += 25
                evidence["asset_integrity"] = "4 sha256 hashes"
            else:
                evidence["asset_integrity"] = "incomplete"
                blockers.append("Amap dependency hash manifest is incomplete")
        else:
            score += 25
            evidence["asset_integrity"] = "not_applicable"
        old_count, new_count = _source_count(old), _source_count(current)
        if old_count <= 0:
            score += 20
            evidence["historical_continuity"] = "baseline"
        elif new_count >= old_count * 0.40:
            score += 20
            evidence["historical_continuity"] = "within_existing_60_percent_drop_guard"
        else:
            evidence["historical_continuity"] = "severe_drop"
            blockers.append("%s source count fell from %d to %d" % (name, old_count, new_count))
        source_scores[name] = {
            "score": score, "max_score": 100, "evidence": evidence,
            "previous_count": old_count, "current_count": new_count,
        }

    if coverage["entries"] == 0 or coverage["coverage_percent"] < 99.0:
        blockers.append("provenance source attribution coverage is below 99%%")
    if coverage["missing_source"]:
        blockers.append("%d generated entries have no source attribution" % coverage["missing_source"])

    before, after = _section_counts(previous_provenance), _section_counts(current_provenance)
    changes = diff.get("summary", {})
    section_results = {}
    for section in SECTIONS:
        counts = changes.get(section, {})
        added = int(counts.get("added", 0))
        removed = int(counts.get("removed", 0))
        action_changed = int(counts.get("action_changed", 0))
        old_count, new_count = before[section], after[section]
        removed_ratio = removed / old_count if old_count else (1.0 if removed else 0.0)
        shrink_ratio = (old_count - new_count) / old_count if old_count else 0.0
        if removed_ratio > 0.25:
            blockers.append("%s removals exceed 25%% of previous output (%d/%d)" %
                            (section, removed, old_count))
        if shrink_ratio > 0.30:
            blockers.append("%s output shrank by more than 30%% (%d -> %d)" %
                            (section, old_count, new_count))
        if old_count and action_changed / old_count > 0.10:
            blockers.append("%s action changes exceed 10%% of previous output" % section)
        if old_count and added / old_count > 1.0:
            warnings.append("%s additions exceed 100%% of previous output; inspect upstream change" % section)
        section_results[section] = {
            "previous_entries": old_count, "current_entries": new_count,
            "added": added, "removed": removed, "action_changed": action_changed,
            "removed_percent": round(removed_ratio * 100, 3),
            "net_shrink_percent": round(shrink_ratio * 100, 3),
        }

    average_score = round(sum(x["score"] for x in source_scores.values()) /
                          len(source_scores), 2)
    return {
        "schema_version": 1,
        "status": "hold" if blockers else ("review" if warnings else "pass"),
        "deployment_allowed": not blockers,
        "average_source_reliability_score": average_score,
        "source_scores": source_scores,
        "provenance_coverage": coverage,
        "section_changes": section_results,
        "warnings": sorted(set(warnings)),
        "blockers": sorted(set(blockers)),
        "policy": {
            "source_count_drop_block_percent": 60,
            "section_output_shrink_block_percent": 30,
            "removed_rules_block_percent_of_previous_section": 25,
            "action_changes_block_percent_of_previous_section": 10,
            "addition_spike_warning_percent_of_previous_section": 100,
            "automatic_rule_or_mitm_edits": False,
        },
        "safety_notes": [
            "Reliability scores summarize source evidence; they do not prove runtime correctness.",
            "Large destructive diffs are held for review rather than silently published.",
            "No rule, MITM hostname, priority, or plugin output is modified by this guard.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous-sources", required=True)
    parser.add_argument("--current-sources", required=True)
    parser.add_argument("--previous-provenance", required=True)
    parser.add_argument("--current-provenance", required=True)
    parser.add_argument("--diff", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    report = build_health(
        read_json(args.previous_sources), read_json(args.current_sources),
        read_json(args.previous_provenance), read_json(args.current_provenance),
        read_json(args.diff))
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                        sort_keys=True) + "\n", encoding="utf-8")
    print("[source-health] status=%s score=%s coverage=%s%% blockers=%d warnings=%d" %
          (report["status"], report["average_source_reliability_score"],
           report["provenance_coverage"]["coverage_percent"],
           len(report["blockers"]), len(report["warnings"])))
    if not report["deployment_allowed"]:
        raise SystemExit("[source-health] HOLD: " + "; ".join(report["blockers"]))


if __name__ == "__main__":
    main()
