from __future__ import annotations
from dataclasses import dataclass

from .board import BLACK, RED, Board, Move, opponent, piece_color
from .parser import format_coord
from .rules import PIECE_VALUES, is_in_check, legal_moves

MATE_SCORE = 1_000_000
CHECK_BONUS = 120

FILE_BONUS = [3, 2, 1, 0, 1, 2, 3, 2, 3]

PIECE_SQUARE_BONUS = {
    "K": 0,
    "A": 8,
    "B": 6,
    "N": 18,
    "R": 14,
    "C": 12,
    "P": 10,
}


@dataclass(slots=True)
class CandidateMove:
    move: Move
    score: int


def choose_move(board: Board, color: str, depth: int = 2) -> tuple[Move | None, str]:
    ranked = rank_moves(board, color, depth)
    if not ranked:
        return None, "没有合法走法"
    best = ranked[0]
    return best.move, f"搜索评分 {best.score}"


async def choose_move_with_mode(
    board: Board,
    color: str,
    depth: int,
    mode: str | None = None,
    provider=None,
    provider_model: str | None = None,
    top_k: int = 0,
    xqwlight_jar_path: str | None = None,
    xqwlight_depth: int = 8,
    xqwlight_timeout_ms: int = 1500,
) -> tuple[Move | None, str]:
    del provider, provider_model, top_k
    if (mode or "builtin").lower() == "xqwlight":
        try:
            from .xqwlight_adapter import choose_move_xqwlight

            return await choose_move_xqwlight(
                board=board,
                color=color,
                jar_path=xqwlight_jar_path,
                depth=xqwlight_depth,
                timeout_ms=xqwlight_timeout_ms,
            )
        except Exception as exc:
            move, reason = choose_move(board, color, depth)
            fallback = f"xqwlight失败，已回退内置AI：{exc}"
            return move, f"{fallback}；{reason}" if reason else fallback
    return choose_move(board, color, depth)


def rank_moves(board: Board, color: str, depth: int = 2) -> list[CandidateMove]:
    moves = legal_moves(board, color)
    if not moves:
        return []

    max_depth = max(1, depth)
    ranked: list[CandidateMove] = []
    ordered = _order_moves(board, moves, color)
    alpha = -MATE_SCORE
    beta = MATE_SCORE

    for move in ordered:
        trial = board.clone()
        trial.apply_move(move.from_pos, move.to_pos)
        terminal = _terminal_general_score(trial, color)
        if terminal is None:
            score = -_negamax(trial, opponent(color), max_depth - 1, -beta, -alpha)
        else:
            score = _terminal_score(terminal, max_depth - 1)
        ranked.append(CandidateMove(move=move, score=score))
        if score > alpha:
            alpha = score

    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked


def render_ascii_board(board: Board) -> str:
    rows: list[str] = []
    for y, row in enumerate(board.grid):
        cells = []
        for piece in row:
            cells.append(piece if piece is not None else ".")
        rows.append(f"{y} " + " ".join(cells))
    rows.append("  a b c d e f g h i")
    return "\n".join(rows)


def describe_move(move: Move) -> str:
    return f"{format_coord(move.from_pos)} -> {format_coord(move.to_pos)}"


def _negamax(board: Board, to_move: str, depth: int, alpha: int, beta: int) -> int:
    terminal = _terminal_general_score(board, to_move)
    if terminal is not None:
        return _terminal_score(terminal, depth)
    if depth <= 0:
        return _evaluate(board, to_move)

    moves = legal_moves(board, to_move)
    if not moves:
        if _safe_is_in_check(board, to_move):
            return -MATE_SCORE - depth
        return _evaluate(board, to_move)

    best = -MATE_SCORE
    for move in _order_moves(board, moves, to_move):
        trial = board.clone()
        trial.apply_move(move.from_pos, move.to_pos)
        score = -_negamax(trial, opponent(to_move), depth - 1, -beta, -alpha)
        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
    return best


def _order_moves(board: Board, moves: list[Move], color: str) -> list[Move]:
    return sorted(moves, key=lambda move: _move_order_score(board, move, color), reverse=True)


def _move_order_score(board: Board, move: Move, color: str) -> int:
    score = 0
    if move.captured is not None:
        score += PIECE_VALUES[move.captured.upper()] * 16 - PIECE_VALUES[move.piece.upper()] * 2

    trial = board.clone()
    trial.apply_move(move.from_pos, move.to_pos)
    terminal = _terminal_general_score(trial, color)
    if terminal is not None:
        return terminal
    if _safe_is_in_check(trial, opponent(color)):
        score += 400
    if _safe_is_in_check(trial, color):
        score -= 500

    score += _piece_activity_bonus(move.piece, move.to_pos, color)
    if _is_square_attacked(trial, move.to_pos, opponent(color)):
        score -= PIECE_VALUES[move.piece.upper()] * 3
    return score


