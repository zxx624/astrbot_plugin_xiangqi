from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


RED = "red"
BLACK = "black"
BOARD_WIDTH = 9
BOARD_HEIGHT = 10

PIECE_NAMES = {
    "K": "帅",
    "A": "仕",
    "B": "相",
    "N": "马",
    "R": "车",
    "C": "炮",
    "P": "兵",
    "k": "将",
    "a": "士",
    "b": "象",
    "n": "马",
    "r": "车",
    "c": "炮",
    "p": "卒",
}

INITIAL_BOARD = [
    list("rnbakabnr"),
    [None] * 9,
    [None, "c", None, None, None, None, None, "c", None],
    ["p", None, "p", None, "p", None, "p", None, "p"],
    [None] * 9,
    [None] * 9,
    ["P", None, "P", None, "P", None, "P", None, "P"],
    [None, "C", None, None, None, None, None, "C", None],
    [None] * 9,
    list("RNBAKABNR"),
]


def piece_color(piece: str | None) -> str | None:
    if piece is None:
        return None
    return RED if piece.isupper() else BLACK


def opponent(color: str) -> str:
    return BLACK if color == RED else RED


def in_bounds(x: int, y: int) -> bool:
    return 0 <= x < BOARD_WIDTH and 0 <= y < BOARD_HEIGHT


@dataclass(slots=True)
class Move:
    from_pos: tuple[int, int]
    to_pos: tuple[int, int]
    piece: str
    captured: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_pos": list(self.from_pos),
            "to_pos": list(self.to_pos),
            "piece": self.piece,
            "captured": self.captured,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Move":
        return cls(
            from_pos=tuple(data["from_pos"]),
            to_pos=tuple(data["to_pos"]),
            piece=data["piece"],
            captured=data.get("captured"),
        )


@dataclass(slots=True)
class Board:
    grid: list[list[str | None]] = field(default_factory=lambda: [row[:] for row in INITIAL_BOARD])
    side_to_move: str = RED
    player_color: str = RED
    last_move: Move | None = None
    history: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def new_game(cls, player_color: str = RED) -> "Board":
        return cls(player_color=player_color)

    def clone(self) -> "Board":
        return Board(
            grid=[row[:] for row in self.grid],
            side_to_move=self.side_to_move,
            player_color=self.player_color,
            last_move=None if self.last_move is None else Move.from_dict(self.last_move.to_dict()),
            history=[entry.copy() for entry in self.history],
        )

    def get_piece(self, pos: tuple[int, int]) -> str | None:
        x, y = pos
        return self.grid[y][x]

    def set_piece(self, pos: tuple[int, int], piece: str | None) -> None:
        x, y = pos
        self.grid[y][x] = piece

    def snapshot(self) -> dict[str, Any]:
        return {
            "grid": [row[:] for row in self.grid],
            "side_to_move": self.side_to_move,
            "player_color": self.player_color,
            "last_move": None if self.last_move is None else self.last_move.to_dict(),
        }

    def restore(self, state: dict[str, Any]) -> None:
        self.grid = [row[:] for row in state["grid"]]
        self.side_to_move = state["side_to_move"]
        self.player_color = state.get("player_color", RED)
        last_move = state.get("last_move")
        self.last_move = None if last_move is None else Move.from_dict(last_move)

    def push_state(self) -> None:
        self.history.append(self.snapshot())

    def pop_state(self) -> bool:
        if not self.history:
            return False
        self.restore(self.history.pop())
        return True

    def apply_move(self, from_pos: tuple[int, int], to_pos: tuple[int, int]) -> Move:
        piece = self.get_piece(from_pos)
        captured = self.get_piece(to_pos)
        if piece is None:
            raise ValueError("起点没有棋子")
        move = Move(from_pos=from_pos, to_pos=to_pos, piece=piece, captured=captured)
        self.set_piece(to_pos, piece)
        self.set_piece(from_pos, None)
        self.last_move = move
        self.side_to_move = opponent(self.side_to_move)
        return move

    def has_general(self, color: str) -> bool:
        target = "K" if color == RED else "k"
        return any(piece == target for row in self.grid for piece in row)

    def find_general(self, color: str) -> tuple[int, int]:
        target = "K" if color == RED else "k"
        for y, row in enumerate(self.grid):
            for x, piece in enumerate(row):
                if piece == target:
                    return x, y
        raise ValueError("将帅不存在，棋局状态异常")

    def to_dict(self) -> dict[str, Any]:
        return {
            "grid": [row[:] for row in self.grid],
            "side_to_move": self.side_to_move,
            "player_color": self.player_color,
            "last_move": None if self.last_move is None else self.last_move.to_dict(),
            "history": [entry.copy() for entry in self.history],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Board":
        board = cls(
            grid=[row[:] for row in data["grid"]],
            side_to_move=data["side_to_move"],
            player_color=data.get("player_color", RED),
        )
        last_move = data.get("last_move")
        board.last_move = None if last_move is None else Move.from_dict(last_move)
        board.history = [entry.copy() for entry in data.get("history", [])]
        return board
