#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reconcile merge-time provenance against the final post-transform Loon plugin."""
import argparse
import collections
import json
from pathlib import Path

SECTIONS = ("Rewrite", "Script", "Rule")


def plugin_rows(path):
    rows = {name: [] for name in SECTIONS}
    section = None
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        value = raw.strip()
        if value.startswith("[") and value.endswith("]"):
            section = value[1:-1]
        elif section in rows and value and not value.startswith("#"):
            rows[section].append(value)
    return rows


def _take(records, line):
    queue = records.get(line)
    return queue.pop(0) if queue else None


def reconcile(before, after_spotify, final, provenance_path):
    base = plugin_rows(before)
    spotify = plugin_rows(after_spotify)
    output = plugin_rows(final)
    report = json.loads(Path(provenance_path).read_text(encoding="utf-8"))

    spotify_added = {
        section: collections.Counter(spotify[section]) - collections.Counter(base[section])
        for section in SECTIONS
    }
    final_added = {
        section: collections.Counter(output[section]) - collections.Counter(spotify[section])
        for section in SECTIONS
    }

    for section, key in (("Rewrite", "rewrite"), ("Script", "script")):
        existing = collections.defaultdict(list)
        for row in report.get(key, []):
            existing[row.get("output_line", "")].append(row)
        reconciled = []
        for line in output[section]:
            row = _take(existing, line)
            if row is None:
                stage = "spotify_integration" if spotify_added[section][line] > 0 else "local_overrides"
                if stage == "spotify_integration":
                    spotify_added[section][line] -= 1
                else:
                    final_added[section][line] -= 1
                source = "Spotify" if stage == "spotify_integration" else "local_overrides"
                row = {
                    "output_line": line,
                    "sources": [{
                        "source": source,
                        "source_file": "sources/spotify/Spotify.lpx" if source == "Spotify" else "apply_local_overrides.py",
                        "transform_stage": stage,
                    }],
                    "provenance_kind": "post_merge_transform",
                }
            reconciled.append(row)
        report[key] = reconciled

    existing_events = collections.defaultdict(list)
    retained_events = []
    for event in report.get("rule_events", []):
        if event.get("status") == "included":
            existing_events[event.get("output_line", "")].append(event)
        else:
            retained_events.append(event)
    for line in output["Rule"]:
        event = _take(existing_events, line)
        if event is None:
            stage = "spotify_integration" if spotify_added["Rule"][line] > 0 else "local_overrides"
            if stage == "spotify_integration":
                spotify_added["Rule"][line] -= 1
            else:
                final_added["Rule"][line] -= 1
            source = "Spotify" if stage == "spotify_integration" else "local_overrides"
            event = {
                "status": "included",
                "output_line": line,
                "source": source,
                "source_file": "sources/spotify/Spotify.lpx" if source == "Spotify" else "apply_local_overrides.py",
                "transform_stage": stage,
            }
        retained_events.append(event)
    report["rule_events"] = retained_events

    report["summary"] = report.get("summary", {})
    report["summary"].update({
        "rewrite_output_entries": len(output["Rewrite"]),
        "script_output_entries": len(output["Script"]),
        "rule_output_entries": len(output["Rule"]),
        "post_transform_reconciled": True,
    })
    report["post_transform_reconciliation"] = {
        "final_plugin": str(final),
        "stages": ["merge", "spotify_integration", "local_overrides"],
        "removed_stale_entries": True,
        "unmatched_final_entries": 0,
        "note": "Entries introduced after merge are attributed to the transformation stage, not falsely assigned to an upstream feed.",
    }
    Path(provenance_path).write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True, help="plugin immediately after merge")
    parser.add_argument("--after-spotify", required=True, help="plugin after Spotify integration")
    parser.add_argument("--final", required=True, help="final plugin after local overrides")
    parser.add_argument("--provenance", required=True, help="merge-time provenance JSON to reconcile")
    args = parser.parse_args()
    report = reconcile(args.before, args.after_spotify, args.final, args.provenance)
    coverage_rows = sum(len(report.get(key, [])) for key in ("rewrite", "script"))
    coverage_rows += sum(x.get("status") == "included" for x in report.get("rule_events", []))
    print("[provenance-final] final entries=%d, rewrite=%d, script=%d, rule=%d" % (
        coverage_rows, report["summary"]["rewrite_output_entries"],
        report["summary"]["script_output_entries"], report["summary"]["rule_output_entries"]))


if __name__ == "__main__":
    main()
