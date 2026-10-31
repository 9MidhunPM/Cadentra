# Independent workspaces and verified Git identities

## Current checkpoint

The repository already exists at https://github.com/9MidhunPM/Cadentra and the current independent checkout has that HTTPS origin. During planning, read-only remote inspection returned no branches. The user approved one initial planning-pack commit/push to main, followed by feature branches and PRs for all application work. No new remote repository or global configuration changes are needed.

Midhun P M keeps the existing default identity and authentication. The three additional keys below were reported in the historical setup; registration, authenticated accounts and repository access have not been verified. These are legacy technical filenames, not team member labels:

| Team member | Existing technical key path |
|---|---|
| Thanushree Suresh | ~/.ssh/gh-agent2 |
| Noel Biju | ~/.ssh/gh-agent3 |
| Sherin Saji | ~/.ssh/gh-agent4 |

Keep existing clone folder names and key files. Never regenerate keys or set another person's commit identity as part of renaming the documentation.

## Read-only inspection first

Run `bash scripts/preflight.sh` in each independent clone. It inspects tools, effective author name/email, remote transport, branch, key presence and potentially overriding environment-variable names. It does not register keys, contact GitHub, change configuration or prove account authentication. Midhun P M's existing HTTPS origin is supported; the preflight recognizes HTTPS and does not require a switch to SSH.

Verify the actual participant's GitHub username and commit email, including an exact GitHub-provided noreply address where appropriate. Do not derive an email from a username. Author metadata and push authentication are separate. The account holder configures their verified identity locally if needed; assistants preserve existing configuration until its ownership is established. Never modify global Git/SSH/GitHub CLI settings.

## Existing clone startup

Use your own clone. A clean, reviewed main baseline is required before creating a feature branch:

```sh
git status --short --branch
git remote -v
git fetch origin
git switch -c feature/subscription-workflows origin/main
```

The example is for Thanushree Suresh. Midhun P M uses feature/platform-foundation, Noel Biju uses feature/billing-payments and Sherin Saji uses feature/frontend-foundation initially. Subsequent branches describe features. If a branch exists, inspect/continue it; do not reset, overwrite work or recreate a clone blindly.

If someone needs a new clone, use their existing authorized transport to clone this same repository into a separate workspace, then follow the startup procedure. A clone is not a second application scaffold. Keep the participant's database, ports and environment separate.

## Optional legacy SSH account checks

Only when an account holder elects to use an existing extra key, they add the corresponding **public .pub file only** to their own GitHub account if needed and verify repository collaborator/write access separately. Never print/upload a private key or assume a key proves identity.

After confirming that direct SSH connectivity is appropriate, these isolated authentication checks use the existing filenames:

```sh
ssh -F /dev/null -i "$HOME/.ssh/gh-agent2" -o IdentitiesOnly=yes -T git@github.com
ssh -F /dev/null -i "$HOME/.ssh/gh-agent3" -o IdentitiesOnly=yes -T git@github.com
ssh -F /dev/null -i "$HOME/.ssh/gh-agent4" -o IdentitiesOnly=yes -T git@github.com
```

-F /dev/null bypasses extra configured identities for that command only. Preserve required proxies/ports where applicable. Do not bypass host-key checks. GitHub's greeting identifies the authenticated username; a nonzero test exit alone does not establish failure because GitHub does not provide an interactive shell.

If SSH is chosen, any core.sshCommand belongs only to that participant's clone and must use the verified key and intended repository. No authentication change is required for Midhun P M's existing HTTPS setup. Check the names of GIT_SSH_COMMAND, GIT_SSH, Git config and author/committer environment overrides without printing secret values; do not change the user's global shell environment.

## Publishing and PRs

Follow docs/09-INTEGRATION.md: commit/test the slice, update the named handoff, push your feature branch and create a PR targeting main with the correct authorized account. If PR creation is unavailable, prepare the title, body and comparison link and ask Midhun P M to create it. SSH authentication does not switch the GitHub CLI/API account. Do not run a global gh auth switch, push application changes directly to main or invent a successful push/PR.

The selected user workflow is feature branches and PRs. Organiser clarification, participant permissions and real attribution remain separately evidenced fields; do not mark them verified from this document alone.

## Cleanup, only after explicit approval

Confirm useful work is committed, integrated and backed up. Stop only workspace processes. If temporary keys are no longer needed, the account holders revoke only those specific public keys after approval. Remove only agreed temporary clones, keys, containers or volumes. Never delete ~/.ssh, default credentials, global configuration or unrelated projects. No destructive cleanup script is supplied.

Technical reference: https://git-scm.com/docs/git-config . These instructions do not claim that any account authentication or collaborator permission has been tested.
