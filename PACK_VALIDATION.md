# Planning pack validation

Checked on 31 October 2026 after the named-team migration. These results cover the planning assets, scripts and examples. Application Gate A remains pending.

## Checks executed

- `python3 scripts/check_pack.py`: PASS. Exactly four named contributor instruction files and handoffs, six prompts, required files, JSON syntax, relative Markdown links and fenced blocks are valid. Obsolete numbered ownership labels and old branch conventions are rejected.
- All six arithmetic fixtures pass, including 4970.16 for the canonical invoice, fixed discount caps, largest-remainder allocation and line-level tax rounding.
- Monthly, yearly, daily and weekly calendar fixtures pass. Payment balances and example invoice/dashboard totals reconcile.
- `bash -n scripts/preflight.sh`: PASS.
- `python3 -m py_compile scripts/check_pack.py`: PASS.
- `bash scripts/preflight.sh`: completed with exit 0. A SHA-256 comparison confirmed the repository-local Git configuration was unchanged. Private-key contents and environment override values were not read or printed. The script now displays named owners and public fingerprints without legacy key comments.
- Ignore-rule inspection confirms local .env files, virtual environments, frontend dependencies/builds and browser artifacts are ignored; .env.example remains publishable.

The copied pack initially failed because .env.example and .gitignore were missing. Both are restored as non-secret setup assets; the pack check now passes.

## Local environment observations

Git, SSH, Python, Node and npm are available. Docker is absent in this execution environment. Remote-head inspection over the configured HTTPS origin returned no branches during setup. These observations do not establish application runtime health or participant push permissions.

## Not performed

No application, database migration, concurrency test, real email delivery, browser workflow, performance benchmark or deployment has been implemented or verified. Pack fixture checks do not exercise future application services. Participant account/key registration, event permissions, repository submission and evaluator access remain separately unverified.

Repeat the pack checks with `python3 scripts/check_pack.py`.
