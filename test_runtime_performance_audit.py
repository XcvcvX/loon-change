import tempfile
import unittest
from pathlib import Path
from runtime_performance_audit import audit_plugin, render_markdown

class RuntimePerformanceAuditTests(unittest.TestCase):
    def test_counts_response_body_triggers_and_remote_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / "test.plugin"
            plugin.write_text(
                "[Script]\n"
                "http-response ^https://api.example.com/a script-path=https://raw.githubusercontent.com/org/repo/main/a.js,requires-body=true\n"
                "http-response ^https://api.example.com/b script-path=https://raw.githubusercontent.com/org/repo/main/a.js,requires-body=true\n"
                "http-request ^https://api.example.com/c script-path=https://cdn.example.com/b.js\n",
                encoding="utf-8",
            )
            (root / "sample.js").write_text(
                "const a = JSON.parse(body); const b = JSON.parse(body);", encoding="utf-8"
            )
            report = audit_plugin(plugin, root)
            summary = report["summary"]
            self.assertEqual(summary["http_response_script_triggers"], 2)
            self.assertEqual(summary["http_response_requires_body_true"], 2)
            self.assertEqual(summary["unique_remote_script_urls"], 2)
            self.assertEqual(summary["mutable_branch_remote_urls"], 1)
            self.assertEqual(summary["non_github_remote_urls"], 1)
            self.assertEqual(summary["local_js_json_parse_calls"], 2)
            self.assertEqual(summary["repeated_json_parse_expressions"], 1)
            self.assertIn("Response-body script triggers", render_markdown(report))

    def test_duplicate_trigger_group_is_reported_not_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / "test.plugin"
            plugin.write_text(
                "[Script]\n"
                "http-response ^https://api.example.com/a script-path=https://example.com/a.js\n"
                "http-response ^https://api.example.com/a script-path=https://example.com/a.js\n",
                encoding="utf-8",
            )
            report = audit_plugin(plugin, root)
            self.assertEqual(report["summary"]["duplicate_script_trigger_groups"], 1)
            self.assertEqual(len(report["duplicate_script_triggers"][0]["lines"]), 2)

    def test_commit_pinned_url_is_not_mutable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / "test.plugin"
            plugin.write_text(
                "[Script]\nhttp-response ^https://api.example.com/a script-path="
                "https://raw.githubusercontent.com/org/repo/0123456789abcdef0123456789abcdef01234567/a.js\n",
                encoding="utf-8",
            )
            report = audit_plugin(plugin, root)
            self.assertEqual(report["summary"]["mutable_branch_remote_urls"], 0)

if __name__ == "__main__":
    unittest.main()
