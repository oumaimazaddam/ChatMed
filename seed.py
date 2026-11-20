import secrets
from app.db import SessionLocal, User, init_db
from app.security import hash_password

init_db()
ACCOUNTS = [
    ("doctor@doctor.tn", "Dr amine", "doctor"),
    ("admin@admin.tn", "Admin oussama", "admin"),
]

with SessionLocal() as db:
    for email, name, role in ACCOUNTS:
        if db.query(User).filter_by(email=email).first():
            print(f"Existe déjà : {email}")
            continue
        password = secrets.token_urlsafe(10)
        db.add(User(email=email, full_name=name, role=role, password_hash=hash_password(password)))
        db.commit()
        print(f"Créé : {email}  mot de passe : {password}   (note-le, il ne sera plus affiché)")