"""Fase y duración de la pausa en el tick que arma el runner a partir del motor."""
from uuid import uuid4

import pytest

from app.behaviors import executor
from app.engine.field import FieldConfig
from app.engine.match_engine import MatchEngine
from app.engine.schedule import build_schedule
from app.engine.setup import PlayerSpec, create_initial_state
from app.engine.state import MatchPhase, Team
from app.services.match_runner import capture_tick

CLUB_OF = {Team.HOME: str(uuid4()), Team.AWAY: str(uuid4())}


class Cfg:
    behavior_timeout_seconds = 0.05
    match_tick_rate = 10
    friendly_match_duration_seconds = 8


def specs():
    return [PlayerSpec(str(uuid4()), 60, 60, 60, 60, 60) for _ in range(3)]


@pytest.fixture
def match_engine(monkeypatch):
    monkeypatch.setattr(executor, "ejecutar_comportamiento", lambda pid, ctx: None)
    field = FieldConfig()
    state = create_initial_state(field, specs(), specs())
    # Pausas de distinta duración: hidratación 1 s, entretiempo 2 s.
    schedule = build_schedule(8, 10, hydration_seconds=1, halftime_seconds=2)
    engine = MatchEngine(state, field, Cfg(), {p.id: "b" for p in state.players},
                         schedule=schedule, realtime=False)
    yield engine
    engine.close()


@pytest.mark.asyncio
async def test_each_tick_reports_phase_and_pause_times(match_engine):
    roster = [p.id for p in match_engine.state.players]
    match_engine.start()
    ticks = [capture_tick(match_engine, roster, CLUB_OF)]
    for _ in range(500):
        if match_engine.state.phase == MatchPhase.FINISHED:
            break
        await match_engine.tick()
        ticks.append(capture_tick(match_engine, roster, CLUB_OF))

    pairs = [(tick.phase, tick.pause_duration) for tick in ticks]
    collapsed = [pair for i, pair in enumerate(pairs) if i == 0 or pair != pairs[i - 1]]
    assert collapsed == [
        ("PLAYING", None), ("HYDRATION", 1),
        ("PLAYING", None), ("HALFTIME", 2),
        ("PLAYING", None), ("HYDRATION", 1),
        ("PLAYING", None), ("FINISHED", None),
    ]

    hydration = [tick.pause_remaining for tick in ticks if tick.phase == "HYDRATION"]
    halftime = [tick.pause_remaining for tick in ticks if tick.phase == "HALFTIME"]
    # Each pause counts down from its total to one tick (0.1 s), never reaching 0.
    assert hydration == pytest.approx([1 - i / 10 for i in range(10)] * 2)
    assert halftime == pytest.approx([2 - i / 10 for i in range(20)])
