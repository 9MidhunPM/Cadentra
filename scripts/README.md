# Included utilities

`python3 scripts/check_pack.py` checks the planning pack, JSON syntax, document links, arithmetic, calendar fixtures and example balances using the Python standard library. It does not test a future application.

`bash scripts/preflight.sh` performs read-only local tool/Git/key-presence inspection. It reads public key fingerprints only, never private-key contents. It does not contact GitHub, register keys, create repositories, change settings, install packages or verify actual SSH authentication.

The preflight recognizes the approved HTTPS origin and legacy SSH key paths, labeling them by contributor without changing identities. There is no automatic account-switching, main-push, repository-creation or destructive cleanup script. Follow the selected feature-branch/PR workflow in the Git/integration documents.
