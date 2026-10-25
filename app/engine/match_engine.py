import asyncio
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Awaitable, Callable
from app.engine.collisions import resolve_player_collisions
from app.engine.constants import PLAYER_RADIUS

from app.engine.action import NULL_ACTION, Action
from app.engine.tick_context import TickContext
from app.behaviors import executor
from app.engine.physics import (
    apply_kick, check_goal, move_player, resolve_possession, step_ball,
)
from app.engine.schedule import Segment, build_schedule
from app.engine.setup import reset_to_kickoff
from app.engine.state import GoalEvent, MatchPhase, MatchState, Team, Vec2

logger = logging.getLogger(__name__)


class MatchEngine:
    def __init__(self, state: MatchState, field, cfg, behavior_ids: dict[str, str], schedule: list[Segment] | None = None, rng: random.Random | None = None,
        on_finish: Callable[[MatchState], Awaitable[None]] | None = None,
        realtime: bool = True,) -> None:
        self.state = state
        self.field = field
        self.cfg = cfg
        self.behavior_ids = behavior_ids
        self.dt = 1.0 / cfg.match_tick_rate
        self.schedule = schedule or build_schedule(
            cfg.friendly_match_duration_seconds, cfg.match_tick_rate
        )
        self.rng = rng or random.Random()
        self.on_finish = on_finish
        self.realtime = realtime          # False en tests: sin esperas
        self._segment_index = 0
        self._pool = ThreadPoolExecutor(
            max_workers=len(state.players), thread_name_prefix="bot"
        )
        self._busy: dict[str, asyncio.Future] = {}
        self.pending_substitution = {Team.HOME: None, Team.AWAY: None}
        self.changes_used_this_pause = {Team.HOME: 0, Team.AWAY: 0}
        self.ws_events: list[dict] = []
        self.coach_active = {Team.HOME: False, Team.AWAY: False}
        self._starters_by_team = {
            Team.HOME: {p.id for p in state.players if p.team == Team.HOME},
            Team.AWAY: {p.id for p in state.players if p.team == Team.AWAY},
        }
        self._bench_by_team = {Team.HOME: set(), Team.AWAY: set()}

    async def _collect_actions(self) -> dict[str, Action]:
        ctx = TickContext(self.state, self.field, self.behavior_ids)
        loop = asyncio.get_running_loop()

        # 1. Lanzar los bots que no estén ocupados del tick anterior
        launched: dict[str, asyncio.Future] = {}
        for p in self.state.players:
            if p.id in self._busy:
                continue                      # sigue colgado: acción nula
            fut = loop.run_in_executor(
                self._pool, executor.ejecutar_comportamiento, p.id, ctx
            )
            self._busy[p.id] = fut
            fut.add_done_callback(lambda _f, pid=p.id: self._busy.pop(pid, None))
            launched[p.id] = fut

        # 2. Esperar a todos con UN solo presupuesto de tiempo
        if launched:
            await asyncio.wait(
                launched.values(), timeout=self.cfg.behavior_timeout_seconds
            )

        # 3. Leer solo lo que terminó a tiempo
        actions: dict[str, Action] = {}
        for p in self.state.players:
            fut = launched.get(p.id)
            if fut is not None and fut.done() and not fut.cancelled() \
                    and fut.exception() is None:
                actions[p.id] = ctx.action_for(p.id)
            else:
                if fut is not None and fut.done() and not fut.cancelled():
                    logger.warning("Bot %s lanzó excepción", p.id,
                                   exc_info=fut.exception())
                actions[p.id] = NULL_ACTION   # timeout, ocupado o falló

        for pid, msg in ctx.errors:
            logger.warning("Bot %s registró error: %s", pid, msg)
        return actions

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
        
     # ---------- Cronograma ----------
    def start(self) -> None:
        self._enter_segment(0)

    def _normalize_team(self, team: Team | str) -> Team:
        return team if isinstance(team, Team) else Team(team)

    def _emit_ws_event(self, event_type: str, *, ok: bool | None = None, status: str | None = None, **payload) -> dict:
        message = {"type": event_type}
        if ok is not None:
            message["ok"] = ok
        if status is not None:
            message["status"] = status
        message.update(payload)
        self.ws_events.append(message)
        return message

    def set_substitute(self, team: Team | str, player_id: str | int) -> None:
        team = self._normalize_team(team)
        pid = str(player_id)
        if pid not in {p.id for p in self.state.players if p.team == team}:
            raise ValueError(f"Jugador {player_id} no pertenece al club {team}")
        self._bench_by_team[team].add(pid)
        self._starters_by_team[team].discard(pid)

    def _apply_single_substitution(self, team: Team, out_player_id: str, in_player_id: str) -> None:
        team = self._normalize_team(team)
        if out_player_id not in self._starters_by_team[team]:
            raise ValueError(f"Jugador titular no válido: {out_player_id}")
        if in_player_id not in self._bench_by_team[team]:
            raise ValueError(f"Jugador suplente no válido: {in_player_id}")

        self._starters_by_team[team].discard(out_player_id)
        self._starters_by_team[team].add(in_player_id)
        self._bench_by_team[team].discard(in_player_id)
        self._bench_by_team[team].add(out_player_id)

        out_player = next((p for p in self.state.players if p.team == team and p.id == out_player_id), None)
        in_player = next((p for p in self.state.players if p.team == team and p.id == in_player_id), None)
        if out_player is not None and in_player is not None:
            out_player.pos, in_player.pos = in_player.pos, out_player.pos

    def request_substitution(self, team: Team | str, out_player_id: str | int, in_player_id: str | int) -> dict:
        team = self._normalize_team(team)
        out = str(out_player_id)
        inn = str(in_player_id)

        if self.coach_active.get(team, False):
            return self._emit_ws_event(
                "error",
                ok=False,
                message="Solo se permite 1 cambio por pausa",
                team=team.value,
                outPlayerId=out,
                inPlayerId=inn,
            )

        if out not in self._starters_by_team[team]:
            return self._emit_ws_event(
                "error",
                ok=False,
                message="El jugador de salida debe ser titular",
                team=team.value,
                outPlayerId=out,
                inPlayerId=inn,
            )

        if inn not in self._bench_by_team[team]:
            return self._emit_ws_event(
                "error",
                ok=False,
                message="El jugador de entrada debe ser suplente",
                team=team.value,
                outPlayerId=out,
                inPlayerId=inn,
            )

        if self.state.phase == MatchPhase.PLAY:
            self.pending_substitution[team] = {"outPlayerId": out, "inPlayerId": inn}
            return self._emit_ws_event(
                "SUBSTITUTION_SCHEDULED",
                ok=True,
                status="scheduled",
                team=team.value,
                outPlayerId=out,
                inPlayerId=inn,
            )

        if self.state.phase in (MatchPhase.HYDRATION, MatchPhase.HALFTIME):
            if self.changes_used_this_pause.get(team, 0) > 0:
                return self._emit_ws_event(
                    "error",
                    ok=False,
                    message="Solo se permite 1 cambio por pausa",
                    team=team.value,
                    outPlayerId=out,
                    inPlayerId=inn,
                )
            self._apply_single_substitution(team, out, inn)
            self.changes_used_this_pause[team] = 1
            return self._emit_ws_event(
                "SUBSTITUTION_APPLIED",
                ok=True,
                status="applied",
                team=team.value,
                outPlayerId=out,
                inPlayerId=inn,
            )

        return self._emit_ws_event(
            "error",
            ok=False,
            message="La sustitución solo se admite en juego o pausa activa",
            team=team.value,
            outPlayerId=out,
            inPlayerId=inn,
        )

    def _enter_segment(self, index: int) -> None:
        prev_phase = self.state.phase
        seg = self.schedule[index]
        self._segment_index = index
        self.state.phase = seg.phase
        self.state.period = seg.period
        self.state.phase_tick = 0
        if seg.phase == MatchPhase.PLAY and prev_phase in (MatchPhase.HYDRATION, MatchPhase.HALFTIME):
            self.changes_used_this_pause = {Team.HOME: 0, Team.AWAY: 0}
        if seg.phase != MatchPhase.PLAY:
            self._apply_substitutions()

    def _advance_segment(self) -> None:
        nxt = self._segment_index + 1
        if nxt >= len(self.schedule):
            self.state.phase = MatchPhase.FINISHED
        else:
            self._enter_segment(nxt)

    def _apply_substitutions(self) -> None:
        for team in (Team.HOME, Team.AWAY):
            payload = self.pending_substitution[team]
            if payload is None:
                continue
            self._apply_single_substitution(team, payload["outPlayerId"], payload["inPlayerId"])
            self.pending_substitution[team] = None
            self.changes_used_this_pause[team] = 1
            self._emit_ws_event(
                "SUBSTITUTION_APPLIED",
                ok=True,
                status="applied",
                team=team.value,
                outPlayerId=payload["outPlayerId"],
                inPlayerId=payload["inPlayerId"],
            )
    
    # ---------- Un tick ----------
    async def tick(self) -> None:
        s = self.state
        if s.phase == MatchPhase.FINISHED:
            return
        if s.phase == MatchPhase.PLAY:
            await self._play_step()
            s.play_ticks += 1
        s.tick_count += 1
        s.phase_tick += 1
        if s.phase_tick >= self.schedule[self._segment_index].ticks:
            self._advance_segment()

    async def _play_step(self) -> None:
        s = self.state
        players = {p.id: p for p in s.players}

        # 1. Decisiones de los bots
        actions = await self._collect_actions()

        # 2. Movimiento
        for p in s.players:
            move_to = actions[p.id].move_to
            if move_to is not None:
                move_player(p, move_to, self.dt, self.field)
            else:
                p.vel = Vec2()

        # 2b. Colisiones entre jugadores
        resolve_player_collisions(s.players, self.field, PLAYER_RADIUS)

        # La pelota acompaña a su dueño antes de patear
        owner = players.get(s.ball.owner_id)
        
        # La pelota acompaña a su dueño antes de patear
        owner = players.get(s.ball.owner_id)
        if owner is not None:
            s.ball.pos = owner.pos

        # 3. Remates (apply_kick revalida la posesión)
        for p in s.players:
            kick = actions[p.id].kick
            if kick is not None:
                apply_kick(s.ball, p, kick)

        # 4. Pelota libre: física y detección de gol
        scorer = None
        if s.ball.owner_id is None:
            prev = s.ball.pos
            step_ball(s.ball, self.dt, self.field)
            scorer = check_goal(prev, s.ball.pos, self.field)

        # 5. Gol: evento, marcador y saque de centro
        if scorer is not None:
            kicker = players.get(s.ball.last_kicker_id)
            author = kicker.id if kicker is not None and kicker.team == scorer else None
            s.goals.append(GoalEvent(
                team=scorer,
                player_id=author,
                second=s.play_ticks // self.cfg.match_tick_rate,
            ))
            s.score[scorer] += 1
            reset_to_kickoff(s, self.field)
            s.ball.last_kicker_id = None
            s.ball.cooldown_ticks = 0
            return
        
        # 6. Posesión
        resolve_possession(s.ball, s.players, self.rng)

    # ---------- Loop ----------
    async def run(self) -> None:
        try:
            self.start()
            next_t = time.monotonic()
            while self.state.phase != MatchPhase.FINISHED:
                await self.tick()
                if not self.realtime:
                    await asyncio.sleep(0)
                    continue
                next_t += self.dt
                delay = next_t - time.monotonic()
                if delay > 0:
                    await asyncio.sleep(delay)
                else:                       # nos atrasamos: no acumular deuda
                    next_t = time.monotonic()
                    await asyncio.sleep(0)
            await self._finalize()
        finally:                            # también si se cancela el task
            self.close()

    async def _finalize(self) -> None:
        logger.info("Partido terminado: %s", self.state.score)
        if self.on_finish is not None:
            try:
                await self.on_finish(self.state)
            except Exception:
                logger.exception("Falló on_finish (persistencia/WebSocket)")    