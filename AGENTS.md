# actions

A monorepo of GitHub Actions, each versioned and released on its own.

## Layout

- `<action>/action.yml`: the action. Used as `eyelock/actions/<action>@<action>-v<major>`.
- `<action>/package.json`: its version, and a workspace package so changesets can version it.
  The `name` must equal the directory name.
- `<action>/Dockerfile` (optional): published as `ghcr.io/eyelock/<action>`.
- `<action>/tests/`: tests and fixtures. CI also runs the action itself against its fixtures.
- `scripts/release-plan.mjs`: lists the actions whose version has no tag yet.

## Adding an action

1. Create `<action>/` with `action.yml`, `package.json` (version `1.0.0`) and a README.
2. Add it to `pnpm-workspace.yaml`, the table in `README.md`, and a job in `.github/workflows/ci.yml`.
3. The first merge to `main` tags `<action>-v1.0.0` and `<action>-v1`.

## Conventions

- Pin every third-party action by commit SHA, with the version in a comment.
- Pin every tool an action installs to a reviewed release, by commit or digest. What gates a
  merge must not change without a pull request.
- Every pull request has a changeset naming each action it changes. Changes to repository
  tooling only need an empty changeset (`pnpm changeset --empty`).
- A change that can make a passing build fail (new rules, stricter defaults) is at least minor.
- Scripts accept `--help`, write results to stdout and diagnostics to stderr.
