from __future__ import annotations

import asyncio
import random
import re
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
        talk_lines = None
        if bot_move is not None:
            board.push_state()
            board.apply_move(bot_move.from_pos, bot_move.to_pos)
            message += f" Bot 先手：{describe_move(bot_move)}"
            if reason:
                message += f"（{reason}）"
            talk_lines = await self._generate_bot_talk(event, board, bot_move, reason, RED)
        self.store.save(session_id, board)
        yield event.plain_result(message)
        if talk_lines:
            for talk_line in talk_lines:
                yield event.plain_result(f"「{talk_line}」")
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
        talk_lines = await self._generate_bot_talk(event, board, bot_move, bot_reason, bot_color)

        if is_in_check(board, player_color):
            message_parts.append("你现在被将军。")
        if self._append_endgame_message(board, player_color, message_parts, winner_is_player=False):
            self.store.delete(session_id)
        else:
            self.store.save(session_id, board)

        yield event.plain_result(" ".join(message_parts))
        if talk_lines:
            for talk_line in talk_lines:
                yield event.plain_result(f"「{talk_line}」")
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
        backend = self._ai_backend()
        yield event.plain_result(f"你执{player}，当前轮到{side}。AI：{backend}，搜索深度：{self._ai_depth()}")

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

    def _ai_backend(self) -> str:
        backend = str(self.config.get("ai_backend", "xqwlight") or "xqwlight").lower()
        return "xqwlight" if backend == "xqwlight" else "builtin"

    def _xqwlight_depth(self) -> int:
        depth = int(self.config.get("xqwlight_depth", 8) or 8)
        if depth < 1:
            return 1
        if depth > 12:
            return 12
        return depth

    def _xqwlight_timeout_ms(self) -> int:
        timeout = int(self.config.get("xqwlight_timeout_ms", 1500) or 1500)
        if timeout < 200:
            return 200
        if timeout > 10000:
            return 10000
        return timeout

    def _xqwlight_jar_path(self) -> str | None:
        value = str(self.config.get("xqwlight_jar_path", "") or "").strip()
        return value or None

    def _image_scale(self) -> int:
        scale = int(self.config.get("image_scale", 1) or 1)
        return 1 if scale <= 1 else 2

    def _llm_talk_enabled(self) -> bool:
        return bool(self.config.get("llm_talk_enabled", True))

    def _llm_persona_prompt(self) -> str:
        return str(
            self.config.get(
                "llm_persona_prompt",
                "你是发作，一个正在群里和人下中国象棋的女孩子。你棋力不错，嘴上不饶人但不低俗；像熟人聊天，有情绪、有小得意、会吐槽，也会偶尔认真分析。不要像客服，不要说'作为AI'，不要解释你是机器人。",
            )
            or ""
        ).strip()

    def _llm_talk_timeout(self) -> float:
        try:
            value = float(self.config.get("llm_talk_timeout", 5) or 5)
        except (TypeError, ValueError):
            value = 5
        return max(1.0, min(value, 15.0))

    def _llm_talk_sentence_count(self) -> int:
        try:
            max_count = int(self.config.get("llm_talk_max_sentences", 3) or 3)
        except (TypeError, ValueError):
            max_count = 3
        max_count = max(1, min(max_count, 3))
        return random.randint(1, max_count)

    def _llm_talk_max_chars(self) -> int:
        try:
            value = int(self.config.get("llm_talk_max_chars", 50) or 50)
        except (TypeError, ValueError):
            value = 50
        return max(10, min(value, 100))

    def _llm_provider_id(self) -> str | None:
        value = str(self.config.get("llm_provider_id", "") or "").strip()
        return value or None

    def _llm_model(self) -> str | None:
        value = str(self.config.get("llm_model", "") or "").strip()
        return value or None

    async def _choose_bot_move(self, board: Board, color: str):
        return await choose_move_with_mode(
            board=board,
            color=color,
            depth=self._ai_depth(),
            mode=self._ai_backend(),
            xqwlight_jar_path=self._xqwlight_jar_path(),
            xqwlight_depth=self._xqwlight_depth(),
            xqwlight_timeout_ms=self._xqwlight_timeout_ms(),
        )

    def _apply_player_move(self, board: Board, from_pos, to_pos, color):
        from .engine.rules import apply_legal_move

        return apply_legal_move(board, from_pos, to_pos, color)

    def _get_llm_provider(self, event: AstrMessageEvent):
        provider_id = self._llm_provider_id()
        if provider_id:
            try:
                provider = self.context.get_provider_by_id(provider_id)
                if provider:
                    return provider
            except Exception as exc:
                logger.warning("xiangqi llm talk skipped: provider id %s unavailable: %s", provider_id, exc)
        try:
            return self.context.get_using_provider(umo=getattr(event, "unified_msg_origin", None))
        except Exception as exc:
            logger.warning("xiangqi llm talk skipped: no provider: %s", exc)
            return None

    async def _generate_bot_talk(
        self,
        event: AstrMessageEvent,
        board: Board,
        bot_move,
        bot_reason: str | None,
        bot_color: str,
    ) -> list[str] | None:
        if not self._llm_talk_enabled():
            return None
        persona = self._llm_persona_prompt()
        if not persona:
            return None
        provider = self._get_llm_provider(event)
        if provider is None:
            return None

        sentence_count = self._llm_talk_sentence_count()
        prompt = self._build_talk_prompt(board, bot_move, bot_reason, bot_color, sentence_count)
        session_id = f"xiangqi_talk_{self._session_id(event)}"
        try:
            response = await asyncio.wait_for(
                provider.text_chat(
                    prompt=prompt,
                    contexts=[],
                    system_prompt=persona,
                    session_id=session_id,
                    model=self._llm_model(),
                    func_tool=None,
                    tool_choice="auto",
                ),
                timeout=self._llm_talk_timeout(),
            )
        except TypeError:
            try:
                response = await asyncio.wait_for(
                    provider.text_chat(
                        prompt=f"{persona}\n\n{prompt}",
                        contexts=[],
                        session_id=session_id,
                        func_tool=None,
                        tool_choice="auto",
                    ),
                    timeout=self._llm_talk_timeout(),
                )
            except Exception as exc:
                logger.warning("xiangqi llm talk failed: %s", exc)
                return None
        except Exception as exc:
            logger.warning("xiangqi llm talk failed: %s", exc)
            return None

        text = str(getattr(response, "completion_text", "") or "").strip()
        return self._clean_llm_talk(text, sentence_count)

    def _build_talk_prompt(
        self,
        board: Board,
        bot_move,
        bot_reason: str | None,
        bot_color: str,
        sentence_count: int,
    ) -> str:
        bot_side = "红方" if bot_color == RED else "黑方"
        player_color = opponent(bot_color)
        player_in_check = is_in_check(board, player_color)
        captured = f"，吃掉{bot_move.captured}" if getattr(bot_move, "captured", None) else ""
        board_text = self._ascii_board(board)
        max_chars = self._llm_talk_max_chars()
        return (
            "你刚刚在中国象棋对局中完成了一步走棋。\n"
            f"你执{bot_side}，刚走：{describe_move(bot_move)}{captured}。\n"
            f"引擎信息：{bot_reason or '无'}。\n"
            f"对手当前{'被将军' if player_in_check else '没有被将军'}。\n"
            f"当前棋盘，0行是黑方底线，9行是红方底线：\n{board_text}\n\n"
            "写法要求：\n"
            f"- 只输出{sentence_count}句中文台词，每句单独一行，每句最多{max_chars}字。\n"
            "- 语气像群里真人下棋：自然、松弛、有一点情绪和胜负欲。\n"
            "- 可以嘴硬、得意、吐槽、试探、装作不在意，也可以简单点出这步棋的想法。\n"
            "- 不要每句都解释规则；不要像旁白/客服/机器人；不要说'我作为AI'。\n"
            "- 不要输出编号、JSON、引号、括号说明；不要替玩家走棋。"
        )

    def _ascii_board(self, board: Board) -> str:
        rows = []
        for y, row in enumerate(board.grid):
            rows.append(f"{y} " + " ".join(piece if piece is not None else "." for piece in row))
        rows.append("  a b c d e f g h i")
        return "\n".join(rows)

    def _clean_llm_talk(self, text: str, sentence_count: int) -> list[str] | None:
        text = text.replace("\r", "\n").strip()
        if not text:
            return None
        candidates: list[str] = []
        for raw_line in re.split(r"[\n]+", text):
            line = raw_line.strip()
            line = re.sub(r"^[-*•\s]*\d+[.、)）]\s*", "", line)
            line = re.sub(r"^[-*•]+\s*", "", line)
            for prefix in ("台词：", "台词:", "回复：", "回复:", "发作：", "发作:"):
                if line.startswith(prefix):
                    line = line[len(prefix) :].strip()
            line = line.strip("`\"'“”‘’「」")
            if line:
                candidates.append(line)

        if not candidates:
            fallback = text.replace("\n", " ").strip("`\"'“”‘’「」")
            if fallback:
                candidates = [fallback]

        max_chars = self._llm_talk_max_chars()
        cleaned: list[str] = []
        for line in candidates:
            line = re.sub(r"\s+", " ", line).strip()
            if not line:
                continue
            if len(line) > max_chars:
                line = line[:max_chars].rstrip("，。！？、 ") + "…"
            cleaned.append(line)
            if len(cleaned) >= sentence_count:
                break
        return cleaned or None

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