def _evaluate(board: Board, color: str) -> int:
    terminal = _terminal_general_score(board, color)
    if terminal is not None:
        return terminal

    score = 0
    for y, row in enumerate(board.grid):
        for x, piece in enumerate(row):
            if piece is None:
                continue
            piece_side = piece_color(piece)
            piece_score = PIECE_VALUES[piece.upper()] * 10
            piece_score += _piece_activity_bonus(piece, (x, y), piece_side)
            piece_score += _piece_structure_bonus(board, piece, (x, y), piece_side)
            if piece_side == color:
                score += piece_score
            else:
                score -= piece_score

    my_moves = legal_moves(board, color)
    enemy_color = opponent(color)
    enemy_moves = legal_moves(board, enemy_color)
    score += (len(my_moves) - len(enemy_moves)) * 3

    if _safe_is_in_check(board, color):
        score -= CHECK_BONUS
    if _safe_is_in_check(board, enemy_color):
        score += CHECK_BONUS

    score += _general_safety(board, color)
    score -= _general_safety(board, enemy_color)
    return score


def _piece_activity_bonus(piece: str, pos: tuple[int, int], color: str) -> int:
    x, y = pos
    mirrored_y = y if color == BLACK else 9 - y
    kind = piece.upper()

    if kind == "P":
        river_bonus = 18 if mirrored_y >= 5 else 6
        forward_bonus = mirrored_y * 2
        return river_bonus + forward_bonus + FILE_BONUS[x]
    if kind == "N":
        return 14 - abs(4 - x) * 2 + min(mirrored_y, 9 - mirrored_y)
    if kind == "R":
        return 10 - abs(4 - x) + min(mirrored_y, 9 - mirrored_y)
    if kind == "C":
        return 8 - abs(4 - x) + min(mirrored_y, 9 - mirrored_y)
    if kind in {"A", "B"}:
        return PIECE_SQUARE_BONUS[kind] - abs(4 - x)
    return PIECE_SQUARE_BONUS.get(kind, 0)


def _piece_structure_bonus(board: Board, piece: str, pos: tuple[int, int], color: str) -> int:
    bonus = 0
    x, y = pos
    kind = piece.upper()

    if kind == "P" and _is_square_attacked(board, pos, opponent(color)):
        bonus -= 8
    if kind in {"R", "C", "N"} and _is_square_attacked(board, pos, opponent(color)):
        bonus -= PIECE_VALUES[kind]
    if kind in {"R", "C"}:
        bonus += _open_file_bonus(board, x, y)
    return bonus


def _open_file_bonus(board: Board, x: int, y: int) -> int:
    blockers = 0
    for scan_y in range(10):
        if scan_y == y:
            continue
        if board.get_piece((x, scan_y)) is not None:
            blockers += 1
    if blockers <= 1:
        return 10
    if blockers <= 3:
        return 4
    return 0


def _general_safety(board: Board, color: str) -> int:
    if not _has_general(board, color):
        return -MATE_SCORE
    gx, gy = board.find_general(color)
    safety = 24
    for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        nx, ny = gx + dx, gy + dy
        if not (0 <= nx < 9 and 0 <= ny < 10):
            continue
        piece = board.get_piece((nx, ny))
        if piece is not None and piece_color(piece) == color:
            safety += 6
        elif _is_square_attacked(board, (nx, ny), opponent(color)):
            safety -= 10
    if _is_square_attacked(board, (gx, gy), opponent(color)):
        safety -= 20
    return safety


def _is_square_attacked(board: Board, pos: tuple[int, int], attacker_color: str) -> bool:
    if _terminal_general_score(board, attacker_color) is not None:
        return False
    for move in legal_moves(board, attacker_color):
        if move.to_pos == pos:
            return True
    return False


def _has_general(board: Board, color: str) -> bool:
    return board.has_general(color)


def _terminal_general_score(board: Board, perspective_color: str) -> int | None:
    red_alive = _has_general(board, RED)
    black_alive = _has_general(board, BLACK)
    if red_alive and black_alive:
        return None
    if not red_alive and not black_alive:
        return 0
    winner = RED if red_alive else BLACK
    return MATE_SCORE if winner == perspective_color else -MATE_SCORE


def _terminal_score(score: int, depth: int) -> int:
    if score > 0:
        return score + depth
    if score < 0:
        return score - depth
    return 0


def _safe_is_in_check(board: Board, color: str) -> bool:
    if not _has_general(board, color):
        return True
    enemy = opponent(color)
    if not _has_general(board, enemy):
        return False
    return is_in_check(board, color)
