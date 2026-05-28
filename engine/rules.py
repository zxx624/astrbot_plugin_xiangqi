from __future__ import annotations

from dataclasses import dataclass

from .board import BLACK, RED, Board, Move, in_bounds, opponent, piece_color


PIECE_VALUES = {
    "K": 10000,
    "A": 20,
    "B": 20,
    "N": 45,
    "R": 90,
    "C": 50,
    "P": 15,
}


class IllegalMoveError(ValueError):
    pass


@dataclass(slots=True)
class MoveCheck:
    ok: bool
    reason: str = ""
    move: Move | None = None


def palace_contains(color: str, x: int, y: int) -> bool:
    if x < 3 or x > 5:
        return False
    if color == BLACK:
        return 0 <= y <= 2
    return 7 <= y <= 9


def crossed_river(color: str, y: int) -> bool:
    return y <= 4 if color == RED else y >= 5


def count_between(board: Board, from_pos: tuple[int, int], to_pos: tuple[int, int]) -> int:
    fx, fy = from_pos
    tx, ty = to_pos
    count = 0
    if fx == tx:
        step = 1 if ty > fy else -1
        for y in range(fy + step, ty, step):
            if board.get_piece((fx, y)) is not None:
                count += 1
        return count
    if fy == ty:
        step = 1 if tx > fx else -1
        for x in range(fx + step, tx, step):
            if board.get_piece((x, fy)) is not None:
                count += 1
        return count
    return -1


def generals_facing(board: Board) -> bool:
    if not board.has_general(RED) or not board.has_general(BLACK):
        return False
    red_x, red_y = board.find_general(RED)
    black_x, black_y = board.find_general(BLACK)
    if red_x != black_x:
        return False
    step = 1 if black_y > red_y else -1
    for y in range(red_y + step, black_y, step):
        if board.get_piece((red_x, y)) is not None:
            return False
    return True


def can_piece_attack(board: Board, from_pos: tuple[int, int], target_pos: tuple[int, int]) -> bool:
    piece = board.get_piece(from_pos)
    if piece is None:
        return False
    try:
        _check_piece_rule(board, from_pos, target_pos, attacking_only=True)
        return True
    except IllegalMoveError:
        return False


def is_in_check(board: Board, color: str) -> bool:
    if not board.has_general(color):
        return True
    general_pos = board.find_general(color)
    enemy = opponent(color)
    if not board.has_general(enemy):
        return False
    for y, row in enumerate(board.grid):
        for x, piece in enumerate(row):
            if piece is None or piece_color(piece) != enemy:
                continue
            if can_piece_attack(board, (x, y), general_pos):
                return True
    return generals_facing(board)


def validate_move(board: Board, from_pos: tuple[int, int], to_pos: tuple[int, int], color: str) -> MoveCheck:
    piece = board.get_piece(from_pos)
    if piece is None:
        return MoveCheck(False, "起点没有棋子")
    if piece_color(piece) != color:
        return MoveCheck(False, "这不是你的棋子")
    target = board.get_piece(to_pos)
    if target is not None and piece_color(target) == color:
        return MoveCheck(False, "终点已有己方棋子")
    try:
        _check_piece_rule(board, from_pos, to_pos)
    except IllegalMoveError as exc:
        return MoveCheck(False, str(exc))

    trial = board.clone()
    move = trial.apply_move(from_pos, to_pos)
    if generals_facing(trial):
        return MoveCheck(False, "将帅不能对脸")
    if is_in_check(trial, color):
        return MoveCheck(False, "这步会让己方将帅暴露，不能走")
    return MoveCheck(True, move=move)


