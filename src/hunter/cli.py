"""The command line, and the only place Hunter is invoked from.

Section 11.5. Every command is a thin wrapper over ``hunter.run``, and the
GitHub Action calls these commands and nothing else. That is what makes local
and CI results identical by construction rather than by discipline.

Exit codes:

* 0  the run completed. In advisory mode this is always the answer.
* 1  the run completed and the score failed the configured gate.
* 2  the run could not complete: a missing manifest, an invalid ruleset.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import typer

from hunter import __version__
from hunter.config import ConfigError
from hunter.config.register import RegisterError
from hunter.emit import mermaid
from hunter.emit.markdown import model_page, write_site
from hunter.emit.pr_comment import build_comment
from hunter.emit.report import write_report
from hunter.emit.showcase import Window, build_showcase, showcase_page
from hunter.ingest.manifest import ManifestError
from hunter.run import RunResult, run
from hunter.score.baseline import Baseline, write_baseline
from hunter.score.engine import fails_build

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Repository intelligence for analytics repositories containing dbt and LookML.",
)

EXIT_OK = 0
EXIT_GATE_FAILED = 1
EXIT_COULD_NOT_RUN = 2


def _fail(message: str) -> None:
    typer.secho(message, fg=typer.colors.RED, err=True)
    raise typer.Exit(EXIT_COULD_NOT_RUN)


def _execute(
    root: Path,
    *,
    config_file: Path | None,
    manifest: Path | None,
    house: str | None = None,
    as_of: dt.date | None = None,
    read_git: bool = True,
) -> RunResult:
    """Run the pipeline, turning every expected failure into a clear message."""
    try:
        return run(
            root,
            project_file=config_file,
            manifest_path=manifest,
            house=house,
            as_of=as_of,
            read_git=read_git,
        )
    except ManifestError as exc:
        _fail(f"Could not read the dbt manifest.\n{exc}")
    except ConfigError as exc:
        _fail(f"The ruleset is not valid.\n{exc}")
    except RegisterError as exc:
        _fail(f"The register file is not valid.\n{exc}")
    raise AssertionError("unreachable")


def _print_score(result: RunResult) -> None:
    """The terminal summary. The number first, the reading second, per FR7.10."""
    from hunter.emit.plain import DIMENSION_HEADINGS

    score = result.score
    typer.echo("")
    typer.secho(f"  {score.total:g} / 100", fg=typer.colors.CYAN, bold=True)
    typer.echo(f"  {score.interpretation}")
    if score.baseline is not None and score.delta is not None:
        typer.echo(
            f"  Starting point {score.baseline:g}, "
            f"{'up' if score.delta > 0 else 'down' if score.delta < 0 else 'level'} "
            f"{abs(score.delta):g}"
        )
    typer.echo("")

    for entry in score.dimensions:
        heading = DIMENSION_HEADINGS[entry.dimension]
        if entry.scored:
            typer.echo(
                f"  {entry.score:>5.1f}  {entry.grade}  {heading:<38}"
                f"{entry.finding_count:>4} findings"
            )
        else:
            typer.echo(f"      -  -  {heading:<38}not measured")

    if score.systemic_gaps:
        typer.echo("")
        typer.secho("  Missing everywhere it was checked:", fg=typer.colors.YELLOW)
        for gap in score.systemic_gaps:
            typer.echo(f"    {gap.failed} of {gap.checked}  {gap.plain_heading or gap.rule}")

    typer.echo("")
    typer.echo(
        f"  {len(result.open_findings)} open, {len(result.suggestions)} suggestions, "
        f"{len(result.suppressed_findings)} silenced"
    )
    typer.echo("")


@app.command()
def score(
    root: Path = typer.Argument(Path(), help="The repository to read."),
    config_file: Path | None = typer.Option(
        None, "--config", "-c", help="Path to hunter.yml. Found automatically if omitted."
    ),
    manifest: Path | None = typer.Option(
        None, "--manifest", "-m", help="Path to manifest.json, if not where the ruleset says."
    ),
    house: str | None = typer.Option(
        None, "--house", help="House ruleset to measure against, e.g. ra-house@1."
    ),
    out: Path | None = typer.Option(
        None, "--out", "-o", help="Where to write report.json. Defaults to the output directory."
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Write the report and print nothing."),
    no_git: bool = typer.Option(
        False, "--no-git", help="Skip history. Faster, but nothing is attributed."
    ),
) -> None:
    """Score a repository and write report.json."""
    result = _execute(
        root, config_file=config_file, manifest=manifest, house=house, read_git=not no_git
    )
    target = out or (root / result.config.paths.output_dir / "report.json")
    write_report(target, result)

    if not quiet:
        _print_score(result)
        typer.echo(f"  Report written to {target}")

    failed, reason = fails_build(result.score, result.config)
    if failed:
        typer.secho(f"\n  {reason}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_GATE_FAILED)


@app.command()
def check(
    root: Path = typer.Argument(Path(), help="The repository to read."),
    pr: str | None = typer.Option(None, "--pr", help="Pull request number, for the footer."),
    base: str = typer.Option(
        "origin/main", "--base", help="The branch this change is measured against."
    ),
    config_file: Path | None = typer.Option(None, "--config", "-c"),
    manifest: Path | None = typer.Option(None, "--manifest", "-m"),
    previous: Path | None = typer.Option(
        None,
        "--previous-report",
        help="A report.json from before this change, for a true before-and-after.",
    ),
    out: Path | None = typer.Option(None, "--out", "-o", help="Where to write the comment body."),
    report_url: str | None = typer.Option(
        None,
        "--report-url",
        help="The workflow run page that holds the report artifact. Linked from the footer.",
    ),
) -> None:
    """Build the pull request comment for a change."""
    result = _execute(root, config_file=config_file, manifest=manifest)
    changed = _changed_files(root, base)

    body = build_comment(
        result,
        changed_files=changed,
        previous_report=previous,
        pull_request=pr,
        report_url=report_url,
    )
    target = out or (root / result.config.paths.output_dir / "pr-comment.md")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")

    typer.echo(body)
    typer.echo(f"\nComment body written to {target}", err=True)

    failed, reason = fails_build(result.score, result.config)
    if failed:
        typer.secho(reason or "The gate failed.", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_GATE_FAILED)


def _changed_files(root: Path, base: str) -> list[str]:
    """Files this change touches, against a base reference.

    A failure here is not fatal: without a diff the comment falls back to
    reporting on the whole repository and says so.
    """
    for target in (base, "HEAD~1"):
        try:
            completed = subprocess.run(
                ["git", "diff", "--name-only", f"{target}...HEAD"],
                cwd=root,
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
        files = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        if files:
            return files
    return []


@app.command()
def align(
    root: Path = typer.Argument(Path(), help="The repository to read."),
    config_file: Path | None = typer.Option(None, "--config", "-c"),
    manifest: Path | None = typer.Option(None, "--manifest", "-m"),
    domain: str | None = typer.Option(None, "--domain", help="Show one area only."),
) -> None:
    """Show what was designed against what exists."""
    result = _execute(root, config_file=config_file, manifest=manifest, read_git=False)
    rows = [row for row in result.alignment.rows if domain is None or row.domain == domain]

    typer.echo("")
    for label, count, meaning in _state_lines(result):
        typer.echo(f"  {count:>4}  {label:<30}{meaning}")
    typer.echo("")

    coverage = result.alignment.coverage
    if coverage.design_coverage is not None:
        typer.echo(
            f"  Business model designed: {coverage.design_coverage:g}% "
            f"({coverage.conceptual_designed} of {coverage.conceptual_entities})"
        )
    if coverage.delivery_coverage is not None:
        typer.echo(
            f"  Design built:            {coverage.delivery_coverage:g}% "
            f"({coverage.designed_and_built} of {coverage.designed_entities})"
        )
    typer.echo("")

    for row in rows:
        typer.echo(f"  {row.label:<38}{row.state_label:<30}{row.technical_name or '-'}")
    typer.echo("")


def _state_lines(result: RunResult) -> list[tuple[str, int, str]]:
    from hunter.emit.plain import state_summary

    return state_summary(result)


@app.command()
def explain(
    model: str = typer.Argument(..., help="The model to describe."),
    root: Path = typer.Argument(Path(), help="The repository to read."),
    config_file: Path | None = typer.Option(None, "--config", "-c"),
    manifest: Path | None = typer.Option(None, "--manifest", "-m"),
) -> None:
    """Show everything Hunter knows about one model."""
    result = _execute(root, config_file=config_file, manifest=manifest)
    if result.project.any_model(model) is None:
        candidates = sorted(
            name for name in result.project.model_names() if model.lower() in name.lower()
        )
        message = f"No model named {model!r}."
        if candidates:
            message += " Did you mean: " + ", ".join(candidates[:5]) + "?"
        _fail(message)
    typer.echo(model_page(result, model))


@app.command()
def showcase(
    root: Path = typer.Argument(Path(), help="The repository to read."),
    days: int = typer.Option(14, "--days", help="How far back to look."),
    config_file: Path | None = typer.Option(None, "--config", "-c"),
    manifest: Path | None = typer.Option(None, "--manifest", "-m"),
    out: Path | None = typer.Option(None, "--out", "-o", help="Where to write the page."),
) -> None:
    """Report what changed in a window, and what it cost."""
    result = _execute(root, config_file=config_file, manifest=manifest)
    from hunter.ingest.git import load_git

    window = Window.last_days(days, end=result.as_of)
    built = build_showcase(result, window=window, git=load_git(root))
    page = showcase_page(result, built)

    target = out or (root / result.config.paths.output_dir / "showcase.md")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page, encoding="utf-8")
    typer.echo(page)
    typer.echo(f"\nShowcase written to {target}", err=True)


docs_app = typer.Typer(no_args_is_help=True, help="Build the published site.")
app.add_typer(docs_app, name="docs")


@docs_app.command("build")
def docs_build(
    root: Path = typer.Argument(Path(), help="The repository to read."),
    config_file: Path | None = typer.Option(None, "--config", "-c"),
    manifest: Path | None = typer.Option(None, "--manifest", "-m"),
    out: Path | None = typer.Option(None, "--out", "-o", help="Where to write the site."),
    build: bool = typer.Option(
        True, "--build/--markdown-only", help="Run MkDocs, or stop at the markdown."
    ),
) -> None:
    """Generate the site pages, and build them with MkDocs."""
    result = _execute(root, config_file=config_file, manifest=manifest)
    target = out or (root / result.config.paths.output_dir / "site")
    files = write_site(result, target)
    typer.echo(f"Wrote {len(files)} pages to {target}")

    if not build:
        return

    # Through this interpreter, not a bare `mkdocs`: the command's presence on
    # PATH is not reliable inside a virtual environment or in CI, and Hunter
    # would then report MkDocs as missing when it is installed.
    completed = subprocess.run(
        [sys.executable, "-m", "mkdocs", "build", "--quiet", "--site-dir", "_built"],
        cwd=target,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        if "No module named mkdocs" in completed.stderr:
            typer.secho(
                "MkDocs is not installed, so the markdown was written but not built. "
                "Install it with: uv tool install 'rittman-hunter[site]'",
                fg=typer.colors.YELLOW,
                err=True,
            )
            return
        typer.secho(
            f"MkDocs could not build the site:\n{completed.stderr.strip()}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(EXIT_COULD_NOT_RUN)

    typer.echo(f"Site built at {target / '_built'}")
    typer.echo(f"Open {target / '_built' / 'dashboard.html'}")


@app.command()
def dashboard(
    root: Path = typer.Argument(Path(), help="The repository to read."),
    config_file: Path | None = typer.Option(None, "--config", "-c"),
    manifest: Path | None = typer.Option(None, "--manifest", "-m"),
    out: Path | None = typer.Option(None, "--out", "-o", help="Where to write the file."),
) -> None:
    """Write the dashboard as one self-contained HTML file.

    Everything is inlined: the stylesheet, every chart and the logo. The file
    can be emailed, attached to a build or opened from a laptop with no network,
    and it needs neither MkDocs nor anything beside it.
    """
    from hunter.emit.dashboard import dashboard_html

    result = _execute(root, config_file=config_file, manifest=manifest)
    target = out or (root / result.config.paths.output_dir / "dashboard.html")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dashboard_html(result), encoding="utf-8")
    size = target.stat().st_size // 1024
    typer.echo(f"Wrote {target} ({size} KB, self-contained)")
    typer.echo(f"Open {target}")


@app.command("sync")
def sync_command(
    which: str = typer.Argument(
        "all",
        help="lookml, droughty, modelling, or all. Default all.",
        metavar="[lookml|droughty|modelling|all]",
    ),
    root: Path = typer.Option(Path(), "--root", "-r", help="The repository to read."),
    config_file: Path | None = typer.Option(None, "--config", "-c"),
    manifest: Path | None = typer.Option(None, "--manifest", "-m"),
    fail_on: str = typer.Option(
        "never",
        "--fail-on",
        help=(
            "never (report only), high (fail on a high-severity drift) or any "
            "(fail on any drift). A skipped check never fails."
        ),
    ),
    out: Path | None = typer.Option(None, "--out", "-o", help="Write the result as JSON."),
    summary: Path | None = typer.Option(
        None, "--summary", help="Write a Markdown summary, for a CI step summary."
    ),
) -> None:
    """Check whether one layer has drifted from another.

    Three checks, each a slice of the same rules the score runs, so a sync
    check and the score can never contradict each other.

    \b
    lookml      does the reporting layer still match the tables
    droughty    has the generated schema been applied, and is it current
    modelling   does what exists match what was designed and asked for

    A check whose sources are missing reports "skipped", never "passed".
    """
    from hunter import sync as sync_module

    if fail_on not in {"never", "high", "any"}:
        _fail(f"--fail-on must be never, high or any, not {fail_on!r}")

    if which != "all" and which not in sync_module.BY_KEY:
        known = ", ".join(sync_module.BY_KEY)
        _fail(f"No sync check named {which!r}. Choose one of: {known}, or all.")

    result = _execute(root, config_file=config_file, manifest=manifest, read_git=False)
    checks = list(sync_module.SYNC_CHECKS) if which == "all" else [sync_module.BY_KEY[which]]
    results = [sync_module.evaluate(result, check) for check in checks]

    for item in results:
        _print_sync(item)

    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(sync_module.as_payload(results, result), indent=2, default=str),
            encoding="utf-8",
        )
        typer.echo(f"  Written to {out}")

    if summary:
        summary.parent.mkdir(parents=True, exist_ok=True)
        summary.write_text(
            sync_module.as_markdown(results, logo_url=result.config.branding.logo_url),
            encoding="utf-8",
        )
        typer.echo(f"  Summary written to {summary}")

    failing = [item for item in results if item.fails_build(fail_on)]
    if failing:
        names = ", ".join(item.check.title for item in failing)
        typer.secho(f"  Failing: {names}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_GATE_FAILED)


def _print_sync(item: object) -> None:
    """One sync result, for a terminal.

    The statements come first and the findings second. A reader wants "5 of 6
    tables have a view" before they want six rule names.
    """
    from hunter import sync as sync_module
    from hunter.emit.plain import severity_label

    assert isinstance(item, sync_module.SyncResult)
    colour = {
        "in sync": typer.colors.GREEN,
        "drifted": typer.colors.RED,
        "skipped": typer.colors.BRIGHT_BLACK,
        "nothing to compare": typer.colors.BRIGHT_BLACK,
    }[item.verdict]

    typer.echo("")
    typer.secho(f"  {item.check.title}: {item.verdict}", fg=colour, bold=True)
    typer.echo(f"  {item.check.question}")
    typer.echo(f"  {item.headline}")

    if not item.ran:
        typer.echo("")
        return

    if item.statements:
        typer.echo("")
        for statement, done, total, missing in item.statements:
            mark = "ok  " if done == total else "--  "
            typer.echo(f"    {mark}{done:>3} of {total:<3} {statement}")
            if missing:
                shown = ", ".join(missing[:4])
                more = f" and {len(missing) - 4} more" if len(missing) > 4 else ""
                typer.echo(f"           {shown}{more}")

    if item.findings:
        typer.echo("")
        for finding in item.findings[:10]:
            typer.echo(f"    [{severity_label(finding.severity)}] {finding.summary}")
        if len(item.findings) > 10:
            typer.echo(f"    and {len(item.findings) - 10} more.")

    if item.absent_but_useful:
        names = ", ".join(sync_module.source_name(source) for source in item.absent_but_useful)
        typer.echo("")
        typer.echo(f"    Not read, so this check is narrower than it could be: {names}.")
    typer.echo("")


@app.command()
def diagram(
    root: Path = typer.Argument(Path(), help="The repository to read."),
    level: str = typer.Option(
        "conceptual",
        "--level",
        help="Which view: conceptual, logical, physical, lineage or blast.",
    ),
    domain: str | None = typer.Option(None, "--domain", help="One area only."),
    model: str | None = typer.Option(None, "--model", help="For the blast radius view."),
    config_file: Path | None = typer.Option(None, "--config", "-c"),
    manifest: Path | None = typer.Option(None, "--manifest", "-m"),
) -> None:
    """Print one Mermaid diagram."""
    result = _execute(root, config_file=config_file, manifest=manifest, read_git=False)
    if level == "conceptual":
        typer.echo(mermaid.conceptual_diagram(result.alignment, domain=domain))
    elif level == "logical":
        typer.echo(mermaid.logical_diagram(result.project, result.alignment, domain=domain))
    elif level == "physical":
        typer.echo(mermaid.physical_diagram(result.project, result.alignment, domain=domain))
    elif level == "lineage":
        if domain:
            typer.echo(mermaid.domain_graph(result.project, result.graph, domain))
        else:
            typer.echo(mermaid.collapsed_graph(result.project, result.graph))
    elif level == "blast":
        if not model:
            _fail("The blast radius view needs --model.")
        typer.echo(mermaid.blast_radius(str(model), result.project, result.graph))
    else:
        _fail(f"Unknown level {level!r}. Choose conceptual, logical, physical, lineage or blast.")


@app.command()
def baseline(
    root: Path = typer.Argument(Path(), help="The repository to read."),
    config_file: Path | None = typer.Option(None, "--config", "-c"),
    manifest: Path | None = typer.Option(None, "--manifest", "-m"),
    note: str | None = typer.Option(None, "--note", help="Why this baseline was taken."),
) -> None:
    """Record where this repository starts.

    FR7.5. An existing repository starts where it starts and only has to
    improve. Without this, installing Hunter on a mature project produces a low
    number and an argument rather than a direction of travel.
    """
    result = _execute(root, config_file=config_file, manifest=manifest)
    path = root / result.config.paths.baseline
    record = Baseline.from_result(
        result.score,
        house_version=result.config.house_version,
        commit=result.meta.get("commit"),
        recorded_on=result.as_of,
        note=note or "Recorded at installation.",
    )
    write_baseline(path, record)
    typer.echo(f"Baseline recorded at {result.score.total:g} in {path}")
    typer.echo("Commit this file so future runs measure movement rather than absolutes.")


@app.command()
def init(
    root: Path = typer.Argument(Path(), help="The repository to set up."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files."),
) -> None:
    """Write a starting hunter.yml and register.yml for this repository.

    The register is pre-filled with the models Hunter would flag, each with a
    blank reason, so the team fills in reasons rather than authoring from
    nothing. That is what makes it get used.
    """
    from hunter.emit.scaffold import detect, scaffold

    found = detect(root)
    for note in found.notes:
        typer.secho(f"  note: {note}", fg=typer.colors.YELLOW)

    # Pre-fill the register from a real run where one is possible. Handing
    # someone an empty file and asking them to document their exceptions does
    # not work; handing them the list and asking for a reason does.
    needs_owner: list[str] = []
    off_plan: list[str] = []
    if found.manifest_found:
        try:
            result = run(root, read_git=False)
        except (ManifestError, ConfigError, RegisterError):
            typer.secho(
                "  note: could not score the repository yet, so the register is a "
                "template rather than a filled-in list.",
                fg=typer.colors.YELLOW,
            )
        else:
            needs_owner = sorted(
                {
                    finding.subject
                    for finding in result.findings
                    if finding.rule == "documentation.owner_missing"
                }
            )
            off_plan = sorted(
                {
                    finding.subject
                    for finding in result.findings
                    if finding.rule == "alignment.built_off_plan"
                }
            )

    try:
        written = scaffold(root, force=force, needs_owner=needs_owner, off_plan=off_plan)
    except FileExistsError as exc:
        _fail(f"{exc}\nRun again with --force to overwrite.")
    for path in written:
        typer.echo(f"Wrote {path}")

    if needs_owner or off_plan:
        typer.echo("")
        typer.echo(
            f"  The register lists {len(needs_owner)} tables with no owner and "
            f"{len(off_plan)} built without a design. Fill in the blanks."
        )
    typer.echo("")
    typer.echo("Next: run `hunter score` and then `hunter baseline` to record a start.")


@app.command()
def rules() -> None:
    """List every rule Hunter can report."""
    import hunter.checks  # noqa: F401  registers every rule
    from hunter.checks.base import REGISTRY
    from hunter.emit.plain import DIMENSION_HEADINGS

    for spec in REGISTRY.all():
        typer.echo(
            f"{spec.id:<52}{spec.severity!s:<8}{spec.points:>5g}  "
            f"{DIMENSION_HEADINGS[spec.dimension]}"
        )
    typer.echo(f"\n{len(REGISTRY.all())} rules.")


@app.command()
def version() -> None:
    """Print the versions this run would stamp on a report."""
    from hunter import SCORE_MODEL_VERSION
    from hunter.config import resolve

    house = resolve().config.house_version
    typer.echo(
        json.dumps(
            {
                "hunter": __version__,
                "house_ruleset": house,
                "score_model": SCORE_MODEL_VERSION,
            },
            indent=2,
        )
    )


def main() -> int:
    """Entry point, so an unexpected failure exits cleanly rather than tracing."""
    try:
        app()
    except typer.Exit as exc:
        return int(exc.exit_code)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
