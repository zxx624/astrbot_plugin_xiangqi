from __future__ import annotations

import re


COORD_RE = re.compile(r"^[a-i][0-9]$")


class ParseError(ValueError):
    pass


def parse_coord(text: str) -> tuple[int, int]:
    value = text.strip().lower()
    if not COORD_RE.fullmatch(value):
        raise ParseError("坐标格式错误，应为类似 e3 的形式")
    return ord(value[0]) - ord("a"), int(value[1])


def format_coord(pos: tuple[int, int]) -> str:
    x, y = pos
    return f"{chr(ord('a') + x)}{y}"
