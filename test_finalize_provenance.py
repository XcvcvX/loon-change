import json
import tempfile
import unittest
from pathlib import Path

from finalize_provenance import reconcile


class FinalizeProvenanceTests(unittest.TestCase):
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
