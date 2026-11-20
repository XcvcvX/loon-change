# Dushu365 runtime optimization

- Upstream: `zirawell/R-Store` commit `d0f4dd305bade7cc6a38e3445a768d72aaea0e5b`
- Active response hooks: DUSHU365-2, -4, -7, -8, -9 (five total)
- Removed per-invocation Storage/Arguments initialization and inactive page branches. The active five hooks do not use those preference branches.
- Added a path allowlist before body decode/JSON.parse; non-matching requests and non-200 responses pass through.
- Fixed upstream fall-through after non-200 and JSON parse failure.
- Added changed-only serialization: already-clean payloads pass through without JSON.stringify.
- Kept Base64/UTF-8 handling and all five active mutations; retained `requires-body=true`.
- Runtime savings are structural; no device-side CPU/battery percentage is claimed.
