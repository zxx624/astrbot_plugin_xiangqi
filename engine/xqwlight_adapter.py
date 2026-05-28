from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from .board import BLACK, RED, Board, Move, piece_color
from .rules import legal_moves

DEFAULT_JAR_PATH = Path(__file__).resolve().parent / "bin" / "xqwlight-cli.jar"
FILES = "abcdefghi"


class XQWLightError(Exception):
    """Raised when the xqwlight helper cannot produce a valid move."""


def board_to_fen(board: Board, color: str) -> str:
    """Convert the plugin board to xqwlight-compatible Xiangqi FEN."""
    rows: list[str] = []
    for row in board.grid:
        empty = 0
        fen_row: list[str] = []
        for piece in row:
            if piece is None:
                empty += 1
                continue
            if empty:
                fen_row.append(str(empty))
                empty = 0
            fen_row.append(piece)
        if empty:
            fen_row.append(str(empty))
        rows.append("".join(fen_row))
    return "/".join(rows) + (" w" if color == RED else " b")


def parse_engine_move(text: str, board: Board, color: str) -> Move:
    """Parse xqwlight CLI output like h0g2 and return a validated plugin Move."""
    move_text = _extract_coord_move(text)
    if move_text is None:
        raise XQWLightError(f"引擎没有返回有效走法: {text.strip() or '<empty>'}")

    from_pos = _coord_to_pos(move_text[:2])
    to_pos = _coord_to_pos(move_text[2:])
    piece = board.get_piece(from_pos)
    if piece is None:
        raise XQWLightError(f"引擎走法起点无棋子: {move_text}")
    if piece_color(piece) != color:
        raise XQWLightError(f"引擎走了错误颜色棋子: {move_text}")

    for move in legal_moves(board, color):
        if move.from_pos == from_pos and move.to_pos == to_pos:
            return move
    raise XQWLightError(f"引擎返回非法走法: {move_text}")


async def choose_move_xqwlight(
    board: Board,
    color: str,
    jar_path: str | Path | None = None,
    depth: int = 8,
    timeout_ms: int = 1500,
) -> tuple[Move | None, str]:
    """Ask the bundled xqwlight Java engine for a legal move."""
    java_bin = shutil.which("java")
    if not java_bin:
        raise XQWLightError("未找到 java 命令")

    jar = Path(jar_path or DEFAULT_JAR_PATH)
    if not jar.is_absolute():
        jar = (Path(__file__).resolve().parent.parent / jar).resolve()
    if not jar.exists():
        raise XQWLightError(f"引擎 jar 不存在: {jar}")

    safe_depth = max(1, min(int(depth or 8), 12))
    safe_timeout_ms = max(200, min(int(timeout_ms or 1500), 10000))
    fen = board_to_fen(board, color)
    timeout_sec = safe_timeout_ms / 1000 + 1.0

    proc = await asyncio.create_subprocess_exec(
        java_bin,
        "-jar",
        str(jar),
        fen,
        str(safe_depth),
        str(safe_timeout_ms),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
    except asyncio.TimeoutError as exc:
        proc.kill()
        await proc.communicate()
        raise XQWLightError("引擎思考超时") from exc

    out = stdout.decode("utf-8", errors="ignore").strip()
    err = stderr.decode("utf-8", errors="ignore").strip()
    if proc.returncode != 0:
        raise XQWLightError(f"引擎退出异常: {err or out or proc.returncode}")

    move = parse_engine_move(out, board, color)
    return move, f"xqwlight depth {safe_depth}"


def _extract_coord_move(text: str) -> str | None:
    for token in text.replace("\r", "\n").split():
        token = token.strip().lower()
        if len(token) == 4 and token[0] in FILES and token[2] in FILES and token[1].isdigit() and token[3].isdigit():
            if 0 <= int(token[1]) <= 9 and 0 <= int(token[3]) <= 9:
                return token
    return None


def _coord_to_pos(coord: str) -> tuple[int, int]:
    if len(coord) != 2 or coord[0] not in FILES or not coord[1].isdigit():
        raise XQWLightError(f"坐标格式错误: {coord}")
    x = FILES.index(coord[0])
    y = int(coord[1])
    if y < 0 or y > 9:
        raise XQWLightError(f"坐标越界: {coord}")
    return x, y
