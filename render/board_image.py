from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..engine.board import BLACK, RED, Board, PIECE_NAMES, piece_color
from ..engine.parser import format_coord


BOARD_COLOR = "#f2d39b"
LINE_COLOR = "#4f2f19"
RED_COLOR = "#bd3124"
BLACK_COLOR = "#262626"
HIGHLIGHT_COLOR = "#2c7a7b"


def render_board(board: Board, output_path: Path, scale: int = 1) -> Path:
    scale = max(1, min(scale, 2))
    cell = 68 * scale
    margin_x = 90 * scale
    margin_y = 80 * scale
    width = margin_x * 2 + cell * 8
    height = margin_y * 2 + cell * 9

    image = Image.new("RGB", (width, height), BOARD_COLOR)
    draw = ImageDraw.Draw(image)
    font_piece = _load_font(34 * scale)
    font_small = _load_font(20 * scale)
    font_title = _load_font(24 * scale)

    left = margin_x
    top = margin_y
    right = left + cell * 8
    bottom = top + cell * 9

    draw.rounded_rectangle((20 * scale, 20 * scale, width - 20 * scale, height - 20 * scale), radius=18 * scale, outline=LINE_COLOR, width=3)
    for x in range(9):
        px = left + x * cell
        draw.line((px, top, px, top + cell * 4), fill=LINE_COLOR, width=2)
        draw.line((px, top + cell * 5, px, bottom), fill=LINE_COLOR, width=2)
    for y in range(10):
        py = top + y * cell
        draw.line((left, py, right, py), fill=LINE_COLOR, width=2)

    draw.line((left + 3 * cell, top, left + 5 * cell, top + 2 * cell), fill=LINE_COLOR, width=2)
    draw.line((left + 5 * cell, top, left + 3 * cell, top + 2 * cell), fill=LINE_COLOR, width=2)
    draw.line((left + 3 * cell, bottom, left + 5 * cell, bottom - 2 * cell), fill=LINE_COLOR, width=2)
    draw.line((left + 5 * cell, bottom, left + 3 * cell, bottom - 2 * cell), fill=LINE_COLOR, width=2)

    river_text = "楚 河         汉 界"
    _draw_centered(draw, ((left + right) // 2, top + cell * 4 + cell // 2), river_text, font_title, LINE_COLOR)

    for idx in range(9):
        label = chr(ord("a") + idx)
        x = left + idx * cell
        _draw_centered(draw, (x, top - 30 * scale), label, font_small, LINE_COLOR)
        _draw_centered(draw, (x, bottom + 30 * scale), label, font_small, LINE_COLOR)
    for idx in range(10):
        y = top + idx * cell
        _draw_centered(draw, (left - 35 * scale, y), str(idx), font_small, LINE_COLOR)
        _draw_centered(draw, (right + 35 * scale, y), str(idx), font_small, LINE_COLOR)

    if board.last_move is not None:
        for pos in (board.last_move.from_pos, board.last_move.to_pos):
            _highlight_cell(draw, pos, left, top, cell)

    for y, row in enumerate(board.grid):
        for x, piece in enumerate(row):
            if piece is None:
                continue
            _draw_piece(draw, piece, (x, y), left, top, cell, font_piece)

    status = f"当前行棋: {'红方' if board.side_to_move == RED else '黑方'}"
    if board.last_move is not None:
        status += f"   最近一步: {format_coord(board.last_move.from_pos)} -> {format_coord(board.last_move.to_pos)}"
    draw.text((30 * scale, height - 50 * scale), status, fill=LINE_COLOR, font=font_small)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG")
    return output_path


def _draw_piece(draw: ImageDraw.ImageDraw, piece: str, pos: tuple[int, int], left: int, top: int, cell: int, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> None:
    x, y = pos
    cx = left + x * cell
    cy = top + y * cell
    radius = int(cell * 0.38)
    bbox = (cx - radius, cy - radius, cx + radius, cy + radius)
    fill = "#f8f0dc"
    outline = RED_COLOR if piece_color(piece) == RED else BLACK_COLOR
    text_color = outline
    draw.ellipse(bbox, fill=fill, outline=outline, width=3)
    _draw_centered(draw, (cx, cy), PIECE_NAMES[piece], font, text_color)


def _highlight_cell(draw: ImageDraw.ImageDraw, pos: tuple[int, int], left: int, top: int, cell: int) -> None:
    x, y = pos
    cx = left + x * cell
    cy = top + y * cell
    span = int(cell * 0.44)
    draw.rectangle((cx - span, cy - span, cx + span, cy + span), outline=HIGHLIGHT_COLOR, width=3)


def _draw_centered(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: str,
) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    draw.text((center[0] - width / 2, center[1] - height / 2), text, fill=fill, font=font)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()
