# Independent workspaces and verified Git identities

## Current checkpoint

The repository already exists at https://github.com/9MidhunPM/Cadentra and the current independent checkout has that HTTPS origin. During planning, read-only remote inspection returned no branches. The user approved one initial planning-pack commit/push to main, followed by feature branches and PRs for all application work. No new remote repository or global configuration changes are needed.

Midhun P M keeps the existing default identity and authentication. The participant handoffs now record successful SSH authentication and feature-branch pushes for the three existing keys below. This verifies Git transport, not API login. Existing filenames remain technical paths:

| Team member | Existing technical key path | Verified SSH account (handoff evidence) |
|---|---|---|
| Thanushree Suresh | ~/.ssh/gh-agent2 | thanushreesuresh |
| Noel Biju | ~/.ssh/gh-agent3 | noel-ult |
| Sherin Saji | ~/.ssh/gh-agent4 | Sherin745 |

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

The user explicitly selected SSH-only participant setup: do not initiate gh login, OAuth, API-token setup or account switching in teammate workspaces. Commit/test the slice, update the named handoff and push through the owner-specific SSH key. Send the tested branch/head, PR title/body, checks and comparison link to Midhun P M through Codex TUI. The coordinator creates/reviews/merges PRs using the existing 9MidhunPM API account. PR author is therefore 9MidhunPM; original commit author/committer metadata is preserved. SSH-only authentication cannot create PRs as the SSH account through GitHub REST/GraphQL. No participant API login is required for this selected workflow. SSH authentication does not switch the GitHub CLI/API account. Do not run a global gh auth switch, push application changes directly to main or invent a successful push/PR.

The selected user workflow is feature branches and PRs. Organiser clarification, participant permissions and real attribution remain separately evidenced fields; do not mark them verified from this document alone.

## Cleanup, only after explicit approval

Confirm useful work is committed, integrated and backed up. Stop only workspace processes. If temporary keys are no longer needed, the account holders revoke only those specific public keys after approval. Remove only agreed temporary clones, keys, containers or volumes. Never delete ~/.ssh, default credentials, global configuration or unrelated projects. No destructive cleanup script is supplied.

Technical reference: https://git-scm.com/docs/git-config . See participant handoffs for their SSH authentication/push evidence. API credentials, organiser compliance and unrelated repository permissions are not inferred from Git authentication.

GitHub primary references: [SSH access](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/about-ssh), [REST API authentication](https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api).
