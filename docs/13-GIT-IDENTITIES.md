# Independent workspaces and verified Git identities

## Current checkpoint

The repository exists at https://github.com/9MidhunPM/Cadentra, with integrated application work on main. The user's latest explicit delivery policy is reviewed local owner merges followed by ordinary main pushes through that owner's SSH identity, serialized by Midhun P M. The previous coordinator API PR workflow is historical and is not used for new slices. See docs/09-INTEGRATION.md for the GO and expected-remote-SHA protocol.

Midhun P M's default SSH identity was verified as 9MidhunPM without changing configuration. All three participant keys below have verified SSH account identities and write access. Verification does not require a participant API login. Existing filenames remain technical paths:

| Team member | Existing technical key path | Verified SSH account (handoff evidence) |
|---|---|---|
| Thanushree Suresh | ~/.ssh/gh-agent2 | thanushreesuresh |
| Noel Biju | ~/.ssh/gh-agent3 | noel-ult |
| Sherin Saji | ~/.ssh/gh-agent4 | Sherin745 |

Keep existing clone folder names and key files. Never regenerate keys or set another person's commit identity as part of renaming the documentation.

## Read-only inspection first

Run `bash scripts/preflight.sh` in each independent clone. It inspects tools, effective author name/email, remote transport, branch, key presence and potentially overriding environment-variable names. It does not register keys, contact GitHub, change configuration or prove account authentication. The preflight supports the existing HTTPS origin; owner publication uses a command-scoped SSH invocation or an already configured owner-specific SSH transport. Preserve origin and global configuration rather than changing them to switch accounts.

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

## Existing owner SSH identities

The existing owner keys and repository write access are verified. Reuse them without regeneration, registration changes or private-key inspection. If account verification later needs refreshing, use only public fingerprints or the isolated SSH greeting test below. Never print/upload private keys.

After confirming that direct SSH connectivity is appropriate, these isolated authentication checks use the existing filenames:

```sh
ssh -F /dev/null -i "$HOME/.ssh/gh-agent2" -o IdentitiesOnly=yes -T git@github.com
ssh -F /dev/null -i "$HOME/.ssh/gh-agent3" -o IdentitiesOnly=yes -T git@github.com
ssh -F /dev/null -i "$HOME/.ssh/gh-agent4" -o IdentitiesOnly=yes -T git@github.com
```

-F /dev/null bypasses extra configured identities for that command only. Preserve required proxies/ports where applicable. Do not bypass host-key checks. GitHub's greeting identifies the authenticated username; a nonzero test exit alone does not establish failure because GitHub does not provide an interactive shell.

Use an already configured owner-specific SSH transport or a command-scoped core.sshCommand with that owner's existing key and the SSH repository URL. Do not modify remote URLs, global Git/SSH/gh settings or default authentication. Midhun P M uses the verified default SSH identity. Check the names of GIT_SSH_COMMAND, GIT_SSH, Git config and author/committer environment overrides without printing secret values; do not change the user's global shell environment.

## Reviewed owner merges and main pushes

Participants remain SSH-key-only; do not initiate gh login, OAuth, API-token setup or account switching. The earlier workflow in which the coordinator created/reviewed/merged PRs using 9MidhunPM API credentials is superseded. Historical PR authors and original commits stay accurately attributed.

Submit the exact tested feature SHA and checks to Midhun P M. After review, wait for a serialized GO that names the owner, immutable reviewed head and expected remote main SHA. Fetch/verify that baseline through the owner's SSH transport, merge the reviewed head locally, test the result and use an ordinary non-force main push through the same owner identity. Recheck remote main immediately before publishing; a different base, changed feature head, conflict, failing check or rejected push requires stopping and reporting for renewed coordination. Only one owner integrates at a time.

Never substitute another account's credentials, bypass review, force push, delete branches or change global settings. Send the verified resulting remote main SHA and test evidence back to Midhun P M before releasing the slot. Full procedure: docs/09-INTEGRATION.md.

Checkpoint: Thanushree Suresh's owner main push at 18e88ff was verified at 06:31 UTC on 31 October 2026. Sherin Saji's production head prefix 76ec is authorized next; the others wait. This snapshot does not replace the latest GO or remote-SHA verification.

Organiser interpretation and contribution evidence remain separately recorded; Git write access does not establish event compliance.

## Cleanup, only after explicit approval

Confirm useful work is committed, integrated and backed up. Stop only workspace processes. If temporary keys are no longer needed, the account holders revoke only those specific public keys after approval. Remove only agreed temporary clones, keys, containers or volumes. Never delete ~/.ssh, default credentials, global configuration or unrelated projects. No destructive cleanup script is supplied.

Technical reference: https://git-scm.com/docs/git-config . See participant handoffs for their SSH authentication/push evidence. API credentials, organiser compliance and unrelated repository permissions are not inferred from Git authentication.

GitHub primary references: [SSH access](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/about-ssh), [REST API authentication](https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api).
