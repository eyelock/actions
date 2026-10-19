# Contributing

1. Branch from `develop` and open the pull request against `develop`. `main` only moves by release.
2. Add a changeset naming each action you change: `pnpm changeset`. Use a minor bump for anything
   that can make a passing build fail (new rules, stricter defaults), major for a breaking input
   or output change. Repository-only changes take `pnpm changeset --empty`.
3. CI must pass: lint, each action's tests, and the action run against its own fixtures. The
   ruleset requires the aggregate **All Clear** check.

## Conventions

- Pin third-party actions by commit SHA, with the version in a comment.
- Pin every tool an action installs to a reviewed release, by commit or digest.
- An action that ships an image builds from its own `Dockerfile`; CI tests that image.
- Scripts accept `--help`, write results to stdout and diagnostics to stderr.

See [AGENTS.md](../AGENTS.md) for the layout and how to add an action.
