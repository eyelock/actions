# skillspector

## 1.1.0

### Minor Changes

- New `include` input: directories without a `SKILL.md` (agents, rules, commands, `.claude`) are scanned as one unit each, so harness artifacts other than skills are gated too. A file in both an included directory and a skill is reported once.
