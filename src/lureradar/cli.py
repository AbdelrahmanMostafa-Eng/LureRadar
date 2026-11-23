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
pcwatch_app = typer.Typer(
    help="PC Watch: is GTA 6 coming to PC? (official sources only)", no_args_is_help=True
)
app.add_typer(feed_app, name="feed")
app.add_typer(pcwatch_app, name="pcwatch")

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


# ---------------------------------------------------------------------- scan
@app.command()
def scan(
    out: Annotated[Path | None, typer.Option(help="Write feeds to this directory.")] = None,
    state: Annotated[Path, typer.Option(help="SQLite state file.")] = Path(".lureradar/state.db"),
    fixtures: Annotated[
        bool, typer.Option("--fixtures", help="Use recorded fixtures (offline, reserved domains).")
    ] = False,
    fixtures_dir: Annotated[Path | None, typer.Option(help="Fixtures directory.")] = None,
    no_enrich: Annotated[bool, typer.Option("--no-enrich", help="Skip DNS/RDAP/TLS/HTTP.")] = False,
    source: Annotated[
        list[str] | None, typer.Option("--source", "-s", help="Only these sources.")
    ] = None,
    since_hours: Annotated[int, typer.Option(help="Look-back window for sources.")] = 72,
    budget: Annotated[float, typer.Option(help="Time budget in seconds.")] = 1200.0,
    max_enrich: Annotated[int, typer.Option(help="Cap on enriched candidates per run.")] = 300,
    pack: Annotated[list[str] | None, typer.Option("--pack", "-p")] = None,
    fpr_from: Annotated[
        Path | None, typer.Option(help="bench results JSON for the FPR badge")
    ] = None,
    json_out: Annotated[bool, typer.Option("--json", help="Print the run report as JSON.")] = False,
    log_json: Annotated[
        bool, typer.Option("--log-json", help="Structured JSON logs on stderr.")
    ] = False,
) -> None:
    """Run the pipeline once: sources -> prefilter -> enrich -> score -> state -> feeds."""
    from lureradar.export.signing import signing_key_from_env
    from lureradar.pipeline.orchestrator import ScanConfig, run_scan
    from lureradar.util import logging as lr_logging

    lr_logging.configure("INFO" if log_json else "WARNING", json_lines=log_json)
    fx = None
    if fixtures or fixtures_dir:
        fx = fixtures_dir or Path(__file__).resolve().parents[2] / "tests" / "fixtures"
        if not (fx / "sources").is_dir():
            raise _fail(f"fixtures not found at {fx} (run from the repository)")
    fpr = None
    if fpr_from and fpr_from.is_file():
        fpr = float(orjson.loads(fpr_from.read_bytes()).get("benign_fpr_likely", 0.0))
    try:
        cfg = ScanConfig(
            state_path=state,
            out_dir=out,
            fixtures=fx,
            enrich=not no_enrich,
            sources=source or None,
            since_hours=since_hours,
            budget_s=budget,
            max_enrich=max_enrich,
            signer=signing_key_from_env(),
            fpr=fpr,
            packs=pack or None,
        )
        if fx is not None:
            from lureradar.util.time import parse_iso

            cfg.now = parse_iso("2026-11-21T12:00:00Z")  # fixtures are recorded at this time
        report = run_scan(cfg)
    except LureRadarError as exc:
        raise _fail(str(exc)) from exc
    if json_out:
        _dump_json(report)
        return
    console = _console()
    tiers_line = ", ".join(f"{k}: {v}" for k, v in report.get("tiers", {}).items())
    console.print(f"[bold {theme.RADAR}]scan complete[/] in {report['seconds']}s")
    for name, info in report.get("sources", {}).items():
        color = theme.RADAR if info["status"] == "ok" else theme.AMBER
        detail = info.get("candidates", info.get("error", ""))
        console.print(f"  [{color}]{info['status']:7}[/] {name}: {escape_markup(str(detail))}")
    console.print(
        f"  collected {report['collected']} → unique {report['unique_domains']} → "
        f"prefilter dropped {report['prefilter_dropped']} ({report['prefilter_drop_ratio']:.0%}) → "
        f"enriched {report['enriched']}"
    )
    console.print(f"  verdicts: {tiers_line}")
    if out:
        console.print(f"  feeds written to [bold]{out}[/]")


def escape_markup(text: str) -> str:
    from rich.markup import escape

    return escape(text)


