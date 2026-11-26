# Legacy runtime snapshots used by tests

These files are retained as regression fixtures, not as production Loon script assets.

- `didi-ads.js`: exercises the previous Didi response handler, including legacy routes that are not all represented by the current consolidated runtime.
- `jd-welcome.js`: preserves the optional legacy JD welcome-page filter so consolidation tests can compare endpoint coverage and safe parsing.
- `pupu-splash.js`: preserves the prior Pupu response handler for parse/serialize and route-coverage regression checks; the production plugin uses native response rules.

The authoritative live behavior is determined by `allAdRewrite.plugin`, the active local scripts under `scripts/`, and the current CI tests. Do not wire these fixture files back into production triggers. When the tests are rewritten to exercise the active implementation directly, the corresponding legacy fixture may be retired.
