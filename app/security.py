import time
from collections import defaultdict, deque

import bcrypt
import jwt
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import FERNET_KEY, JWT_SECRET
from app.db import AuditLog, User, get_db

fernet = Fernet(FERNET_KEY.encode())
bearer = HTTPBearer()


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def check_password(p: str, h: str) -> bool:
    return bcrypt.checkpw(p.encode(), h.encode())


def encrypt(text: str) -> str:
    return fernet.encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    return fernet.decrypt(token.encode()).decode() if token else ""


def make_token(user: User, minutes: int = 60) -> str:
    payload = {"sub": str(user.id), "role": user.role, "exp": int(time.time()) + minutes * 60}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer), db=Depends(get_db)) -> User:
    try:
        data = jwt.decode(creds.credentials, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Session invalide ou expirée")
    user = db.get(User, int(data["sub"]))
    if not user:
        raise HTTPException(401, "Utilisateur introuvable")
    return user


def require_role(*roles):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "Accès refusé")
        return user
    return dep


def audit(db, user_id, action: str, target: str = ""):
    db.add(AuditLog(user_id=user_id, action=action, target=target))
    db.commit()


_hits = defaultdict(deque)


def rate_limit(key: str, max_calls: int = 10, window: int = 60):
    t = time.time()
    q = _hits[key]
    while q and q[0] < t - window:
        q.popleft()
    if len(q) >= max_calls:
        raise HTTPException(429, "Trop de requêtes, réessayez dans un moment")
    q.append(t)