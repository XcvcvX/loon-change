# Phase 10 batch 37 — Didi root response-data reference cache

## Change
- Read the parsed response's root `data` property once and reuse the reference across scene-list, homepage-core, info-list, and user-center branches.
- Preserve all nested filtering predicates, stable array order, lazy serialization, and route dispatch.
- Add a getter-count runtime regression to prove the root `data` accessor is evaluated once per supported response.
- Extend the upstream optimizer with marker, idempotence, and fail-closed checks.

## Validation
- Node VM tests verify a homepage response still retains only the existing nav allowlists and reads the root `data` property once.
- No device-level CPU, battery, thermal, or latency improvement is claimed without real-device measurements.
