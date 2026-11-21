"""LureRadar command line interface (Typer + Rich).

Exit codes for ``check``: 0 clear, 10 suspicious, 20 likely, 30 confirmed,
1 error. They make LureRadar easy to use from scripts and CI.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import orjson
import typer
from rich.console import Console

from lureradar import __version__, theme
from lureradar.config import FEED_SCHEMA_VERSION, VERDICT_SCHEMA_VERSION, base_url
from lureradar.errors import LureRadarError

app = typer.Typer(
    name="lureradar",
    help="See the lure before you bite. Open threat radar for hyped-launch scams.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)
pack_app = typer.Typer(help="List, validate and scaffold campaign packs.", no_args_is_help=True)
feed_app = typer.Typer(help="Build, diff, verify and pull feeds.", no_args_is_help=True)
app.add_typer(pack_app, name="pack")
app.add_typer(feed_app, name="feed")

EXIT_ERROR = 1


def _console(stderr: bool = False) -> Console:
    return Console(stderr=stderr, highlight=False, soft_wrap=False)


def _fail(message: str) -> typer.Exit:
    _console(stderr=True).print(f"[bold {theme.DANGER}]error:[/] {message}")
    return typer.Exit(EXIT_ERROR)


def _dump_json(data: object) -> None:
    sys.stdout.write(orjson.dumps(data, option=orjson.OPT_INDENT_2).decode() + "\n")


# --------------------------------------------------------------------- check
@app.command()
def check(
    target: Annotated[
        str,
        typer.Argument(
            help="URL, domain (defanged is fine) or a message to analyse. Use - to read stdin."
        ),
    ],
    json_out: Annotated[bool, typer.Option("--json", help="Machine-readable output.")] = False,
    live: Annotated[
        bool,
        typer.Option(
            "--live",
            help="Also query DNS, RDAP, TLS, the page itself (hardened fetch) and configured "
            "reputation sources. Offline by default.",
        ),
    ] = False,
    pack: Annotated[
        list[str] | None, typer.Option("--pack", "-p", help="Campaign pack id(s). Default: all.")
    ] = None,
    explain: Annotated[
        bool, typer.Option("--explain", help="Show evidence for every signal.")
    ] = False,
    snapshot: Annotated[
        Path | None, typer.Option(help="Feed snapshot to consult (default: cached `feed pull`).")
    ] = None,
    no_snapshot: Annotated[
        bool, typer.Option("--no-snapshot", help="Ignore the local feed snapshot.")
    ] = False,
) -> None:
    """Score a URL, domain or message and print a verdict card."""
    from lureradar.pipeline.snapshot import FeedSnapshot
    from lureradar.render import verdict_card
    from lureradar.scoring.engine import Engine

    raw = sys.stdin.read() if target == "-" else target
    try:
        snap = None if no_snapshot else FeedSnapshot.load_default(snapshot)
        engine = Engine(pack_ids=pack or None, snapshot=snap)
        enricher = None
        if live:
            from lureradar.enrich.live import LiveEnricher

            enricher = LiveEnricher.from_env()
            if not json_out:
                _console(stderr=True).print(
                    f"[{theme.MUTED}]--live: contacting the target and enrichment services "
                    "(DNS, RDAP, TLS, HTTP). See docs/PRIVACY.md.[/]"
                )
        verdict = engine.check(raw, enricher=enricher)
    except LureRadarError as exc:
        raise _fail(str(exc)) from exc
    if json_out:
        _dump_json(verdict.model_dump(mode="json"))
    else:
        console = _console()
        width = min(console.width, 100)
        console.print(verdict_card(verdict, explain=explain), width=width)
    raise typer.Exit(verdict.tier.exit_code)


# ---------------------------------------------------------------------- pack
@pack_app.command("list")
def pack_list(
    json_out: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """List available campaign packs."""
    from rich.table import Table

    from lureradar.packs.loader import list_pack_dirs, load_pack, packs_root

    try:
        packs = [load_pack(d) for d in list_pack_dirs()]
    except LureRadarError as exc:
        raise _fail(str(exc)) from exc
    if json_out:
        _dump_json(
            [
                {
                    "id": p.id,
                    "name": p.name,
                    "version": p.version,
                    "as_of": p.as_of.isoformat(),
                    "keywords": len(p.keywords),
                    "brands": len(p.brands),
                }
                for p in packs
            ]
        )
        return
    table = Table(title=f"Campaign packs in {packs_root()}", title_style=theme.MUTED)
    for col in ("id", "name", "version", "as of", "keywords", "brands", "allowlist"):
        table.add_column(col)
    for p in packs:
        table.add_row(
            p.id,
            p.name,
            str(p.version),
            p.as_of.isoformat(),
            str(len(p.keywords)),
            str(len(p.brands)),
            str(len(p.allowlist.outlets) + len(p.allowlist.platforms)),
        )
    _console().print(table)


@pack_app.command("validate")
def pack_validate(
    paths: Annotated[
        list[Path] | None, typer.Argument(help="Pack folders (default: all packs).")
    ] = None,
    strict: Annotated[bool, typer.Option(help="Treat warnings as errors.")] = False,
) -> None:
    """Validate pack schema, references and quality lints."""
    from lureradar.packs.loader import list_pack_dirs
    from lureradar.packs.validator import validate_pack_dir

    console = _console()
    targets = paths or list_pack_dirs()
    if not targets:
        raise _fail("no packs found")
    failed = False
    for path in targets:
        report = validate_pack_dir(path)
        if report.ok:
            console.print(f"[{theme.RADAR}]✓[/] {path}")
        else:
            failed = True
            console.print(f"[{theme.DANGER}]✗[/] {path}")
            for err in report.errors:
                console.print(f"  [{theme.DANGER}]{err}[/]")
        for warning in report.warnings:
            console.print(f"  [{theme.AMBER}]warning:[/] {warning}")
            failed = failed or strict
    if failed:
        raise typer.Exit(EXIT_ERROR)


@pack_app.command("new")
def pack_new(
    pack_id: Annotated[str, typer.Argument(help="New pack id, e.g. 'console-x'.")],
    name: Annotated[str | None, typer.Option(help="Display name.")] = None,
    root: Annotated[Path, typer.Option(help="Packs directory.")] = Path("packs"),
) -> None:
    """Scaffold a minimal, valid campaign pack (about 20 lines of YAML)."""
    from lureradar.packs.scaffold import new_pack

    try:
        path = new_pack(pack_id, root, name)
    except LureRadarError as exc:
        raise _fail(str(exc)) from exc
    _console().print(
        f"[{theme.RADAR}]created[/] {path}/pack.yaml  → edit it, then run "
        f"[bold]lureradar pack validate {path}[/]"
    )


# -------------------------------------------------------------------- doctor
@app.command()
def doctor(
    json_out: Annotated[bool, typer.Option("--json")] = False,
    offline: Annotated[bool, typer.Option("--offline", help="Skip all network checks.")] = False,
    fixtures: Annotated[
        Path | None, typer.Option(help="Report source health in fixture mode instead.")
    ] = None,
) -> None:
    """Check the environment and the live health of every data source."""
    from lureradar.doctor import run_doctor

    report = run_doctor(offline=offline, fixtures=fixtures)
    if json_out:
        _dump_json(report)
        return
    from rich.markup import escape
    from rich.table import Table

    colors = {
        "ok": theme.RADAR,
        "degraded": theme.AMBER,
        "requires_key": theme.INFO,
        "disabled": theme.MUTED,
        "down": theme.DANGER,
        "skipped": theme.MUTED,
        "warn": theme.AMBER,
    }
    console = _console()
    for title, rows in (("Environment", report["environment"]), ("Sources", report["sources"])):
        table = Table(title=title, title_style=f"bold {theme.TEXT}", expand=False)
        table.add_column("check")
        table.add_column("status")
        table.add_column("detail", style=theme.MUTED, overflow="fold")
        for row in rows:
            status = row["status"]
            table.add_row(
                escape(row["name"]),
                f"[{colors.get(status, theme.TEXT)}]{status}[/]",
                escape(row["detail"]),
            )
        console.print(table)
    console.print(f"[{theme.MUTED}]checked at {report['checked_at']}[/]")


# ------------------------------------------------------------------- version
@app.command()
def version(json_out: Annotated[bool, typer.Option("--json")] = False) -> None:
    """Print version information."""
    info = {
        "version": __version__,
        "verdict_schema": VERDICT_SCHEMA_VERSION,
        "feed_schema": FEED_SCHEMA_VERSION,
        "base_url": base_url(),
        "python": sys.version.split()[0],
    }
    if json_out:
        _dump_json(info)
    else:
        _console().print(
            f"LureRadar {__version__} (verdict schema {VERDICT_SCHEMA_VERSION}, "
            f"feed schema {FEED_SCHEMA_VERSION}) · {base_url()}"
        )


def main() -> None:
    """Console-script entry point."""
    try:
        app()
    except LureRadarError as exc:  # pragma: no cover - commands handle their own errors
        _console(stderr=True).print(f"[bold {theme.DANGER}]error:[/] {exc}")
        sys.exit(EXIT_ERROR)


if __name__ == "__main__":  # pragma: no cover
    main()
