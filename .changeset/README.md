# Changesets

Each action is its own package, so a changeset names the action it changes:

```md
---
"skillspector": minor
---

What changed, for someone reading the release notes.
```

Run `pnpm changeset` to write one. `scripts/release-plan.mjs` turns a version that has
no tag yet into `<action>-v<version>` and a moved `<action>-v<major>`.