# ---------------------------------------------------------------------- feed
@feed_app.command("build")
def feed_build(
    out: Annotated[Path, typer.Option(help="Output directory.")] = Path("build/feeds"),
    state: Annotated[Path, typer.Option(help="SQLite state file.")] = Path(".lureradar/state.db"),
) -> None:
    """Rebuild every feed file from the pipeline state (no collection)."""
    from lureradar.export.signing import signing_key_from_env
    from lureradar.pipeline.publish import publish
    from lureradar.pipeline.state import State
    from lureradar.util.time import utcnow

    if not state.is_file():
        raise _fail(f"{state} not found: run `lureradar scan` first")
    st = State(state)
    try:
        paths = publish(st.all(), out, utcnow(), signer=signing_key_from_env())
    finally:
        st.close()
    _console().print(f"[{theme.RADAR}]wrote[/] {len(paths)} files to {out}")


@feed_app.command("diff")
def feed_diff(
    old: Annotated[Path, typer.Argument(help="Older latest.json")],
    new: Annotated[Path, typer.Argument(help="Newer latest.json")],
    json_out: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Show indicators added, removed or re-tiered between two feed documents."""
    from lureradar.export.jsonfeed import load
    from lureradar.util.defang import defang

    try:
        a, b = load(old), load(new)
    except LureRadarError as exc:
        raise _fail(str(exc)) from exc
    before = {i.domain: i for i in a.indicators}
    after = {i.domain: i for i in b.indicators}
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(d for d in set(before) & set(after) if before[d].tier != after[d].tier)
    if json_out:
        _dump_json({"added": added, "removed": removed, "retiered": changed})
        return
    console = _console()
    for d in added:
        console.print(f"[{theme.DANGER}]+ {defang(d)}[/] ({after[d].tier.value})")
    for d in removed:
        console.print(f"[{theme.RADAR}]- {defang(d)}[/]")
    for d in changed:
        console.print(
            f"[{theme.AMBER}]~ {defang(d)}[/] {before[d].tier.value} → {after[d].tier.value}"
        )
    console.print(f"{len(added)} added, {len(removed)} removed, {len(changed)} re-tiered")


@feed_app.command("verify")
def feed_verify(
    path: Annotated[Path, typer.Argument(help="Feed directory (or latest.json).")],
    pubkey: Annotated[
        Path | None, typer.Option(help="minisign public key (default: keys/lureradar-feed.pub).")
    ] = None,
    require_signature: Annotated[bool, typer.Option(help="Fail if files are unsigned.")] = False,
) -> None:
    """Validate every feed format, checksums and minisign signatures."""
    from lureradar.export.verify import verify_feed_dir

    directory = path if path.is_dir() else path.parent
    key = pubkey or Path("keys/lureradar-feed.pub")
    results = verify_feed_dir(directory, key if key.is_file() else None, require_signature)
    console = _console()
    failed = False
    for name, ok, detail in results:
        failed = failed or not ok
        mark = f"[{theme.RADAR}]✓[/]" if ok else f"[{theme.DANGER}]✗[/]"
        console.print(f"{mark} {name}: {escape_markup(detail)}")
    if failed:
        raise typer.Exit(EXIT_ERROR)


@feed_app.command("pull")
def feed_pull(
    url: Annotated[
        str | None, typer.Option(help="Feed base URL (default: BASE_URL/feeds/).")
    ] = None,
    pubkey: Annotated[Path | None, typer.Option(help="minisign public key to verify with.")] = None,
) -> None:
    """Download the latest feed snapshot for offline `check` (verifies the signature)."""
    from lureradar.pipeline.pull import pull_snapshot

    try:
        path, note = pull_snapshot(url, pubkey)
    except LureRadarError as exc:
        raise _fail(str(exc)) from exc
    _console().print(f"[{theme.RADAR}]saved[/] {path} ({note})")


@feed_app.command("keygen")
def feed_keygen(
    out: Annotated[Path, typer.Option(help="Where to write the PUBLIC key.")] = Path(
        "keys/lureradar-feed.pub"
    ),
) -> None:
    """Create a feed signing key. The secret is printed once and never written to disk."""
    from lureradar.export.signing import generate

    if out.exists():
        raise _fail(f"{out} exists; refusing to overwrite a published key")
    key = generate()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(key.public_file(), encoding="utf-8")
    console = _console()
    console.print(
        f"[{theme.RADAR}]public key[/] written to {out} (key id {key.key_id_hex}); commit it."
    )
    console.print(
        f"[bold {theme.AMBER}]secret key[/] (store as the GitHub Actions secret "
        "LURERADAR_SIGNING_KEY, then clear your terminal):"
    )
    sys.stdout.write(key.secret_b64() + "\n")


# -------------------------------------------------------------------- export
@app.command("export")
def export_cmd(
    fmt: Annotated[str, typer.Option("--format", "-f", help="hosts|domains|abp|rpz|json|csv|stix")],
    input_path: Annotated[
        Path | None, typer.Option("--input", "-i", help="Feed JSON (default: cached snapshot).")
    ] = None,
    min_tier: Annotated[str, typer.Option(help="Minimum tier to include.")] = "likely",
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Write to a file.")] = None,
) -> None:
    """Convert a feed document into a blocklist or interchange format."""
    from lureradar.export import abp, csvfeed, hosts, jsonfeed, rpz, stix
    from lureradar.models import Tier
    from lureradar.pipeline.snapshot import default_snapshot_path

    writers = {
        "hosts": hosts.to_hosts,
        "domains": hosts.to_domains,
        "abp": abp.to_abp,
        "adguard": abp.to_abp,
        "rpz": rpz.to_rpz,
        "csv": csvfeed.to_csv,
        "stix": stix.to_stix,
    }
    try:
        tier = Tier.parse(min_tier)
        doc = jsonfeed.load(input_path or default_snapshot_path())
    except (LureRadarError, ValueError) as exc:
        raise _fail(str(exc)) from exc
    if fmt == "json":
        chosen = [i for i in doc.indicators if i.tier >= tier and i.status == "active"]
        text = jsonfeed.dumps(
            doc.model_copy(update={"indicators": chosen, "min_tier": tier})
        ).decode()
    elif fmt in writers:
        text = writers[fmt](doc, tier)
    else:
        raise _fail(f"unknown format {fmt!r} (choose from json, {', '.join(writers)})")
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


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


# ------------------------------------------------------------------- pcwatch
def _pcwatch_context(pack_id: str):  # type: ignore[no-untyped-def]
    from lureradar.packs.loader import load_packs
    from lureradar.pcwatch.config import load_config

    try:
        (pack,) = load_packs([pack_id])
        return pack, load_config(pack)
    except LureRadarError as exc:
        raise _fail(str(exc)) from exc


def _print_pcwatch(state, console: Console) -> None:  # type: ignore[no-untyped-def]
    from rich.panel import Panel
    from rich.table import Table

    from lureradar.pcwatch.feed import BADGE_COLORS
    from lureradar.pcwatch.status import honest_sentence

    color = BADGE_COLORS[state.status]
    body = Table.grid(padding=(0, 2))
    body.add_row(f"[bold {color}]{state.status.value}[/]", f"[bold]{honest_sentence(state)}[/]")
    if state.note and state.status.value != "UNKNOWN":
        body.add_row("", f"[{theme.AMBER}]{escape_markup(state.note)}[/]")
    body.add_row("last checked", str(state.last_checked or "never"))
    body.add_row("last success", str(state.last_success or "never"))
    body.add_row("last changed", str(state.last_changed or "unknown"))
    for src in state.sources:
        mark = {"ok": theme.RADAR, "failed": theme.DANGER, "unsupported": theme.MUTED}[src.status]
        body.add_row(
            f"[{mark}]{src.status}[/]", f"{src.name}: [{theme.MUTED}]{escape_markup(src.detail)}[/]"
        )
    console.print(Panel(body, title=f"PC Watch · {state.subject}", border_style=color))
    console.print(f"[{theme.MUTED}]{state.disclaimer}[/]")


@pcwatch_app.command("status")
def pcwatch_status(
    state_file: Annotated[
        Path | None, typer.Option("--state", help="A published pc-watch.json.")
    ] = None,
    pack: Annotated[str, typer.Option("--pack", "-p")] = "gta6",
    json_out: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Show the current PC Watch status (UNKNOWN unless a recent check succeeded)."""
    from lureradar.pcwatch.feed import load_state, to_json
    from lureradar.pcwatch.status import resolve
    from lureradar.util.time import utcnow

    pk, config = _pcwatch_context(pack)
    previous = load_state(state_file) if state_file else None
    state = resolve(pk, config, None, previous, utcnow())
    if json_out:
        sys.stdout.write(to_json(state).decode())
        return
    _print_pcwatch(state, _console())


@pcwatch_app.command("check")
def pcwatch_check(
    pack: Annotated[str, typer.Option("--pack", "-p")] = "gta6",
    previous: Annotated[
        Path | None, typer.Option(help="Previous pc-watch.json (keeps history).")
    ] = None,
    out: Annotated[Path | None, typer.Option(help="Write pc-watch.json/.atom/badge here.")] = None,
    fixtures: Annotated[
        Path | None, typer.Option(help="Read recorded source pages instead.")
    ] = None,
    issue_body: Annotated[
        Path | None, typer.Option(help="Write a maintainer issue body here if review is needed.")
    ] = None,
    json_out: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Check official sources now. Never changes the published status by itself."""
    from lureradar.pcwatch.feed import load_state, to_json, write_outputs
    from lureradar.pcwatch.notify import issue_body as make_issue
    from lureradar.pcwatch.sources import PcWatchChecker
    from lureradar.pcwatch.status import resolve
    from lureradar.util.time import utcnow

    pk, config = _pcwatch_context(pack)
    check = PcWatchChecker(config, fixtures=fixtures).run()
    state = resolve(pk, config, check, load_state(previous) if previous else None, utcnow())
    if out:
        write_outputs(state, out)
    if issue_body is not None:
        if state.review_pending:
            issue_body.write_text(make_issue(state, check), encoding="utf-8")
        elif issue_body.exists():
            issue_body.unlink()
    if json_out:
        sys.stdout.write(to_json(state).decode())
        return
    _print_pcwatch(state, _console())


@pcwatch_app.command("history")
def pcwatch_history(
    pack: Annotated[str, typer.Option("--pack", "-p")] = "gta6",
    json_out: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Print the verified evidence timeline (official statements only)."""
    from lureradar.pcwatch.timeline import ordered

    _pk, config = _pcwatch_context(pack)
    entries = ordered(config)
    if json_out:
        _dump_json([e.model_dump(mode="json") for e in entries])
        return
    console = _console()
    for e in entries:
        console.print(f"[bold {theme.INFO}]{e.date}[/]  [bold]{escape_markup(e.title)}[/]")
        console.print(f"            {escape_markup(e.paraphrase)}")
        console.print(f"            [{theme.MUTED}]{escape_markup(e.meaning)} · {e.url}[/]")
        verified = f"verified {e.verified_on}: {escape_markup(e.verification)}"
        console.print(f"            [{theme.MUTED}]{verified}[/]")


# -------------------------------------------------------------------- report
@app.command()
def report(
    stats: Annotated[
        Path | None, typer.Option(help="stats.json from a feed directory (default: fixture demo).")
    ] = None,
    out: Annotated[Path, typer.Option(help="Output directory.")] = Path("build/report"),
    abuse: Annotated[
        str | None, typer.Option("--abuse", help="Draft an abuse report for this domain/URL.")
    ] = None,
    live: Annotated[bool, typer.Option("--live", help="Look up the RDAP abuse contact.")] = False,
) -> None:
    """Shareable daily lure-report card (SVG/HTML/PNG), or an abuse-report draft."""
    from lureradar.models import Tier
    from lureradar.report.abuse import build_abuse_report
    from lureradar.report.card import share_text, write_report
    from lureradar.scoring.engine import Engine

    console = _console()
    if abuse:
        try:
            verdict = Engine().check(abuse)
        except LureRadarError as exc:
            raise _fail(str(exc)) from exc
        rdap = None
        if live:
            import asyncio

            from lureradar.enrich.rdap import RdapClient
            from lureradar.util.domains import parse_target

            try:
                rdap = asyncio.run(RdapClient().lookup(parse_target(abuse).registrable_domain))
            except LureRadarError as exc:
                console.print(f"[{theme.AMBER}]RDAP lookup failed: {escape_markup(str(exc))}[/]")
        if verdict.tier < Tier.LIKELY:
            console.print(
                f"[{theme.AMBER}]Verdict is {verdict.tier.value.upper()}: LureRadar does not "
                "consider this a likely lure. Verify it yourself before reporting anything.[/]"
            )
        draft = build_abuse_report(verdict, rdap)
        console.print(
            f"[bold]To:[/] {', '.join(draft.to) or '(registrar/host abuse contact; use --live)'}"
        )
        console.print(f"[bold]Subject:[/] {escape_markup(draft.subject)}\n")
        sys.stdout.write(draft.body)
        console.print(f"[{theme.MUTED}]Draft only: LureRadar never sends reports automatically.[/]")
        return
    demo = stats is None
    if stats is None:
        from lureradar.pipeline.orchestrator import ScanConfig, run_scan
        from lureradar.util.time import parse_iso

        fixtures = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
        tmp = out / "demo-feeds"
        run_scan(ScanConfig(state_path=out / "demo.db", out_dir=tmp, fixtures=fixtures,
                            now=parse_iso("2026-11-21T12:00:00Z")))  # fmt: skip
        stats = tmp / "stats.json"
    data = orjson.loads(stats.read_bytes())
    paths = write_report(data, out, demo=demo)
    for p in paths:
        console.print(f"[{theme.RADAR}]wrote[/] {p}")
    console.print(f"share text: {escape_markup(share_text(data, demo=demo))}")


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
