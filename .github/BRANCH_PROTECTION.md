# Branch Protection Configuration

`develop` and `main` are each protected by one repository ruleset. There is no classic branch
protection: the rulesets are the single source of truth.

| Ruleset | Branch | Purpose |
|---------|--------|---------|
| Develop Branch Protection | `develop` | Where feature and fix work lands (the default branch) |
| Main Branch Protection | `main` | Moves only by release: PRs from `develop`, `release/*` or `hotfix/*` |
| Never Delete Main or Develop | `main`, `develop` | Neither branch can be deleted or force-pushed, by anyone: it has no bypass, so admins included |

## Required checks

Both rulesets require the status check **All Clear**. It is the last job of the CI workflow,
depends on every other job in `ci.yml` and fails if any of them failed or was cancelled. Add or
rename CI jobs freely; only All Clear is required, and a new job must be added to its `needs`.

`main` additionally requires **Verify PR source branch**, from `protect-main.yml`, which rejects
a PR into `main` unless its source is `develop`, `release/*` or `hotfix/*`.

## Rules (both rulesets)

- Changes reach the branch through a pull request, with zero required approvals
- All review conversations must be resolved
- The branch need not be up to date before merging (required status checks are not strict)
- Force pushes blocked
- Branch deletion blocked
- Repository admins can bypass in emergencies

Release tags (`<action>-v<version>` and the moved `<action>-v<major>`) are pushed by the release
workflow and are not covered by these branch rulesets.

Squash merges and merge commits are allowed, rebase merges are not. Merge commits are for
release and back-merge PRs; everything else is squashed.
