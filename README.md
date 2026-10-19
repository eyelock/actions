# actions

Reusable GitHub Actions. Each one lives in its own directory and is versioned and released on
its own, so upgrading one never forces an upgrade of another.

| Action | Use | Image |
|---|---|---|
| [skillspector](skillspector/) | `eyelock/actions/skillspector@skillspector-v1` | `ghcr.io/eyelock/skillspector:1` |

## Versions

An action's releases are tagged `<action>-v<version>`, and `<action>-v<major>` moves to the
latest release of that major version. Actions that ship a container publish it as
`ghcr.io/eyelock/<action>` with the same version and major tags, so the image also works
outside GitHub Actions.

Pin the major tag to receive fixes, or an exact version (or commit SHA) to upgrade only when
you choose. A ref that is not a release tag builds the action's image from source.

## Contributing

Each change carries a changeset naming the action it changes (`pnpm changeset`). See
[AGENTS.md](AGENTS.md) for the layout and conventions.
