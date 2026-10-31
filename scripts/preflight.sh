#!/usr/bin/env bash
# Read-only local checks. No network, key content, config writes or installs.
set -uo pipefail

printf 'Cadentra preflight (read-only; not an authentication test)\n\n'
for tool in git ssh ssh-keygen python3 node npm docker; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf '[present] %s\n' "$tool"
  else
    printf '[missing] %s\n' "$tool"
  fi
done

printf '\nTemporary key file presence (private contents are never read):\n'
for n in 2 3 4; do
  case "$n" in
    2) participant='Thanushree Suresh' ;;
    3) participant='Noel Biju' ;;
    4) participant='Sherin Saji' ;;
  esac
  key="$HOME/.ssh/gh-agent$n"
  if [[ -f "$key" && -f "$key.pub" ]]; then
    printf '[present] %s legacy key files\n' "$participant"
    if command -v ssh-keygen >/dev/null 2>&1; then
      if fingerprint=$(ssh-keygen -lf "$key.pub"); then
        read -r bits digest _ <<< "$fingerprint"
        printf '[public fingerprint] %s %s\n' "$bits" "$digest"
      else
        printf '[warning] Cannot parse public key for %s\n' "$participant"
      fi
    fi
  else
    printf '[unverified] Missing legacy key file(s) for %s; do not regenerate automatically\n' "$participant"
  fi
done

printf '\nPotential environment overrides (values withheld):\n'
for name in GIT_SSH GIT_SSH_COMMAND GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL GIT_COMMITTER_NAME GIT_COMMITTER_EMAIL GIT_CONFIG_COUNT GIT_CONFIG_GLOBAL GIT_CONFIG_SYSTEM GIT_CONFIG_PARAMETERS GH_TOKEN GITHUB_TOKEN; do
  if [[ -v "$name" ]]; then
    printf '[review] %s is set\n' "$name"
  fi
done

if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  printf '\nCurrent branch and effective commit identity:\n'
  git branch --show-current
  git config --show-origin --get user.name || true
  git config --show-origin --get user.email || true
  printf '\nRemote safety checks:\n'
  for key in remote.origin.url remote.origin.pushurl; do
    values=$(git config --get-all "$key" || true)
    if [[ -z "$values" ]]; then
      printf '[unset] %s\n' "$key"
      continue
    fi
    while IFS= read -r value; do
      case "$value" in
        git@github.com:*|ssh://git@github.com/*) printf '[SSH GitHub] %s\n' "$key" ;;
        https://github.com/*) printf '[HTTPS GitHub] %s; verify existing account before publishing\n' "$key" ;;
        *) printf '[review] %s is not a recognized GitHub remote form; value withheld\n' "$key" ;;
      esac
    done <<< "$values"
  done
  if git config --local --get core.sshCommand >/dev/null 2>&1; then
    printf '[configured] repository-local core.sshCommand (not printed)\n'
  else
    printf '[inherited/default] no repository-local core.sshCommand\n'
  fi
  if [[ -f AGENTS.override.md ]]; then
    printf '[review] Root AGENTS.override.md exists and may supersede AGENTS.md\n'
  fi
else
  printf '\n[not initialized] This directory is not a Git working tree. No repository was created.\n'
fi
printf '\nNo settings changed. Key registration, authenticated username and repository permissions remain unverified.\n'
