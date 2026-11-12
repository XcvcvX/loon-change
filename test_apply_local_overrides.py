import unittest
from apply_local_overrides import (
    apply, RULE, HELLOBIKE_RULES, HELLOBIKE_MITM_HOSTS,
    SPOTIFY_SCRIPT_TAGS, SPOTIFY_MITM_HOSTS, SPOTIFY_SOURCE,
)

BASE = """#!name=test
[Rewrite]
^https?:\\/\\/example\\.com/old reject
[Script]
response if ${url} ~= /^https?:\\/\\/example\\.com/ then reject
[MITM]
hostname = creditcard.bankcomm.cn, creditcard.bankcomm.com, creditcardapp.bankcomm.cn, creditcardapp.bankcomm.com
"""

class LocalOverrideTests(unittest.TestCase):
    def setUp(self):
        self.spotify_source = SPOTIFY_SOURCE.read_text(encoding="utf-8")

    def test_adds_rule_once_and_preserves_mitm(self):
        result = apply(BASE, self.spotify_source)
        self.assertIn(RULE, result)
        self.assertIn("creditcardapp.bankcomm.cn", result)
        self.assertEqual(apply(result, self.spotify_source), result)

    def test_adds_hellobike_rules_and_required_mitm_hosts(self):
        result = apply(BASE, self.spotify_source)
        for rule in HELLOBIKE_RULES:
            self.assertIn(rule, result)
        for host in HELLOBIKE_MITM_HOSTS:
            self.assertIn(host, result)
        self.assertEqual(apply(result, self.spotify_source), result)

    def test_spotify_extracts_only_ad_rules_and_three_response_filters(self):
        result = apply(BASE, self.spotify_source)
        self.assertIn("premium-marketing\\/upsellOffer", result)
        for tag in SPOTIFY_SCRIPT_TAGS:
            self.assertIn("tag=" + tag, result)
        for host in SPOTIFY_MITM_HOSTS:
            self.assertIn(host, result)
        self.assertIn("scripts/spotify/spot-NoSearchAd.js", result)
        self.assertIn("scripts/spotify/spot-NoHomeAd.js", result)
        self.assertIn("scripts/spotify/spot-NoScrollAd.js", result)
        self.assertNotIn("spot-proto-", result)
        self.assertNotIn("spot-gabo.js", result)
        self.assertNotIn("PROTOCOL, QUIC", result)
        self.assertNotIn("hide_ai_dj", result)
        self.assertEqual(apply(result, self.spotify_source), result)

    def test_requires_target_mitm_hosts(self):
        with self.assertRaises(ValueError):
            apply(BASE.replace("creditcard.bankcomm.com, ", ""), self.spotify_source)

    def test_rejects_missing_upstream_ad_scripts(self):
        bad = self.spotify_source.replace("tag=Spotify home ads", "tag=Other")
        with self.assertRaises(ValueError):
            apply(BASE, bad)

if __name__ == "__main__":
    unittest.main()
