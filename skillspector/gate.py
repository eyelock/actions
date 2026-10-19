#!/usr/bin/env python3
"""Gate a tree of agent skills on SkillSpector findings.

`skillspector scan` scores one skill and exits 1 only when the risk score
passes 50, so a skill with several medium findings still exits 0. A gate that
trusts that exit code reports "clean" over active findings. This script takes
its verdict from the SARIF instead: any finding the baseline does not
suppress fails the gate.

It also lets a repository keep one baseline for all its skills. SkillSpector
matches a rule's `path:` against paths relative to the skill it is scanning,
so a rule written against the repository layout never matches. Each rule is
resolved here against the files that exist in each skill, and handed to the
scan as an exact, skill-relative path. Suppression itself stays in
SkillSpector, so its reports and SARIF still record every suppression and its
reason.

Exit codes: 0 no active findings, 1 active findings, 2 bad input or a scan
that did not complete.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_BASELINE = ".skillspector-baseline.yaml"
SKIP_DIRS = {".git", "node_modules"}
LEVEL_ORDER = {"error": 0, "warning": 1, "note": 2, "none": 3}
ANNOTATION = {"error": "error", "warning": "warning", "note": "notice", "none": "notice"}


class GateError(Exception):
    """Bad input, or a scan that did not complete. Exit code 2."""


@dataclass
class Finding:
    rule: str
    level: str
    severity: str
    path: str
    line: int | None
    message: str
    matched: str
    suppressed_by: str | None = None


@dataclass
class SkillResult:
    skill: str
    findings: list[Finding] = field(default_factory=list)
    included: bool = False

    @property
    def active(self) -> list[Finding]:
        return [f for f in self.findings if f.suppressed_by is None]


def discover_skills(root: Path, excludes: list[str]) -> list[str]:
    """Every directory under root holding a SKILL.md, relative to root."""
    skills = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        if "SKILL.md" not in filenames:
            continue
        rel = Path(dirpath).relative_to(root).as_posix()
        if any(fnmatch.fnmatch(rel, pattern) for pattern in excludes):
            continue
        skills.append(rel)
    return skills


def select_changed(skills: list[str], changed: list[str], baseline: str | None) -> list[str]:
    """Scan targets containing a changed file. All of them if the baseline
    changed, since dropping a rule can surface findings in any skill."""
    changed = [c.strip().removeprefix("./") for c in changed if c.strip()]
    if baseline and baseline in changed:
        return skills
    picked = []
    for skill in skills:
        prefix = "" if skill == "." else skill + "/"
        if any(c.startswith(prefix) for c in changed):
            picked.append(skill)
    return picked


def load_baseline(path: Path) -> list[dict]:
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise GateError(f"cannot read baseline {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise GateError(f"baseline {path} is not a mapping")
    if doc.get("fingerprints"):
        raise GateError(
            f"baseline {path} has fingerprints. They bind to one SkillSpector version and to "
            "paths relative to a single skill, so a repository-wide baseline cannot use them. "
            "Write path-scoped rules instead."
        )
    rules = doc.get("rules") or []
    if not isinstance(rules, list):
        raise GateError(f"baseline {path}: rules must be a list")
    for i, rule in enumerate(rules):
        if not isinstance(rule, dict) or not str(rule.get("reason", "")).strip():
            raise GateError(f"baseline {path}: rule {i + 1} needs a non-empty reason")
        if not (rule.get("id") or rule.get("rule_id")):
            raise GateError(
                f"baseline {path}: rule {i + 1} needs an id. A rule without one "
                "suppresses every kind of finding."
            )
    return rules


def glob_escape(path: str) -> str:
    return "".join(f"[{c}]" if c in "*?[" else c for c in path)


def skill_files(root: Path, skill: str) -> list[str]:
    base = root / skill
    files = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            files.append((Path(dirpath) / name).relative_to(base).as_posix())
    return files


def rules_for_skill(rules: list[dict], skill: str, files: list[str]) -> list[tuple[int, dict]]:
    """Translate repository-relative rules into rules for one skill.

    A rule without a path applies everywhere and is kept as is. A rule with a
    path becomes one rule per file of this skill whose repository path the glob
    matches, with that file's exact skill-relative path.
    """
    prefix = "" if skill == "." else skill + "/"
    out = []
    for index, rule in enumerate(rules):
        pattern = rule.get("path", rule.get("file"))
        if pattern is None:
            out.append((index, dict(rule)))
            continue
        for rel in files:
            if fnmatch.fnmatch(prefix + rel, pattern):
                translated = {k: v for k, v in rule.items() if k not in ("path", "file")}
                translated["path"] = glob_escape(rel)
                out.append((index, translated))
    return out


def scan(binary: str, root: Path, skill: str, baseline: Path | None, sarif: Path) -> None:
    cmd = [binary, "scan", str(root / skill), "--no-llm", "--format", "sarif", "--output", str(sarif)]
    if baseline is not None:
        cmd += ["--baseline", str(baseline)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    # 0 and 1 are both completed scans; the verdict comes from the SARIF.
    if proc.returncode not in (0, 1) or not sarif.is_file():
        detail = (proc.stderr or proc.stdout).strip().splitlines()[-5:]
        raise GateError(f"skillspector failed on {skill} (exit {proc.returncode}): " + " | ".join(detail))


def read_sarif(sarif: Path, skill: str, display_root: str) -> tuple[list[Finding], dict]:
    doc = json.loads(sarif.read_text(encoding="utf-8"))
    findings = []
    runs = doc.get("runs") or []
    if not runs:
        raise GateError(f"SARIF for {skill} has no runs")
    for run in runs:
        for res in run.get("results", []):
            loc = (res.get("locations") or [{}])[0].get("physicalLocation", {})
            artifact = loc.get("artifactLocation", {})
            path = Path(os.path.normpath(os.path.join(display_root, skill, artifact.get("uri", "")))).as_posix()
            # Rewritten in place so the merged SARIF points at real repository paths.
            if "uri" in artifact:
                artifact["uri"] = path
            region = loc.get("region", {})
            props = res.get("properties", {})
            suppressions = res.get("suppressions") or []
            findings.append(
                Finding(
                    rule=res.get("ruleId", "?"),
                    level=res.get("level", "warning"),
                    severity=props.get("severity", ""),
                    path=path,
                    line=region.get("startLine"),
                    # Matched text can span lines; reports and annotations want one.
                    message=" ".join(res.get("message", {}).get("text", "").split()),
                    matched=" ".join(str(props.get("finding", "")).split()),
                    suppressed_by=(suppressions[0].get("justification") or "baseline") if suppressions else None,
                )
            )
    return findings, doc


def finding_key(f: Finding) -> tuple:
    return (f.rule, f.path, f.line, f.matched)


def sarif_key(res: dict) -> tuple:
    loc = (res.get("locations") or [{}])[0].get("physicalLocation", {})
    return (
        res.get("ruleId"),
        loc.get("artifactLocation", {}).get("uri"),
        loc.get("region", {}).get("startLine"),
        " ".join(str(res.get("properties", {}).get("finding", "")).split()),
    )


def merge_sarif(docs: list[dict]) -> dict:
    """One run for the whole tree. Code scanning rejects several runs from the
    same tool in one upload. A file inside both a skill and an included
    directory is reported once."""
    rules: dict[str, dict] = {}
    results = []
    seen: set[tuple] = set()
    driver = {}
    for doc in docs:
        for run in doc.get("runs", []):
            driver = driver or {k: v for k, v in run.get("tool", {}).get("driver", {}).items() if k != "rules"}
            for rule in run.get("tool", {}).get("driver", {}).get("rules", []):
                rules.setdefault(rule["id"], rule)
            for res in run.get("results", []):
                key = sarif_key(res)
                if key not in seen:
                    seen.add(key)
                    results.append(res)
    driver["rules"] = list(rules.values())
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{"tool": {"driver": driver}, "results": results}],
    }


def escape_annotation(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def report(results: list[SkillResult], stale: list[dict], annotate: bool) -> str:
    active = [f for r in results for f in r.active]
    suppressed = sum(len(r.findings) - len(r.active) for r in results)
    lines = []
    for f in sorted(active, key=lambda f: (LEVEL_ORDER.get(f.level, 9), f.path, f.line or 0)):
        where = f"{f.path}:{f.line}" if f.line else f.path
        detail = f" ({f.matched})" if f.matched else ""
        lines.append(f"  {f.severity or f.level:<8} {f.rule:<5} {where}  {f.message}{detail}")
        if annotate:
            props = f"file={f.path}" + (f",line={f.line}" if f.line else "") + f",title=SkillSpector {f.rule}"
            print(f"::{ANNOTATION.get(f.level, 'warning')} {props}::{escape_annotation(f.message + detail)}")
    print(f"SkillSpector: scanned {scanned(results)}, {len(active)} active finding(s), {suppressed} suppressed.")
    if lines:
        print()
        print("\n".join(lines))
        print()
        print("Fix each finding, or add a path-scoped rule with a reason to the baseline.")
    for rule in stale:
        print(f"warning: baseline rule suppressed nothing: {json.dumps(rule, sort_keys=True)}", file=sys.stderr)
    return summary_markdown(results, active, suppressed, stale)


def scanned(results: list[SkillResult]) -> str:
    skills = sum(1 for r in results if not r.included)
    included = len(results) - skills
    text = f"{skills} skill(s)"
    return text + (f" and {included} included director{'y' if included == 1 else 'ies'}" if included else "")


def summary_markdown(results, active, suppressed, stale) -> str:
    out = ["## SkillSpector", ""]
    if not results:
        out.append("No skills to scan.")
        return "\n".join(out) + "\n"
    verdict = "✅ No active findings" if not active else f"❌ {len(active)} active finding(s)"
    out += [f"{verdict} in {scanned(results)}, {suppressed} suppressed by the baseline.", ""]
    if active:
        out += ["| Severity | Rule | Location | Finding |", "|---|---|---|---|"]
        for f in sorted(active, key=lambda f: (LEVEL_ORDER.get(f.level, 9), f.path, f.line or 0)):
            where = f"`{f.path}:{f.line}`" if f.line else f"`{f.path}`"
            text = (f.message + (f": {f.matched}" if f.matched else "")).replace("|", "\\|")
            out.append(f"| {f.severity or f.level} | {f.rule} | {where} | {text} |")
        out.append("")
    if stale:
        out += [f"{len(stale)} baseline rule(s) suppressed nothing and can be removed.", ""]
    return "\n".join(out) + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="skillspector-gate",
        description="Scan every skill under ROOT with SkillSpector and fail on any finding the baseline does not suppress.",
    )
    p.add_argument("root", nargs="?", default=".", help="directory to search for skills (default: .)")
    p.add_argument(
        "--baseline",
        help=f"repository-wide baseline, paths relative to ROOT (default: ROOT/{DEFAULT_BASELINE} if present)",
    )
    p.add_argument(
        "--changed-files",
        help="file listing changed paths relative to ROOT, one per line; only skills containing one are scanned",
    )
    p.add_argument(
        "--exclude", action="append", default=[], help="glob of skill directories to skip, relative to ROOT; repeatable"
    )
    p.add_argument(
        "--include",
        action="append",
        default=[],
        help="directory without a SKILL.md to scan as one unit (agents, rules, commands), relative to ROOT; repeatable",
    )
    p.add_argument("--sarif", help="write one merged SARIF file here, paths relative to the working directory")
    p.add_argument("--summary", help="write a Markdown summary here")
    p.add_argument("--skillspector", default="skillspector", help="skillspector executable")
    return p.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    root = Path(args.root)
    if not root.is_dir():
        raise GateError(f"{root} is not a directory")

    baseline_path = Path(args.baseline) if args.baseline else root / DEFAULT_BASELINE
    if args.baseline and not baseline_path.is_file():
        raise GateError(f"baseline {baseline_path} not found")
    rules = load_baseline(baseline_path) if baseline_path.is_file() else []
    baseline_rel = os.path.relpath(baseline_path, root) if baseline_path.is_file() else None

    skills = discover_skills(root, args.exclude)
    included = []
    for d in args.include:
        rel = Path(os.path.normpath(d.strip())).as_posix()
        if not (root / rel).is_dir():
            raise GateError(f"--include {d}: no such directory under {root}")
        if rel not in skills and rel not in included:
            included.append(rel)
    skills = skills + included
    full_scan = True
    if args.changed_files:
        changed = Path(args.changed_files).read_text(encoding="utf-8").splitlines()
        selected = select_changed(skills, changed, baseline_rel)
        full_scan = len(selected) == len(skills)
        skills = selected

    results: list[SkillResult] = []
    docs = []
    used: set[int] = set()
    seen: set[tuple] = set()
    with tempfile.TemporaryDirectory(prefix="skillspector-gate-") as tmp:
        for n, skill in enumerate(skills):
            translated = rules_for_skill(rules, skill, skill_files(root, skill))
            skill_baseline = None
            if translated:
                skill_baseline = Path(tmp) / f"{n}.baseline.yaml"
                doc = {"version": 2, "rules": [rule for _, rule in translated]}
                skill_baseline.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
            sarif = Path(tmp) / f"{n}.sarif"
            print(f"==> {skill}", file=sys.stderr)
            scan(args.skillspector, root, skill, skill_baseline, sarif)
            findings, doc = read_sarif(sarif, skill, args.root)
            # A file inside both a skill and an included directory is scanned twice.
            findings = [f for f in findings if finding_key(f) not in seen]
            seen.update(finding_key(f) for f in findings)
            docs.append(doc)
            results.append(SkillResult(skill, findings, included=skill in included))
            reasons = {f.suppressed_by for f in findings if f.suppressed_by}
            used.update(i for i, rule in translated if str(rule.get("reason")) in reasons)

    # Staleness is only knowable when every skill was scanned.
    stale = [rules[i] for i in range(len(rules)) if i not in used] if full_scan and skills else []
    summary = report(results, stale, annotate=os.environ.get("GITHUB_ACTIONS") == "true")
    if args.summary:
        Path(args.summary).write_text(summary, encoding="utf-8")
    if args.sarif:
        Path(args.sarif).write_text(json.dumps(merge_sarif(docs), indent=2), encoding="utf-8")
    return 1 if any(r.active for r in results) else 0


def main(argv: list[str] | None = None) -> int:
    try:
        return run(parse_args(sys.argv[1:] if argv is None else argv))
    except GateError as exc:
        print(f"skillspector-gate: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
