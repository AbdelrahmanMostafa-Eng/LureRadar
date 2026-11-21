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
app.add_typer(pack_app, name="pack")

EXIT_ERROR = 1


def _console(stderr: bool = False) -> Console:
    return Console(stderr=stderr, highlight=False, soft_wrap=False)


def _fail(message: str) -> typer.Exit:
    _console(stderr=True).print(f"[bold {theme.DANGER}]error:[/] {message}")
    return typer.Exit(EXIT_ERROR)


def _dump_json(data: object) -> None:
    sys.stdout.write(orjson.dumps(data, option=orjson.OPT_INDENT_2).decode() + "\n")


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
