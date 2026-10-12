"""Merge an upright family (Regular/Bold) with an italic family (Italic/Bold Italic)

Each font directory is searched recursively for "<prefix>-.otf|ttf". Faces are chosen by
OS/2 weight, italic flag and normal width, SemiWide cuts are skipped, not
by file name, so renamed styles between releases don't matter.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from fontTools.ttLib import TTFont, TTLibError

# OS/2 fsSelection bits
ITALIC: Final[int] = 1 << 0
BOLD: Final[int] = 1 << 5
REGULAR: Final[int] = 1 << 6

# head.macStyle bits
MAC_BOLD: Final[int] = 1 << 0
MAC_ITALIC: Final[int] = 1 << 1


NORMAL_WIDTH: Final[int] = 5
FONT_SUFFIXES: Final[frozenset[str]] = frozenset({".otf", ".ttf"})
NAME_IDS: Final[tuple[int, ...]] = (1, 2, 3, 4, 6, 16, 17, 21, 22, 25)

# (platformID,platformEncID,langID): Windows/Unicode/en-US and Mac/Roman/English
NAME_PLATFORMS: Final[tuple[tuple[int, int, int], ...]] = ((3, 1, 0x409), (1, 0, 0))


class FaceNotFoundErr(Exception):
    """No face in the directory matches the requested style"""


@dataclass(frozen=True)
class Args:
    out_dir: Path
    family: str
    upright_prefix: str
    italic_prefix: str
    src_dirs: tuple[Path, ...]


@dataclass(frozen=True)
class Style:
    """One face of merged family and where it comes from."""

    source_prefix: str
    name: str
    weight: int
    italic: bool
    fs_selection: int
    mac_style: int


def parse_args(argv: Sequence[str] | None = None) -> Args:
    parser = argparse.ArgumentParser((__doc__ or "").split("\n", 1)[0])
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("family")
    parser.add_argument("upright_prefix")
    parser.add_argument("italic_prefix")
    parser.add_argument("src_dirs", type=Path, nargs="+")
    ns = parser.parse_args(argv)
    for label, value in (
        ("family", ns.family),
        ("upright prefix", ns.upright_prefix),
        ("italic prefix", ns.italic_prefix),
    ):
        if not value.strip():
            parser.error(f"{label} must not be empty")

    missing = [str(d) for d in ns.src_dirs if not d.is_dir()]
    if missing:
        parser.error(f"Not a directory: {', '.join(missing)}")

    return Args(
        out_dir=ns.out_dir,
        family=ns.family,
        upright_prefix=ns.upright_prefix,
        italic_prefix=ns.italic_prefix,
        src_dirs=tuple(ns.src_dirs),
    )


def build_styles(args: Args) -> tuple[Style, ...]:
    return (
        Style(args.upright_prefix, "Regular", 400, False, REGULAR, 0),
        Style(args.upright_prefix, "Bold", 700, False, BOLD, MAC_BOLD),
        Style(args.italic_prefix, "Italic", 400, True, ITALIC, MAC_ITALIC),
        Style(
            args.italic_prefix,
            "Bold Italic",
            700,
            True,
            ITALIC | BOLD,
            MAC_BOLD | MAC_ITALIC,
        ),
    )


def candidates(src_dirs: Sequence[Path], prefix: str) -> list[Path]:
    return sorted(
        path
        for dir in src_dirs
        for path in dir.rglob(f"{prefix}-*")
        if path.suffix in FONT_SUFFIXES
    )


def find_face(src_dirs: Sequence[Path], style: Style) -> tuple[Path, TTFont]:
    found = candidates(src_dirs, style.source_prefix)
    for path in found:
        try:
            font = TTFont(path)
            os2 = font["OS/2"]
        except (TTLibError, KeyError, OSError) as err:
            print(f"warning: skipping unreadable font {path}:{err}", file=sys.stderr)
            continue
        if (
            os2.usWeightClass == style.weight
            and bool(os2.fsSelection & ITALIC) == style.italic
            and os2.usWidthClass == NORMAL_WIDTH
        ):
            return path, font
        else:
            font.close()

    seen = ", ".join(p.name for p in found) or "(none)"
    raise FaceNotFoundErr(
        f"no '{style.source_prefix}-*' face with weight={style.weight}"
        f"italic={style.italic}, width=normal in {[str(d) for d in src_dirs]}; saw: {seen}"
    )


def make_ps_name(family: str, style_name: str) -> str:
    raw = f"{family}-{style_name}".replace(" ", "")
    sanitized = re.sub(r"[^A-Za-z0-9_.-]", "", raw)
    if not sanitized:
        raise ValueError(f"resulting Postscript name for family '{family}' is invalid")
    return sanitized


def rename(font: TTFont, family: str, style_name: str, ps_name: str) -> None:
    """Style-linke naming: nameID 1/2 only so apps only see fourface family"""
    names = font["name"]
    for name_id in NAME_IDS:
        names.removeNames(nameID=name_id)

    records = (
        (1, family),
        (2, style_name),
        (3, ps_name),
        (4, f"{family} {style_name}"),
        (6, ps_name),
    )
    for platform_id, enc_id, lang_id in NAME_PLATFORMS:
        for name_id, value in records:
            names.setName(value, name_id, platform_id, enc_id, lang_id)


def apply_style_flags(font: TTFont, style: Style, ps_name: str) -> None:
    os2 = font["OS/2"]
    os2.fsSelection = (
        os2.fsSelection & ~(ITALIC | BOLD | REGULAR)
    ) | style.fs_selection
    head = font["head"]
    head.macStyle = (head.macStyle & ~(MAC_BOLD | MAC_ITALIC)) | style.mac_style
    if "CFF " in font:
        font["CFF "].cff.fontNames = [ps_name]


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    styles = build_styles(args)
    resolved_faces: list[tuple[Style, Path, TTFont]] = []
    try:
        for style in styles:
            source, font = find_face(args.src_dirs, style)
            resolved_faces.append((style, source, font))
    except FaceNotFoundErr as err:
        print(f"error: {err}", file=sys.stderr)
        for _, _, font in resolved_faces:
            try:
                font.close()
            except (OSError, TTLibError, AttributeError) as close_err:
                print(
                    f"warning: failing to close font resource: {close_err}",
                    file=sys.stderr,
                )

        return 1
    try:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        for style, source, font in resolved_faces:
            ps_name = make_ps_name(args.family, style.name)
            rename(font, args.family, style.name, ps_name)
            apply_style_flags(font, style, ps_name)
            out = args.out_dir / f"{ps_name}{source.suffix}"
            font.save(out)
            font.close()
            print(f"{source.name:44} -> {out.name}")

    except (OSError, TTLibError, ValueError) as err:
        print(f"error during font compilation/saving: {err}", file=sys.stderr)
        for _, _, font in resolved_faces:
            try:
                font.close()
            except (OSError, TTLibError, AttributeError) as close_err:
                print(
                    f"warning: failing to close font resource: {close_err}",
                    file=sys.stderr,
                )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
