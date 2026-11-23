"""Render assets/demo.gif without vhs: Rich -> SVG -> PNG (resvg) -> GIF (Pillow).

`make demo` uses vhs + assets/demo.tape when vhs is installed, and falls back
to this script otherwise. The GIF shows the exact offline command from the
README; nothing here touches the network.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import resvg_py
from PIL import Image
from rich.console import Console
from rich.terminal_theme import TerminalTheme

from lureradar.render import verdict_card
from lureradar.scoring.engine import Engine

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "demo.gif"
TARGET = "https://rockstar-gta6-pc-download[.]test/free-key"
COMMAND = f'uvx lureradar check "{TARGET}"'
WIDTH_COLS = 92
OUT_WIDTH = 960
# Terminal theme built from the design tokens (src/lureradar/theme.py).
THEME = TerminalTheme(
    (7, 9, 13),
    (230, 237, 243),
    [(13, 17, 23), (255, 77, 94), (60, 255, 176), (255, 176, 32),
     (76, 194, 255), (76, 194, 255), (76, 194, 255), (230, 237, 243)],
    [(139, 152, 165), (255, 77, 94), (60, 255, 176), (255, 176, 32),
     (76, 194, 255), (76, 194, 255), (76, 194, 255), (255, 255, 255)],
)  # fmt: skip


def _console() -> Console:
    return Console(
        record=True,
        width=WIDTH_COLS,
        force_terminal=True,
        color_system="truecolor",
        file=io.StringIO(),
    )


def _svg(lines_printer, total_lines: int) -> str:  # type: ignore[no-untyped-def]
    con = _console()
    printed = lines_printer(con)
    for _ in range(max(0, total_lines - printed)):
        con.print("")
    return con.export_svg(title="lureradar", font_aspect_ratio=0.61, theme=THEME)


def _png(svg: str) -> Image.Image:
    data = resvg_py.svg_to_bytes(svg_string=svg, font_family="DejaVu Sans Mono", width=OUT_WIDTH)
    return Image.open(io.BytesIO(bytes(data))).convert("RGB")


def main() -> int:
    verdict = Engine(pack_ids=["gta6"]).check(TARGET)
    probe = _console()
    probe.print(verdict_card(verdict), width=WIDTH_COLS)
    card_text = probe.export_text()
    card_lines = card_text.count("\n")
    total = card_lines + 2

    def typed(n: int):  # type: ignore[no-untyped-def]
        def p(con: Console) -> int:
            con.print(f"[bold #3CFFB0]$[/] {COMMAND[:n]}[reverse] [/]", highlight=False)
            return 1

        return p

    def full(con: Console) -> int:
        con.print(f"[bold #3CFFB0]$[/] {COMMAND}", highlight=False)
        con.print(verdict_card(verdict), width=WIDTH_COLS)
        return 1 + card_lines

    frames: list[tuple[Image.Image, int]] = []
    for n in range(0, len(COMMAND) + 1, 3):
        frames.append((_png(_svg(typed(n), total)), 45))
    frames.append((_png(_svg(typed(len(COMMAND)), total)), 450))
    frames.append((_png(_svg(full, total)), 4800))
    images = [f for f, _ in frames]
    durations = [d for _, d in frames]
    pal = images[-1].quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    quantized = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in images]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    quantized[0].save(
        OUT, save_all=True, append_images=quantized[1:], duration=durations, loop=0, optimize=True
    )
    total_ms = sum(durations)
    print(
        f"wrote {OUT} ({len(images)} frames, {total_ms / 1000:.1f}s, {OUT.stat().st_size // 1024} KiB)"
    )
    return 0 if total_ms <= 8000 else 1


if __name__ == "__main__":
    sys.exit(main())