def _check_piece_rule(
    board: Board,
    from_pos: tuple[int, int],
    to_pos: tuple[int, int],
    attacking_only: bool = False,
) -> None:
    fx, fy = from_pos
    tx, ty = to_pos
    if not in_bounds(fx, fy) or not in_bounds(tx, ty):
        raise IllegalMoveError("坐标超出棋盘范围")
    if from_pos == to_pos:
        raise IllegalMoveError("起点和终点不能相同")
    piece = board.get_piece(from_pos)
    if piece is None:
        raise IllegalMoveError("起点没有棋子")
    target = board.get_piece(to_pos)
    color = piece_color(piece)
    dx = tx - fx
    dy = ty - fy
    kind = piece.upper()

    if kind == "R":
        if fx != tx and fy != ty:
            raise IllegalMoveError("该棋子不能这样走")
        if count_between(board, from_pos, to_pos) != 0:
            raise IllegalMoveError("路径被阻挡")
        return

    if kind == "N":
        if sorted((abs(dx), abs(dy))) != [1, 2]:
            raise IllegalMoveError("该棋子不能这样走")
        if abs(dx) == 2:
            leg = (fx + dx // 2, fy)
        else:
            leg = (fx, fy + dy // 2)
        if board.get_piece(leg) is not None:
            raise IllegalMoveError("路径被阻挡")
        return

    if kind == "B":
        if abs(dx) != 2 or abs(dy) != 2:
            raise IllegalMoveError("该棋子不能这样走")
        eye = (fx + dx // 2, fy + dy // 2)
        if board.get_piece(eye) is not None:
            raise IllegalMoveError("路径被阻挡")
        if color == RED and ty < 5:
            raise IllegalMoveError("相不能过河")
        if color == BLACK and ty > 4:
            raise IllegalMoveError("象不能过河")
        return

    if kind == "A":
        if abs(dx) != 1 or abs(dy) != 1 or not palace_contains(color, tx, ty):
            raise IllegalMoveError("该棋子不能这样走")
        return

    if kind == "K":
        if abs(dx) + abs(dy) != 1 or not palace_contains(color, tx, ty):
            raise IllegalMoveError("该棋子不能这样走")
        return

    if kind == "C":
        if fx != tx and fy != ty:
            raise IllegalMoveError("该棋子不能这样走")
        between = count_between(board, from_pos, to_pos)
        if target is None:
            if between != 0:
                raise IllegalMoveError("路径被阻挡")
        else:
            if between != 1:
                raise IllegalMoveError("炮吃子时必须隔恰好一个棋子")
        return

    if kind == "P":
        forward = -1 if color == RED else 1
        if dy == forward and dx == 0:
            return
        if crossed_river(color, fy) and dy == 0 and abs(dx) == 1:
            return
        if attacking_only and target is not None and crossed_river(color, fy) and dy == 0 and abs(dx) == 1:
            return
        raise IllegalMoveError("该棋子不能这样走")

    raise IllegalMoveError("未知棋子类型")


def legal_moves(board: Board, color: str) -> list[Move]:
    moves: list[Move] = []
    for y, row in enumerate(board.grid):
        for x, piece in enumerate(row):
            if piece is None or piece_color(piece) != color:
                continue
            for ty in range(10):
                for tx in range(9):
                    result = validate_move(board, (x, y), (tx, ty), color)
                    if result.ok and result.move is not None:
                        moves.append(result.move)
    return moves


def apply_legal_move(board: Board, from_pos: tuple[int, int], to_pos: tuple[int, int], color: str) -> Move:
    result = validate_move(board, from_pos, to_pos, color)
    if not result.ok:
        raise IllegalMoveError(result.reason)
    board.push_state()
    return board.apply_move(from_pos, to_pos)


def is_checkmate(board: Board, color: str) -> bool:
    state = general_state(board, color)
    if state == "missing_self":
        return True
    if state == "missing_enemy":
        return False
    return is_in_check(board, color) and not legal_moves(board, color)


def is_stalemate(board: Board, color: str) -> bool:
    if general_state(board, color) != "alive":
        return False
    return not is_in_check(board, color) and not legal_moves(board, color)


def general_state(board: Board, color: str) -> str:
    has_self = board.has_general(color)
    has_enemy = board.has_general(opponent(color))
    if not has_self:
        return "missing_self"
    if not has_enemy:
        return "missing_enemy"
    return "alive"


def evaluate_material(board: Board, color: str) -> int:
    score = 0
    for row in board.grid:
        for piece in row:
            if piece is None:
                continue
            value = PIECE_VALUES[piece.upper()]
            if piece_color(piece) == color:
                score += value
            else:
                score -= value
    return score
