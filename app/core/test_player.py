from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.club import Club
from app.models.user import User

TEST_EMAIL = "test@test.com"


def crear_datos_prueba():
    db = SessionLocal()

    try:
        # Buscar o crear usuario
        user = db.scalar(
            select(User).where(User.email == TEST_EMAIL)
        )

        if user is None:
            user = User(
                username="test",
                email=TEST_EMAIL,
                password_hash="x",
            )

            db.add(user)
            db.commit()
            db.refresh(user)

            print("Usuario de prueba creado.")

        # Buscar o crear club
        club = db.scalar(
            select(Club).where(Club.user_id == user.id)
        )

        if club is None:
            club = Club(
                user_id=user.id,
                name="Club de prueba",
            )

            db.add(club)
            db.commit()
            db.refresh(club)

            print("Club de prueba creado.")

        print("\n==============================")
        print("DATOS DE PRUEBA")
        print("==============================")
        print(f"Usuario: {user.email}")
        print(f"Club ID: {club.id}")
        print("==============================\n")

        return club.id

    finally:
        db.close()


def get_current_club_id() -> str:
    db = SessionLocal()

    try:
        user = db.scalar(
            select(User).where(User.email == TEST_EMAIL)
        )

        if user is None:
            raise Exception("Usuario de prueba no encontrado.")

        club = db.scalar(
            select(Club).where(Club.user_id == user.id)
        )

        if club is None:
            raise Exception("Club de prueba no encontrado.")

        return club.id

    finally:
        db.close()


if __name__ == "__main__":
    crear_datos_prueba()
