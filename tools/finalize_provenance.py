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



# Exact, reviewed local-override removals. These entries are not generic regex
# inference: every retained matcher is checked against the final plugin output.
VERIFIED_LOCAL_REWRITE_COVERAGE = {
    "^https:\\/\\/ep\\.kugou\\.com\\/v\\d\\/album_shop\\/get_entrance_info reject-dict": {
        "status": "excluded_semantic_duplicate",
        "covered_by": "^https?:\\/\\/ep\\.kugou\\.com\\/v\\d\\/album_shop\\/get_entrance_info reject-dict",
        "coverage_kind": "strict_https_subset",
        "reason": "HTTPS-only matcher is a strict subset of the retained HTTP+HTTPS matcher with the same reject-dict action and path",
    },
    "^https:\\/\\/fx\\.service\\.kugou\\.com\\/mfx-kugoulive\\/ad\\/ reject-dict": {
        "status": "excluded_semantic_duplicate",
        "covered_by": "^https?:\\/\\/fx\\.service\\.kugou\\.com\\/mfx-kugoulive\\/ad\\/ reject-dict",
        "coverage_kind": "strict_https_subset",
        "reason": "HTTPS-only matcher is a strict subset of the retained HTTP+HTTPS matcher with the same reject-dict action and path",
    },
    "^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/adp\\/ad\\/ reject-dict": {
        "status": "excluded_semantic_duplicate",
        "covered_by": "^https?:\\/\\/gateway(retry)?\\.kugou\\.com\\/adp\\/ad\\/ reject-dict",
        "coverage_kind": "strict_https_subset",
        "reason": "HTTPS-only matcher is a strict subset of the retained HTTP+HTTPS matcher with the same reject-dict action and path",
    },
    "^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/adp\\/bubble\\/v\\d\\/song_play reject-dict": {
        "status": "excluded_semantic_duplicate",
        "covered_by": "^https?:\\/\\/gateway(retry)?\\.kugou\\.com\\/adp\\/bubble\\/v\\d\\/song_play reject-dict",
        "coverage_kind": "strict_https_subset",
        "reason": "HTTPS-only matcher is a strict subset of the retained HTTP+HTTPS matcher with the same reject-dict action and path",
    },
    "^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/ads\\.gateway\\/ reject-dict": {
        "status": "excluded_semantic_duplicate",
        "covered_by": "^https?:\\/\\/gateway(retry)?\\.kugou\\.com\\/ads\\.gateway\\/ reject-dict",
        "coverage_kind": "strict_https_subset",
        "reason": "HTTPS-only matcher is a strict subset of the retained HTTP+HTTPS matcher with the same reject-dict action and path",
    },
    "^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/mstc\\/musicsymbol\\/v\\d\\/system\\/profile reject-dict": {
        "status": "excluded_semantic_duplicate",
        "covered_by": "^https?:\\/\\/gateway(retry)?\\.kugou\\.com\\/mstc\\/musicsymbol\\/v\\d\\/system\\/profile reject-dict",
        "coverage_kind": "strict_https_subset",
        "reason": "HTTPS-only matcher is a strict subset of the retained HTTP+HTTPS matcher with the same reject-dict action and path",
    },
    "^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/ocean\\/v\\d\\/sound\\/banner reject-dict": {
        "status": "excluded_semantic_duplicate",
        "covered_by": "^https?:\\/\\/gateway(retry)?\\.kugou\\.com\\/ocean\\/v\\d\\/sound\\/banner reject-dict",
        "coverage_kind": "strict_https_subset",
        "reason": "HTTPS-only matcher is a strict subset of the retained HTTP+HTTPS matcher with the same reject-dict action and path",
    },
    "^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/r\\/v\\d\\/general\\/putin\\/midad reject-dict": {
        "status": "excluded_semantic_duplicate",
        "covered_by": "^https?:\\/\\/gateway(retry)?\\.kugou\\.com\\/r\\/v\\d\\/general\\/putin\\/midad reject-dict",
        "coverage_kind": "strict_https_subset",
        "reason": "HTTPS-only matcher is a strict subset of the retained HTTP+HTTPS matcher with the same reject-dict action and path",
    },
    "^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/searchnofocus\\/v\\d\\/search_no_focus_word reject-dict": {
        "status": "excluded_semantic_duplicate",
        "covered_by": "^https?:\\/\\/gateway(retry)?\\.kugou\\.com\\/searchnofocus\\/v\\d\\/search_no_focus_word reject-dict",
        "coverage_kind": "strict_https_subset",
        "reason": "HTTPS-only matcher is a strict subset of the retained HTTP+HTTPS matcher with the same reject-dict action and path",
    },
    "^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/singerdiscuss\\/v\\d\\/entrance\\/comment reject-dict": {
        "status": "excluded_semantic_duplicate",
        "covered_by": "^https?:\\/\\/gateway(retry)?\\.kugou\\.com\\/singerdiscuss\\/v\\d\\/entrance\\/comment reject-dict",
        "coverage_kind": "strict_https_subset",
        "reason": "HTTPS-only matcher is a strict subset of the retained HTTP+HTTPS matcher with the same reject-dict action and path",
    },
    "^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/v\\d\\/feeds\\/follow_feed_fallback reject-dict": {
        "status": "excluded_semantic_duplicate",
        "covered_by": "^https?:\\/\\/gateway(retry)?\\.kugou\\.com\\/v\\d\\/feeds\\/follow_feed_fallback reject-dict",
        "coverage_kind": "strict_https_subset",
        "reason": "HTTPS-only matcher is a strict subset of the retained HTTP+HTTPS matcher with the same reject-dict action and path",
    },
    "^https:\\/\\/gzacshow\\.kugou\\.com\\/mfx-rt-show\\/cdn\\/mo\\/show\\/headline reject-dict": {
        "status": "excluded_semantic_duplicate",
        "covered_by": "^https?:\\/\\/gzacshow\\.kugou\\.com\\/mfx-rt-show\\/cdn\\/mo\\/show\\/headline reject-dict",
        "coverage_kind": "strict_https_subset",
        "reason": "HTTPS-only matcher is a strict subset of the retained HTTP+HTTPS matcher with the same reject-dict action and path",
    },
    "^https:\\/\\/hwstore\\.kugou\\.com\\/v\\d\\/get_store_data reject-dict": {
        "status": "excluded_semantic_duplicate",
        "covered_by": "^https?:\\/\\/hwstore\\.kugou\\.com\\/v\\d\\/get_store_data reject-dict",
        "coverage_kind": "strict_https_subset",
        "reason": "HTTPS-only matcher is a strict subset of the retained HTTP+HTTPS matcher with the same reject-dict action and path",
    },
    "^https:\\/\\/m1fxgroup\\.kugou\\.com\\/fxsing\\/yqc\\/alongInfo\\/getUserAlongInfo reject-dict": {
        "status": "excluded_semantic_duplicate",
        "covered_by": "^https?:\\/\\/m1fxgroup\\.kugou\\.com\\/fxsing\\/yqc\\/alongInfo\\/getUserAlongInfo reject-dict",
        "coverage_kind": "strict_https_subset",
        "reason": "HTTPS-only matcher is a strict subset of the retained HTTP+HTTPS matcher with the same reject-dict action and path",
    },
    "^https:\\/\\/jad-api\\.jin10\\.com\\/ad reject-dict": {
        "status": "excluded_unreachable_response",
        "covered_by": "request if ${url} ~= /^https?:\\/\\/jad-api\\.jin10\\.com\\/ad/ then reject(404)",
        "coverage_kind": "request_terminates_before_response",
        "reason": "The exact request-phase reject(404) terminates this URL before a response-phase Rewrite can run",
    },
}


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


    # Record exact local removals only when their retained coverage is present.
    # The broad legacy list_v matcher is intentionally not listed: list_v2 does
    # not prove coverage for every possible list_v version.
    removed_rewrites = collections.Counter(spotify["Rewrite"]) - collections.Counter(output["Rewrite"])
    exclusions = report.setdefault("rewrite_exclusions", [])
    known_exclusions = {
        item.get("source_raw_line") for item in exclusions
        if isinstance(item, dict)
    }
    for removed_line, metadata in VERIFIED_LOCAL_REWRITE_COVERAGE.items():
        if removed_rewrites[removed_line] <= 0 or removed_line in known_exclusions:
            continue
        if metadata["covered_by"] not in output["Rewrite"]:
            raise ValueError(
                "verified Rewrite coverage missing from final plugin: " + metadata["covered_by"]
            )
        exclusions.append({
            **metadata,
            "source_raw_line": removed_line,
            "input_line": removed_line,
            "source": "local_overrides",
            "source_file": "apply_local_overrides.py",
            "transform_stage": "local_overrides",
        })

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
