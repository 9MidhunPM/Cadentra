# Release evidence

Status: LOCAL FOUNDATION, IDENTITY/CATALOG, FINANCIAL APIs AND REPORTING/PORTAL READS VERIFIED. FULL PRODUCT INTEGRATION CONTINUES.

## Candidate and checks

Reviewed main:48c7896c779f1b1a53aa725328f7f048cc89975f (PR10). Migration head:0002;27 tables. Dependencies are locked in backend/uv.lock and frontend/package-lock.json.

The combined main/reporting verification passes214 backend tests plus121 subtests against real PostgreSQL18.6, with committed financial races isolated in a separate test database. All104 frontend tests, typecheck/lint/build, full backend Ruff, pack validation and whitespace checks pass. Independent review found no reporting/portal merge blocker. These checks do not establish the complete financial browser journey.

Identity/catalog real Chromium checks pass for signup/login/logout/reload, password recovery, customer/product/variant/plan persistence, staff provisioning and backend403 restrictions. Gate A checks pass real cookie, CSRF, role and session behavior through the frontend proxy. Reporting owner records six separate unmocked PostgreSQL/browser cases and24 fixture cases with two platform skips. Invoice/payment API review includes three real PostgreSQL payment/cancellation races.

Local password reset -> outbox -> actual SMTP acceptance -> Mailpit API/web inbox -> reset form -> new-password sign-in passes with fictional QA data. Native Mailpit1.33.0 is checksum verified and loopback only. External SMTP is not configured or attempted, as requested. SMTP capture is not external delivery. Compose pins capture/PostgreSQL/backend versions; Docker is unavailable here, so container build/execution and public deployment remain unverified.

GitGuardian PR9 reports eight Generic Password occurrences of one finding in mocked frontend/src/features/identity/identity.test.tsx. Review confirms synthetic password inputs and mocked API requests, with no live credential in these findings. The failed external check remains visible and explained in PR9; no broad suppression was added. PR10 external security check passes.

## Integrated slices and active gates

PRs1-4 established calendar/pricing preparation and the shared backend/frontend foundation; Gate A main5b78567 passed locally. PR5 integrated the approved Graphite Mint/Sage Commerce themes. PR6 added immutable subscription billing inputs. PR7 added tax/discount/invoice/payment APIs. PR8 fixed nested invoice privacy and scoped race-fixture cleanup. PR9 integrated identity/catalog screens, local mail wiring and independent test fixtures. PR10 integrated reporting and customer-owned portal reads.

Subscription workflows/staff screens (PR11) are under review. Recurring invoice issuance/staff billing screens, delegated portal actions, actual worker catch-up/action races and the full T31 product-to-payment/report/portal journey remain open. The current worker deliberately refuses missing domain services. Fresh-clone reproduction and complete final-runtime page timing remain open. No incomplete slice is treated as a completed product.

Reporting performance evidence contains250 browser samples over ten reporting/portal views with5000 subscriptions and20000 invoices. Recorded Overview warm p95 is556.7ms and full applied-filter p95 is1333.9ms. The evidence names its older measured commit and missing staff surfaces; it is a local sequential baseline, not proof that every page of the final runtime meets two seconds. Method/raw samples: backend/tests/reporting/evidence/.

## Team workflow and cadence

Contributors: Midhun P M, Thanushree Suresh, Noel Biju and Sherin Saji. Each uses an independent clone and its verified owner SSH key. Participant gh/OAuth/token login is not required or initiated. The coordinator opens/reviews/merges PRs using existing9MidhunPM API authentication and preserves original commit authorship.

The user's SSH-only direct-merge question was checked: all three teammate accounts have repository write access and main has no active protection/rules. Local merges and normal pushes can therefore use their owner keys. This capability check does not replace the selected reviewed PR workflow.

Hourly integration checkpoints are active through Codex TUI; reviewed ready slices merge earlier when useful. The05:36UTC checkpoint included ready PRs1-8; PRs9-10 followed after verification. Next checkpoint06:36UTC. Contributors were asked to incorporate reviewed main at least hourly. No unattended scheduler is installed.

## Submission and deployment evidence

Repository/name:9MidhunPM/Cadentra, user approved. Organiser PR/tool-use clarification, portal submission receipt, selected-statement confirmation and final evaluator access remain unverified. No public server/domain was changed. Demo video and signed-out access check are not recorded. These administrative fields are not inferred from passing code tests.
