import unittest
from pathlib import Path
from optimize_taobao import KELEE_PATH, LOCAL, rewrite_plugin

ROOT = Path(__file__).resolve().parent
PLUGIN = ROOT / "allAdRewrite.plugin"


def fixture(guide=True, poplayer=True, extra=False):
    lines = [
        "[Script]",
        "http-response guide-response script-path=" + LOCAL + ",tag=TAOBAO,requires-body=true",
        "http-response poplayer-response script-path=" + LOCAL + ",tag=TAOBAO-2,requires-body=true",
    ]
    base = "https://raw.githubusercontent.com/ifflagged/Romeo/abc123" + KELEE_PATH
    if guide:
        lines.append('response if $' + '{url} ~= /^guide-acs/ then script("' + base + '") with tag="Taobao", requires_body=true')
    if poplayer:
        lines.append('response if $' + '{url} ~= /^poplayer/ then script("' + base + '") with tag="Taobao", requires_body=true')
    if extra:
        lines.append('response if $' + '{url} ~= /^unexpected/ then script("' + base + '") with tag="Other", requires_body=true')
    lines.extend([
        'response if $' + '{url} ~= /mdkd/ then script("https://example.invalid/pdd.js") with tag="PDD", requires_body=true',
        "[MITM]",
        "hostname = guide-acs.m.taobao.com,poplayer.template.alibaba.com",
    ])
    return "\n".join(lines) + "\n"


class TaobaoDeduplicationTests(unittest.TestCase):
    def test_exact_duplicate_handlers_are_removed_and_local_triggers_remain(self):
        result = rewrite_plugin(fixture())
        self.assertEqual(result.count(LOCAL), 2)
        self.assertNotIn(KELEE_PATH, result)
        self.assertIn("mdkd", result)
        self.assertIn("[MITM]", result)
        self.assertEqual(rewrite_plugin(result), result)

    def test_repository_snapshot_contains_only_local_optimized_handlers_after_cleanup(self):
        result = rewrite_plugin(PLUGIN.read_text(encoding="utf-8"))
        self.assertNotIn(KELEE_PATH, result)
        self.assertEqual(result.count(LOCAL), 2)
        self.assertEqual(rewrite_plugin(result), result)

    def test_missing_local_coverage_fails_closed(self):
        broken = fixture().replace(LOCAL, "https://example.invalid/taobao.js", 1)
        with self.assertRaisesRegex(ValueError, "Local optimized Taobao trigger inventory changed"):
            rewrite_plugin(broken)

    def test_partial_or_unknown_kelee_inventory_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "trigger inventory changed"):
            rewrite_plugin(fixture(poplayer=False))
        with self.assertRaisesRegex(ValueError, "Unrecognized Taobao Kelee URL matcher"):
            rewrite_plugin(fixture(extra=True))

    def test_no_duplicate_handlers_is_a_noop(self):
        original = fixture(guide=False, poplayer=False)
        self.assertEqual(rewrite_plugin(original), original)


if __name__ == "__main__":
    unittest.main()
