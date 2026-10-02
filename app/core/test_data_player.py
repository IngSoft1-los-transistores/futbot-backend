from app.db.session import SessionLocal
from app.models.club import Club
from app.models.user import User
from app.services.auth import start_session


# Crea un usuario y un club de prueba, y genera un un club_id para usar en los tests
def crear_datos_prueba():
    db = SessionLocal()

    try:
        user = User(
            username="test",
            email="test@test.com",
            password_hash="x",
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        club = Club(
            user_id=user.id,
            name="Club de prueba",
        )

        db.add(club)
        db.commit()
        db.refresh(club)

        club_id = club.id

        print("\n==============================")
        print("DATOS DE PRUEBA")
        print("==============================")
       
        print("\nCLUB ID:")
        print(club_id)
        print("==============================\n")

        return club_id

    finally:
        db.close()

# Ejecutar: python -c "from app.core.test_data_player import crear_datos_prueba; crear_datos_prueba()"
