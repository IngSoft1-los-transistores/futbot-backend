import pytest

from app.behaviors import executor, loader
from app.engine import live_engines
from app.engine.field import FieldConfig
from app.engine.match_engine import MatchEngine
from app.engine.schedule import build_schedule
from app.engine.setup import PlayerSpec, create_initial_state
from app.engine.state import Team
from app.models.behavior import BEHAVIOR_KIND_DT, Behavior
from app.services import dt_behavior_service
from app.services.exceptions_dt import ManualActionBlockedByDt
from app.services.match_runner import _resolve_dt


class Cfg:
    behavior_timeout_seconds = 0.05
    match_tick_rate = 10
    friendly_match_duration_seconds = 8


def _specs(prefix):
    return [PlayerSpec(f"{prefix}{i}", 60, 60, 60, 60, 60) for i in range(3)]


def dummy_dt(context):
    return []


@pytest.fixture
def make_dt_engine(monkeypatch):
    monkeypatch.setattr(executor, "ejecutar_comportamiento", lambda pid, ctx: None)
    engines = []

    def _make(dt_functions=None):
        field = FieldConfig()
        state = create_initial_state(field, _specs("h"), _specs("a"))
        schedule = build_schedule(8, 10, hydration_seconds=1, halftime_seconds=2)
        engine = MatchEngine(
            state,
            field,
            Cfg(),
            {p.id: "b" for p in state.players},
            schedule=schedule,
            realtime=False,
            dt_functions=dt_functions,
        )
        engines.append(engine)
        return engine

    yield _make
    for e in engines:
        e.close()


@pytest.fixture
def dt_behavior(db, club) -> Behavior:
    behavior = Behavior(
        club_id=club.id,
        name="my_dt",
        code="def run_dt(context):\n    return []",
        is_preprogrammed=False,
        kind=BEHAVIOR_KIND_DT,
    )
    db.add(behavior)
    db.commit()
    return behavior


def test_engine_snapshot_is_independent_of_the_source_dict(make_dt_engine):
    source = {Team.HOME: dummy_dt, Team.AWAY: None}
    engine = make_dt_engine(dt_functions=source)
    source[Team.AWAY] = dummy_dt  # mutate after kickoff
    source[Team.HOME] = None
    assert engine.has_dt(Team.HOME) is True
    assert engine.has_dt(Team.AWAY) is False


def test_engine_without_dt_functions_has_no_dt(make_dt_engine):
    engine = make_dt_engine()
    assert engine.has_dt(Team.HOME) is False
    assert engine.has_dt(Team.AWAY) is False


def test_resolved_dt_survives_unassign_and_cache_replacement(db, club, dt_behavior):
    original = dummy_dt
    loader._cache[dt_behavior.id] = original
    try:
        dt_behavior_service.assign_dt(db, club, dt_behavior.id)
        snapshot = _resolve_dt(db, club.id)
        dt_behavior_service.clear_dt(db, club)  # unassign mid-match
        loader._cache[dt_behavior.id] = lambda ctx: ["changed"]  # recompiled edit
        assert snapshot is original
        assert _resolve_dt(db, club.id) is None
    finally:
        loader._cache.pop(dt_behavior.id, None)


def test_resolve_dt_returns_none_when_function_not_loaded(db, club, dt_behavior):
    dt_behavior_service.assign_dt(db, club, dt_behavior.id)
    loader._cache.pop(dt_behavior.id, None)
    assert _resolve_dt(db, club.id) is None


def test_resolve_dt_returns_none_when_club_has_no_dt(db, club):
    assert _resolve_dt(db, club.id) is None


class FakeEngine:
    def __init__(self, home_has_dt, away_has_dt):
        self._dt = {Team.HOME: home_has_dt, Team.AWAY: away_has_dt}

    def has_dt(self, team):
        return self._dt[team]


class FakeMatch:
    id = "m1"
    home_club_id = "club-home"


def test_manual_action_blocked_when_club_has_dt():
    live_engines.engines["m1"] = FakeEngine(True, False)
    try:
        with pytest.raises(ManualActionBlockedByDt):
            dt_behavior_service.ensure_manual_action_allowed(FakeMatch(), "club-home")
        # the rival has no DT: allowed
        dt_behavior_service.ensure_manual_action_allowed(FakeMatch(), "club-away")
    finally:
        live_engines.engines.pop("m1", None)


def test_manual_action_allowed_when_match_is_not_running():
    dt_behavior_service.ensure_manual_action_allowed(FakeMatch(), "club-home")
