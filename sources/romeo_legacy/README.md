# Romeo migration compatibility snapshots

These files are retained because Romeo does not currently provide a complete
behavior-equivalent module for the corresponding AOOMEE entry. They are local,
pinned snapshots from AOOMEE commit
`370a13085514ccca924f43d13c6d3acfa5671dbe`; the build no longer clones or
fetches the AOOMEE repository.

| Snapshot | Reason |
|---|---|
| `51cg.plugin` | AOOMEE-specific 51 吃瓜 web cleanup |
| `91porn.plugin` | AOOMEE-specific 91Porn web cleanup |
| `cmcc.plugin` | User-supplied China Mobile splash rule; no Romeo equivalent |
| `huazhu.plugin` | Exact two-endpoint variant not found in Romeo |
| `chelaile2.plugin` | App-version-specific 7.6.6 flow-position rules; kept alongside Romeo's CaoXiaoMann module |
| `qunar-legacy.plugin` | Legacy Loon syntax variant retained for compatibility |
| `youtube-zh.lpx` | Full Chinese enhancement variant has no complete Romeo equivalent |

The two scripts formerly fetched from AOOMEE are vendored under
`scripts/romeo_legacy/` and the plugin references point to this repository.
The snapshots are intentionally not auto-updated; their origin and filenames
are recorded in `source-report.json` during the next production sync.
