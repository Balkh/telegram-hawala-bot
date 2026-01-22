import bcrypt
import db


def authenticate(username, password):
    user = db.get_user_by_username(username)
    if not user:
        return None

    if not bcrypt.checkpw(password.encode(), user["password"].encode()):
        return None

    return user
