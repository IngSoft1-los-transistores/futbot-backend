from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

""" hashing de contraseñas """
def hash_password(password: str) -> str:
    return pwd_context.hash(password)