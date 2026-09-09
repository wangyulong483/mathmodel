# -*- coding: utf-8 -*-
"""Render a source file as a readable PNG for a paper appendix."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def find_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/consola.ttf"),
        Path("C:/Windows/Fonts/cour.ttf"),
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size)
            except OSError:
                continue
    return ImageFont.load_default()


def render_code_image(code: str, output: Path, font_size: int = 24, padding: int = 24) -> None:
    lines = code.expandtabs(4).splitlines() or [""]
    font = find_font(font_size)
    line_height = int(font_size * 1.45)
    widths = [font.getbbox(line)[2] - font.getbbox(line)[0] for line in lines]
    image = Image.new(
        "RGB",
        (max(widths, default=0) + padding * 2, line_height * len(lines) + padding * 2),
        "white",
    )
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(lines):
        draw.text((padding, padding + index * line_height), line, font=font, fill="black")
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, "PNG", dpi=(300, 300))
    print(f"[OK] {output} ({image.width}x{image.height})")


def main() -> int:
    parser = argparse.ArgumentParser(description="将 Python 源码渲染为附录 PNG")
    parser.add_argument("--input", required=True, help="源代码文件")
    parser.add_argument("--output", required=True, help="PNG 输出路径")
    parser.add_argument("--font-size", type=int, default=24)
    args = parser.parse_args()
    render_code_image(Path(args.input).read_text(encoding="utf-8"), Path(args.output), args.font_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
