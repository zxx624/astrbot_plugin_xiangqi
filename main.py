from __future__ import annotations

from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools

from .engine.ai import choose_move_with_mode, describe_move
from .engine.board import BLACK, RED, Board, opponent
from .engine.parser import ParseError, format_coord, parse_coord
from .engine.rules import IllegalMoveError, is_checkmate, is_in_check, is_stalemate
from .render.board_image import render_board
from .storage.session_store import SessionStore


class XiangqiPlugin(Star):
    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        self.data_dir: Path = StarTools.get_data_dir()
        self.store = SessionStore(self.data_dir)
        self.board_dir = self.data_dir / "boards"
        self.board_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or {}

    @filter.command("象棋新局")
    async def new_game(self, event: AstrMessageEvent):
        session_id = self._session_id(event)
        board = Board.new_game(player_color=RED)
        self.store.save(session_id, board)
        logger.info("xiangqi new game: %s", session_id)
        yield event.plain_result("新对局已开始，你执红先行。发送“走棋 b9 c7”即可落子。")
        yield event.image_result(str(self._render_session_board(session_id, board)))

    @filter.command("象棋执黑")
    async def new_game_black(self, event: AstrMessageEvent):
        session_id = self._session_id(event)
        board = Board.new_game(player_color=BLACK)
        bot_move, reason = await self._choose_bot_move(board, RED)
        message = "新对局已开始，你执黑。"
        if bot_move is not None:
            board.push_state()
            board.apply_move(bot_move.from_pos, bot_move.to_pos)
            message += f" Bot 先手：{describe_move(bot_move)}"
            if reason:
                message += f"（{reason}）"
        self.store.save(session_id, board)
        yield event.plain_result(message)
        yield event.image_result(str(self._render_session_board(session_id, board)))

    @filter.command("走棋")
    async def move(self, event: AstrMessageEvent, from_coord: str, to_coord: str):
        session_id = self._session_id(event)
        board = self.store.load(session_id)
        if board is None:
            yield event.plain_result('当前没有对局，请先发送“象棋新局”')
            return
        player_color = board.player_color
        if board.side_to_move != player_color:
            yield event.plain_result("当前不是你的回合，请稍后再试")
            return
        try:
            from_pos = parse_coord(from_coord)
            to_pos = parse_coord(to_coord)
            player_move = self._apply_player_move(board, from_pos, to_pos, player_color)
        except (ParseError, IllegalMoveError, ValueError) as exc:
            yield event.plain_result(str(exc))
            return

        message_parts = [f"你走了 {format_coord(player_move.from_pos)} -> {format_coord(player_move.to_pos)}"]
        if self._append_endgame_message(board, opponent(player_color), message_parts, winner_is_player=True):
            self.store.delete(session_id)
            yield event.plain_result(" ".join(message_parts))
            yield event.image_result(str(self._render_session_board(session_id, board)))
            return

        bot_color = opponent(player_color)
        bot_move, bot_reason = await self._choose_bot_move(board, bot_color)
        if bot_move is None:
            message_parts.append("Bot 无合法走法，本局结束。")
            self.store.delete(session_id)
            yield event.plain_result(" ".join(message_parts))
            yield event.image_result(str(self._render_session_board(session_id, board)))
            return

        board.push_state()
        board.apply_move(bot_move.from_pos, bot_move.to_pos)
        bot_message = f"Bot 走了 {describe_move(bot_move)}"
        if bot_reason:
            bot_message += f"（{bot_reason}）"
        message_parts.append(bot_message)

        if is_in_check(board, player_color):
            message_parts.append("你现在被将军。")
        if self._append_endgame_message(board, player_color, message_parts, winner_is_player=False):
            self.store.delete(session_id)
        else:
            self.store.save(session_id, board)

        yield event.plain_result(" ".join(message_parts))
        yield event.image_result(str(self._render_session_board(session_id, board)))

    @filter.command("棋盘")
    async def board(self, event: AstrMessageEvent):
        session_id = self._session_id(event)
        board = self.store.load(session_id)
        if board is None:
            yield event.plain_result('当前没有对局，请先发送“象棋新局”')
            return
        yield event.image_result(str(self._render_session_board(session_id, board)))

    @filter.command("悔棋")
    async def undo(self, event: AstrMessageEvent):
        session_id = self._session_id(event)
        board = self.store.load(session_id)
        if board is None:
            yield event.plain_result('当前没有对局，请先发送“象棋新局”')
            return
        if len(board.history) < 2:
            yield event.plain_result("当前没有可撤销的完整回合")
            return
        board.pop_state()
        board.pop_state()
        self.store.save(session_id, board)
        yield event.plain_result("已撤销上一整个回合")
        yield event.image_result(str(self._render_session_board(session_id, board)))

    @filter.command("认输")
    async def resign(self, event: AstrMessageEvent):
        session_id = self._session_id(event)
        board = self.store.load(session_id)
        if board is None:
            yield event.plain_result('当前没有对局，请先发送“象棋新局”')
            return
        self.store.delete(session_id)
        yield event.plain_result("你已认输，本局结束。")

    @filter.command("提示")
    async def hint(self, event: AstrMessageEvent):
        session_id = self._session_id(event)
        board = self.store.load(session_id)
        if board is None:
            yield event.plain_result('当前没有对局，请先发送“象棋新局”')
            return
        if board.side_to_move != board.player_color:
            yield event.plain_result("当前不是你的回合")
            return
        move, reason = await self._choose_bot_move(board, board.player_color)
        if move is None:
            yield event.plain_result("当前没有合法走法")
            return
        message = f"可以考虑：{describe_move(move)}"
        if reason:
            message += f"（{reason}）"
        yield event.plain_result(message)

    @filter.command("象棋状态")
    async def status(self, event: AstrMessageEvent):
        session_id = self._session_id(event)
        board = self.store.load(session_id)
        if board is None:
            yield event.plain_result('当前没有对局，请先发送“象棋新局”')
            return
        side = "红方" if board.side_to_move == RED else "黑方"
        player = "红方" if board.player_color == RED else "黑方"
        yield event.plain_result(f"你执{player}，当前轮到{side}。搜索深度：{self._ai_depth()}")

    async def terminate(self):
        return None

    def _session_id(self, event: AstrMessageEvent) -> str:
        origin = getattr(event, "unified_msg_origin", None)
        if origin:
            return str(origin)
        group_id = getattr(event, "get_group_id", lambda: None)()
        if group_id:
            return f"group:{group_id}"
        return f"user:{event.get_sender_id()}"

    def _render_session_board(self, session_id: str, board: Board) -> Path:
        filename = session_id.replace("/", "_").replace(":", "_") + ".png"
        return render_board(board, self.board_dir / filename, self._image_scale())

    def _ai_depth(self) -> int:
        depth = int(self.config.get("ai_depth", 2) or 2)
        if depth < 1:
            return 1
        if depth > 3:
            return 3
        return depth

    def _image_scale(self) -> int:
        scale = int(self.config.get("image_scale", 1) or 1)
        return 1 if scale <= 1 else 2

    async def _choose_bot_move(self, board: Board, color: str):
        return await choose_move_with_mode(
            board=board,
            color=color,
            depth=self._ai_depth(),
        )

    def _apply_player_move(self, board: Board, from_pos, to_pos, color):
        from .engine.rules import apply_legal_move

        return apply_legal_move(board, from_pos, to_pos, color)

    def _append_endgame_message(
        self,
        board: Board,
        color: str,
        message_parts: list[str],
        winner_is_player: bool,
    ) -> bool:
        if is_checkmate(board, color):
            message_parts.append("将死，恭喜获胜。" if winner_is_player else "你被将死，本局结束。")
            return True
        if is_stalemate(board, color):
            message_parts.append("对方无子可走，本局结束。" if winner_is_player else "你已无合法走法，本局结束。")
            return True
        return False
