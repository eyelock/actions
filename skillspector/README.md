# skillspector

Scan agent skills with [NVIDIA SkillSpector](https://github.com/NVIDIA/SkillSpector) and fail on
any finding the baseline does not suppress.

A skill is any directory holding a `SKILL.md`. Each one is scanned on its own, statically
(`--no-llm`): no API key, no cost, and the same tree always gives the same result.

## Why not just run `skillspector scan`

- **Its exit code is not a gate.** `skillspector scan` exits 1 only when a skill's risk score
  passes 50, so a skill with several medium findings exits 0. This action takes its verdict
  from the SARIF instead, and fails on any active finding.
- **One baseline per repository.** SkillSpector matches a baseline rule's `path:` against paths
  relative to the skill being scanned. This action lets a repository keep one baseline whose
  paths are relative to the repository, and resolves each rule for each skill.
- **Pinned, packaged and published.** SkillSpector is not on PyPI. The image pins a reviewed
  release by commit, so an upstream change cannot alter what gates a merge.

## Usage

```yaml
name: Skills
on:
  pull_request:

permissions:
  contents: read

jobs:
  skillspector:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: eyelock/actions/skillspector@skillspector-v1
        with:
          exclude: |
            */evals/files/*
```

On a pull request only the skills the pull request touches are scanned. A change to the
baseline scans them all, since removing a rule can surface a finding anywhere.

| Input | Default | |
|---|---|---|
| `path` | `.` | Directory to search for skills. |
| `baseline` | `<path>/.skillspector-baseline.yaml` if present | Repository-wide baseline. |
| `exclude` | | Globs of skill directories to skip, relative to `path`, one per line. |
| `changed-only` | `true` | On pull requests, scan only the skills that changed. |
| `fail-on-findings` | `true` | `false` reports without failing, for introducing the scan. |
| `upload-sarif` | `false` | Upload to code scanning; needs `security-events: write`. |
| `image` | | Scanner image to run instead of the published one. |

Outputs: `result` (`pass` or `fail`) and `sarif` (path to the merged report). Findings appear
as annotations on the pull request and as a table in the job summary.

## The baseline

Accept a finding only after reading it. Each rule needs an `id` and a `reason`, and should
have a `path`, so the suppression cannot hide the same kind of finding elsewhere:

```yaml
version: 2
rules:
  - id: "P1"
    path: "skills/github/SKILL.md"
    reason: "Quotes 'ignore previous instructions' as an example of text the skill must refuse."
  - id: "SC2"
    path: "plugins/vendor-harness/skills/vendor-adapters/references/*.md"
    reason: "Reference docs quote each vendor's official installer; the skill never runs them."
```

- `path` is a glob over the repository path, relative to `path`; `*` crosses `/`.
- `message` (optional) is a case-insensitive glob over the finding's description or matched text.
- `fingerprints` are refused: they bind to one SkillSpector version and to skill-relative paths,
  so they break on every upgrade.

On a full scan the action warns about rules that suppressed nothing, so the baseline only
shrinks when the skills improve.

## Upgrading SkillSpector

The image pins a SkillSpector release. A weekly workflow opens a pull request when NVIDIA
publishes a newer one, as a minor version of this action: new rules can report findings that
the previous release did not. Pin `@skillspector-v1` to take those upgrades, or an exact
`@skillspector-v1.2.0` to take them when you choose.

## Outside GitHub Actions

The image works anywhere Docker does:

```bash
docker run --rm -v "$PWD:/scan:ro" ghcr.io/eyelock/skillspector:1 gate .
docker run --rm -v "$PWD:/scan:ro" ghcr.io/eyelock/skillspector:1 gate . --exclude '*/evals/files/*'
docker run --rm -v "$PWD:/scan:ro" ghcr.io/eyelock/skillspector:1 scan ./skills/my-skill
```

`gate` exits 0 with no active findings, 1 with active findings and 2 when a scan could not
complete. Any other first argument goes straight to `skillspector`.

### As a ynh sensor

```json
"sensors": {
  "skillspector": {
    "category": "security",
    "tolerance": "blocking",
    "version_command": "docker run --rm ghcr.io/eyelock/skillspector:1 --version",
    "source": {
      "command": "docker run --rm -v \"$PWD:/scan:ro\" ghcr.io/eyelock/skillspector:1 gate ."
    },
    "output": { "format": "text", "channel": "stdout+exit" }
  }
}
```

## Development

```bash
docker build -t skillspector-gate:dev skillspector
docker run --rm -v "$PWD/skillspector:/src:ro" --entrypoint python \
  skillspector-gate:dev -m unittest discover -s /src/tests -v
```
