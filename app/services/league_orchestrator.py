import asyncio
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from app.models.room import Room, ROOM_STATUS_IN_PROGRESS, ROOM_STATUS_FINISHED
from app.models.match import Match, ESTADO_SCHEDULED, ESTADO_PRE_MATCH, ESTADO_IN_PROGRESS, ESTADO_FINISHED
from app.models.enrollment import Enrollment
from app.models.club import Club
from app.services.match_runner import start_match
from app.core.config import get_settings
from app.ws.manager import league_manager

def get_league_lobby_payload(db: Session, league_id: str) -> dict:
    """Calcula y consolida el estado completo de liga activa."""
    room = db.get(Room, league_id)
    if not room or room.status != ROOM_STATUS_IN_PROGRESS:
        return None

    # Partido en curso y proximo
    current_match = db.execute(
        select(Match).where(Match.room_id == league_id, Match.status == ESTADO_IN_PROGRESS).limit(1)
    ).scalar_one_or_none()

    next_match = db.execute(
        select(Match)
        .where(Match.room_id == league_id, Match.status.in_([ESTADO_SCHEDULED, ESTADO_PRE_MATCH]))
        .order_by(Match.round.asc(), Match.id.asc())
        .limit(1)
    ).scalar_one_or_none()

    # Fixture completo

    matches = db.execute(
        select(Match).where(Match.room_id == league_id).order_by(Match.round.asc())
    ).scalars().all()


    # Tabla de posiciones con los 5 criterios de desempate
    enrollments = db.execute(
        select(Enrollment).where(Enrollment.room_id == league_id)
    ).scalars().all()

    standing_data = []
    for enr in enrollments:
        club = db.get(Club, enr.club_id)
        goal_diff = enr.goals_for - enr.goals_against
        standing_data.append({
            "club_id": enr.club_id,
            "club_name": club.name if club else "Desconocido",
            "matches_played": enr.matches_played,
            "matches_won": enr.matches_won,
            "matches_drawn": enr.matches_drawn,
            "matches_lost": enr.matches_lost,
            "goals_for": enr.goals_for,
            "goals_against": enr.goals_against,
            "goal_difference": goal_diff,
            "points": enr.points,
        })

    sorted_standings = sorted(
        standing_data,
        key=lambda x: (
            -x["points"],
            -x["matches_won"],
            -x["goal_difference"],
            -x["goals_for"],
            x["club_name"].lower()
        )
    )

    return {
        "type": "league_lobby_update",
        "league_id": room.id,
        "league_name": room.name,
        "status": room.status,
        "currentMatch": {
            "id": current_match.id,
            "home_club_id": current_match.home_club_id,
            "away_club_id": current_match.away_club_id,
            "round": current_match.round,
            "status": current_match.status,
        } if current_match else None,
        "nextMatch": {
            "id": next_match.id,
            "home_club_id": next_match.home_club_id,
            "away_club_id": next_match.away_club_id,
            "round": next_match.round,
            "status": next_match.status,
        } if next_match else None,
        "standings": sorted_standings,
        "calendar": [
            {
                "id": m.id,
                "round": m.round,
                "home_club_id": m.home_club_id,
                "away_club_id": m.away_club_id,
                "home_goals": m.home_goals,
                "away_goals": m.away_goals,
                "status": m.status,
            } for m in matches
        ],
    }


async def on_match_finished_notifier(match_id: str, data: dict, bind):
    """Callback invocado por el motor de partido al finalizar un encuentro."""
    if data.get("type") == "MATCH_FINISHED":
        with Session(bind) as db:
            match = db.get(Match, match_id)
            if not match or not match.room_id:
                return

            league_id = match.room_id

            # Actualizar estadisticas en Enrollment
            home_enr = db.execute(
                select(Enrollment).where(Enrollment.room_id == league_id, Enrollment.club_id == match.home_club_id)
            ).scalar_one_or_none()

            away_enr = db.execute(
                select(Enrollment).where(Enrollment.room_id == league_id, Enrollment.club_id == match.away_club_id)
            ).scalar_one_or_none()

            if home_enr and away_enr:
                home_goals = data.get("home_goals", 0)
                away_goals = data.get("away_goals", 0)

                match.home_goals = home_goals
                match.away_goals = away_goals
                match.status = ESTADO_FINISHED

                home_enr.matches_played += 1
                away_enr.matches_played += 1
                home_enr.goals_for += home_goals
                home_enr.goals_against += away_goals
                away_enr.goals_for += away_goals
                away_enr.goals_against += home_goals

                if home_goals > away_goals:
                    home_enr.matches_won += 1
                    home_enr.points += 3
                    away_enr.matches_lost += 1
                elif home_goals < away_goals:
                    away_enr.matches_won += 1
                    away_enr.points += 3
                    home_enr.matches_lost += 1
                else:
                    home_enr.matches_drawn += 1
                    home_enr.points += 1
                    away_enr.matches_drawn += 1
                    away_enr.points += 1

                db.commit()

            # Broadcast con la tabla actualizada
            updated_payload = get_league_lobby_payload(db, league_id)
            if updated_payload:
                await league_manager.broadcast_active(league_id, updated_payload)

            # Disparar el siguiente partido del fixture
            asyncio.create_task(run_next_league_match(bind, league_id))


async def run_next_league_match(bind, league_id: str):
    """Busca y ejecuta el siguiente partido programado."""
    await asyncio.sleep(2) #esto es por si acaso

    with Session(bind) as db:
        next_match = db.execute(
            select(Match)
            .where(Match.room_id == league_id, Match.status.in_([ESTADO_SCHEDULED, ESTADO_PRE_MATCH]))
            .order_by(Match.round.asc(), Match.id.asc())
            .limit(1)
        ).scalar_one_or_none()

        if not next_match:
            # Si no quedan más partidos, la liga finaliza
            room = db.get(Room, league_id)
            if room:
                room.status = ROOM_STATUS_FINISHED
                db.commit()
            return

        next_match.status = ESTADO_PRE_MATCH
        db.commit()

        # Notificar inicio de nuevo partido a los observadores
        payload = get_league_lobby_payload(db, league_id)
        if payload:
            await league_manager.broadcast_active(league_id, payload)

        # Iniciar motor de partido
        start_match(
            db, 
            next_match.id, 
            get_settings(), 
            notifier=lambda m_id, data: on_match_finished_notifier(m_id, data, bind)
        )
