# Phase 9 Batch 11 — Meituan Linglong image-header scan

## Finding

The consolidated Meituan response script handles Linglong image responses before JSON parsing. For every matching image it previously called `Object.keys(headers).find(...)`, allocating a complete key array to locate at most one of four trace-header names.

## Runtime change

- Replace the per-response key-array creation and `find` callback with a short-circuiting `for...in` scan.
- Keep the same case-insensitive header-name expression and match only own enumerable properties, matching `Object.keys` semantics.
- Stop at the first matching key; keep the existing `@1sc` exception and all 204/empty-response behavior unchanged.
- Do not alter URL matching, MITM, JSON response handlers, or other Meituan paths.

## Regression coverage

The Node VM test disables `Object.keys` while executing the active Linglong image branch. It verifies a matching own header still returns the existing 204 response, an unmarked request is passed through, and an inherited header does not count.

This removes one transient key array and the `find` callback from each matching image response. No device-level CPU or battery percentage is claimed without on-device measurement.
