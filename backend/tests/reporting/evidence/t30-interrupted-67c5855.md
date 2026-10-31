# Interrupted native T30 run

This is historical partial evidence, not the final all-page performance gate. The raw JSON is preserved unchanged in [t30-interrupted-67c5855.json](t30-interrupted-67c5855.json), SHA256 `479af9f7c9205bf068a3d67329b5b7fbb0c41f481bec1dd24b608bf322c76aef`.

The frozen source was `67c5855139ec61d8ebaf02681daa4a7e89c1cecc`, with application/configuration files matching reviewed main `b662117`. Built assets ran through native NGINX1.30.6, a fresh loopback API in APP_ENV=test and the isolated `cadentra_performance_test` UUID namespace. The recorded peer/header/upstream adaptations do not establish public Docker/Traefik performance. The later cinematic homepage and CycleGuard release was not part of this run.

Exactly 55 of 61 planned scenarios completed: 1,375 browser samples comprising 1,100 warm and 275 fresh-context samples. Their 3,550 independent API measurements returned the expected 200 status. Every saved p50/p95/max was independently recomputed from the raw values. Source/harness hashes match the recorded Git blobs and API/server metadata; runtime_stable is true for that historical run only.

Sign-in timed out during warmup and saved zero samples. Its failure snapshot showed the form, and the API log recorded the expected unauthenticated session 401. Source inspection supports a benchmark waiter deadlock: the session provider can cancel its own 401 body while the waiter discards canceled responses and waits for another. Tracing was disabled, so the precise cancellation event was not preserved. This does not establish a form-render defect. Signup was interrupted by the user's explicit pause and also saved zero samples.

Forgot-password, reset-password, the customer overdue drilldown and chart-data cases did not run. Six cases/150 samples and the settled mobile capture remained outstanding. The raw legacy `gaps: []` is not proof of complete coverage; the replacement harness explicitly enumerates unstarted/failed cases and pending capture status. No all-page or universal under-two-seconds claim follows from these 55 cases.

All three owned processes were stopped for the pause. The fixture and private mode 0600 manifest were retained. Read-only verification after resumption confirmed its UUID inventory and 2,000,000.00 invoiced/1,500,000.00 paid/500,000.00 outstanding totals unchanged. The older immutable T31 database was not accessed.
