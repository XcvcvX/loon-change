import unittest

from mitm_policy import MITM_SKIP_REASONS, mitm_skip_host, mitm_skip_match


class MitmPolicyTests(unittest.TestCase):
    def test_exact_domains_and_subdomains_are_skipped(self):
        for domain in MITM_SKIP_REASONS:
            with self.subTest(domain=domain):
                self.assertTrue(mitm_skip_host(domain))
                self.assertTrue(mitm_skip_host("api." + domain))
                self.assertTrue(mitm_skip_host("*." + domain))

    def test_negative_prefix_and_case_are_normalized(self):
        self.assertTrue(mitm_skip_host("-API.IOS.CHAT.OPENAI.COM"))
        self.assertEqual(
            mitm_skip_match("pv.elife.icbc.com.cn")[0],
            "elife.icbc.com.cn"
        )

    def test_unrelated_hosts_are_not_skipped(self):
        self.assertFalse(mitm_skip_host("ads.example.com"))
        self.assertIsNone(mitm_skip_match("example.com"))


if __name__ == "__main__":
    unittest.main()
