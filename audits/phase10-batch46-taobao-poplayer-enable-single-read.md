# Phase 10 batch 46 — Taobao Poplayer enable single-read update

## Change
- Reuse the already-cached `poplayerEnabled` value to perform the existing false assignment directly.
- Preserve the original truthy guard and output behavior: only truthy `enable` values are set to `false`, and the response is marked modified.
- Remove the generic `setIfDifferent` helper after the cloud-video route has also been specialized, leaving no unused setter function or call sites.
- Add optimizer idempotence/fail-closed checks and a getter-count runtime regression.

## Performance rationale
- The Poplayer route previously read `obj.enable` once into `poplayerEnabled`, then read the same property again inside `setIfDifferent`.
- The direct write uses the already-known truthy value and avoids a second getter read plus one helper call.
- The generic helper becomes unnecessary after the CloudVideo setters already use direct cached-value writes.

## Validation
- Runtime getter instrumentation asserts one `enable` read and confirms the final response value is `false`.
- Existing Poplayer array cleanup and lazy serialization tests remain in place.
- No device-level CPU, battery, thermal, or latency improvement is claimed without real-device measurements.
