#!/usr/bin/env bash
# One-time GitHub-side setup for a repo created from repo-template.
# Templates can't carry branch protection or repo settings — this script does.
# Requires: gh (authenticated). Safe to re-run.
#
# Usage:
#   ./bootstrap.sh                      # Tier A, requires a check named `test`
#   REQUIRED_CHECKS=ci,lint ./bootstrap.sh
#   REQUIRED_CHECKS= ./bootstrap.sh     # PR required, but no required checks
#   TIER=B ./bootstrap.sh               # repo settings only, no branch protection
set -euo pipefail

TIER="${TIER:-A}"
# Comma-separated job names, matched EXACTLY against reported check names.
REQUIRED_CHECKS="${REQUIRED_CHECKS-test}"

REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
echo "Configuring $REPO (tier $TIER)"

# Merge policy: squash ONLY, so every PR lands as exactly one commit on main,
# and the branch is deleted on merge. Note this makes `gh pr merge --merge`
# fail — use `--squash`.
gh repo edit "$REPO" \
  --enable-squash-merge --enable-merge-commit=false --enable-rebase-merge=false \
  --delete-branch-on-merge --enable-issues

if [ "$TIER" != "A" ]; then
  echo "Tier $TIER: repo settings applied, branch protection skipped."
  exit 0
fi

# ---------------------------------------------------------------------------
# Tier A: protect the default branch.
#
# enforce_admins is TRUE, deliberately. With it false — the previous default —
# the whole block is decorative on a solo repo: a repo admin's direct push to
# main SUCCEEDS, GitHub prints its objections and accepts the push anyway. If
# you are the only contributor and you are an admin, that protects nobody, and
# any AGENTS.md claiming "no direct pushes to main" is simply false.
# Emergency bypass is then a deliberate act: re-PUT this endpoint with the flag
# off, fix, put it back.
#
# Asymmetry worth knowing: allow_force_pushes/allow_deletions bind admins
# REGARDLESS of enforce_admins. So with enforce_admins false you get the worst
# combination — a normal push to main goes through, but a force-push to undo it
# is refused.
#
# TRAP — do not require a check that will not always report. A required context
# whose workflow is path-filtered (or does not exist yet) leaves every PR that
# does not touch that path stuck on "Expected — Waiting for status", forever
# and unmergeably. For a repo whose CI is path-filtered, either require nothing
# (PR-only protection still stops direct pushes) or add one always-runs
# aggregator job and require that.
# ---------------------------------------------------------------------------
DEFAULT_BRANCH=$(gh api "repos/$REPO" --jq .default_branch)

if [ -n "$REQUIRED_CHECKS" ]; then
  CONTEXTS=$(printf '%s' "$REQUIRED_CHECKS" | jq -R 'split(",") | map(select(length > 0))')
  CHECKS_BLOCK=$(jq -nc --argjson c "$CONTEXTS" '{strict: false, contexts: $c}')
  echo "Requiring status checks: $REQUIRED_CHECKS"
  echo "  (verify each name actually reports on every PR — see TRAP above)"
else
  CHECKS_BLOCK=null
  echo "No required status checks — PR requirement only."
fi

jq -nc --argjson checks "$CHECKS_BLOCK" '{
  required_status_checks: $checks,
  enforce_admins: true,
  required_pull_request_reviews: { required_approving_review_count: 0 },
  restrictions: null,
  allow_force_pushes: false,
  allow_deletions: false
}' | gh api -X PUT "repos/$REPO/branches/$DEFAULT_BRANCH/protection" \
  -H "Accept: application/vnd.github+json" --input - > /dev/null

# Report what actually landed rather than assuming the PUT meant what we meant.
printf 'Protected %s: ' "$DEFAULT_BRANCH"
gh api "repos/$REPO/branches/$DEFAULT_BRANCH/protection" --jq '
  "enforce_admins=\(.enforce_admins.enabled)  " +
  "checks=[\(.required_status_checks.contexts // [] | join(","))]  " +
  "force_pushes=\(.allow_force_pushes.enabled)"'

echo "Done. You can still self-merge instantly — 0 approvals are required."
