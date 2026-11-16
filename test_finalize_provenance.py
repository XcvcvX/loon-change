import json
import tempfile
import unittest
from pathlib import Path

from finalize_provenance import reconcile


class FinalizeProvenanceTests(unittest.TestCase):

    def test_records_only_exact_verified_kugou_and_jin10_coverage(self):
        kugou_old = r"^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/adp\\/ad\\/ reject-dict"
        kugou_new = kugou_old.replace("^https:", "^https?:")
        jin_old = r"^https:\\/\\/jad-api\\.jin10\\.com\\/ad reject-dict"
        jin_request = r"request if ${url} ~= /^https?:\\/\\/jad-api\\.jin10\\.com\\/ad/ then reject(404)"
        broad_list_v = r"^https?:\\/\\/gzacshow\\.kugou\\.com\\/mfanxing-home\\/cdn\\/room\\/index\\/list_v reject-dict"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            before, after, final, provenance = [root / name for name in (
                "before.plugin", "after.plugin", "final.plugin", "provenance.json"
            )]
            after.write_text(
                "[Rewrite]\\n" + "\\n".join([kugou_old, jin_old, broad_list_v]) + "\\n",
                encoding="utf-8",
            )
            before.write_text(after.read_text(encoding="utf-8"), encoding="utf-8")
            final.write_text(
                "[Rewrite]\\n" + "\\n".join([kugou_new, jin_request, broad_list_v]) + "\\n",
                encoding="utf-8",
            )
            provenance.write_text(json.dumps({"rewrite": [], "script": [], "rule_events": []}),
                                  encoding="utf-8")
            report = reconcile(before, after, final, provenance)
            exclusions = {x["source_raw_line"]: x for x in report["rewrite_exclusions"]}
            self.assertEqual(exclusions[kugou_old]["status"], "excluded_semantic_duplicate")
            self.assertEqual(exclusions[kugou_old]["covered_by"], kugou_new)
            self.assertEqual(exclusions[jin_old]["status"], "excluded_unreachable_response")
            self.assertEqual(exclusions[jin_old]["covered_by"], jin_request)
            self.assertNotIn(broad_list_v, exclusions)

    def test_fails_when_verified_covering_matcher_is_missing(self):
        removed = r"^https:\\/\\/gateway(retry)?\\.kugou\\.com\\/adp\\/ad\\/ reject-dict"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            before, after, final, provenance = [root / name for name in (
                "before.plugin", "after.plugin", "final.plugin", "provenance.json"
            )]
            after.write_text("[Rewrite]\\n" + removed + "\\n", encoding="utf-8")
            before.write_text(after.read_text(encoding="utf-8"), encoding="utf-8")
            final.write_text("[Rewrite]\\n", encoding="utf-8")
            provenance.write_text(json.dumps({"rewrite": [], "script": [], "rule_events": []}),
                                  encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "verified Rewrite coverage missing"):
                reconcile(before, after, final, provenance)

    def test_reconciles_spotify_and_local_overrides_and_drops_stale_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            before = root / "before.plugin"
            after = root / "spotify.plugin"
            final = root / "final.plugin"
            provenance = root / "provenance.json"
            before.write_text(
                "[Rewrite]\nbase-rule reject\nstale-rule reject\n"
                "[Script]\nbase-script script-path=https://cdn.test/base.js\n"
                "[Rule]\nDOMAIN,base.test,REJECT\n",
                encoding="utf-8",
            )
            after.write_text(
                "[Rewrite]\nbase-rule reject\nspotify-rule reject\n"
                "[Script]\nbase-script script-path=https://cdn.test/base.js\n"
                "spotify-script script-path=https://cdn.test/spotify.js\n"
                "[Rule]\nDOMAIN,base.test,REJECT\nDOMAIN,spotify.test,REJECT\n",
                encoding="utf-8",
            )
            final.write_text(
                "[Rewrite]\nbase-rule reject\nspotify-rule reject\nlocal-rule reject\n"
                "[Script]\nbase-script script-path=https://cdn.test/base.js\n"
                "spotify-script script-path=https://cdn.test/spotify.js\n"
                "[Rule]\nDOMAIN,base.test,REJECT\nDOMAIN,spotify.test,REJECT\nDOMAIN,local.test,REJECT\n",
                encoding="utf-8",
            )
            provenance.write_text(json.dumps({
                "schema_version": 1,
                "summary": {},
                "rewrite": [
                    {"output_line": "base-rule reject", "sources": [{"source": "base"}]},
                    {"output_line": "stale-rule reject", "sources": [{"source": "base"}]},
                ],
                "script": [
                    {"output_line": "base-script script-path=https://cdn.test/base.js",
                     "sources": [{"source": "base"}]},
                ],
                "rule_events": [
                    {"status": "included", "output_line": "DOMAIN,base.test,REJECT", "source": "filter"},
                    {"status": "duplicate", "output_line": "DOMAIN,dup.test,REJECT", "source": "filter"},
                ],
            }), encoding="utf-8")

            report = reconcile(before, after, final, provenance)
            self.assertEqual([x["output_line"] for x in report["rewrite"]],
                             ["base-rule reject", "spotify-rule reject", "local-rule reject"])
            self.assertEqual(report["rewrite"][1]["sources"][0]["source"], "Spotify")
            self.assertEqual(report["rewrite"][2]["sources"][0]["source"], "local_overrides")
            self.assertEqual(report["script"][1]["sources"][0]["source"], "Spotify")
            included = [x for x in report["rule_events"] if x.get("status") == "included"]
            self.assertEqual({x["output_line"] for x in included}, {
                "DOMAIN,base.test,REJECT", "DOMAIN,spotify.test,REJECT", "DOMAIN,local.test,REJECT"
            })
            self.assertTrue(report["post_transform_reconciliation"]["removed_stale_entries"])
            self.assertEqual(report["summary"]["rewrite_output_entries"], 3)


if __name__ == "__main__":
    unittest.main()
