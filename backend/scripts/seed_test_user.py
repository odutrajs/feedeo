"""Cria (ou atualiza) o usuário de teste com assinatura recorrente 'paga'.

Uso: cd backend && .venv/bin/python -m scripts.seed_test_user

Credenciais: teste@virou.ai / teste123

Se o banco tiver o usuário legado (default@local), ele é convertido no usuário
de teste — assim todos os workspaces/projetos/biblioteca existentes continuam
pertencendo a ele.
"""

from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.db.base import SessionLocal, init_db
from app.db.models import User

TEST_EMAIL = "teste@virou.ai"
TEST_PASSWORD = "teste123"
TEST_NAME = "Usuário Teste"


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == TEST_EMAIL).first()
        if user is None:
            # Converte o usuário legado (dados existentes) no usuário de teste
            user = db.query(User).filter(User.email == "default@local").first()
        if user is None:
            user = User(name=TEST_NAME, email=TEST_EMAIL)
            db.add(user)

        user.name = TEST_NAME
        user.email = TEST_EMAIL
        user.password_hash = hash_password(TEST_PASSWORD)
        user.role = "user"
        user.subscription_status = "active"  # recorrência 'paga'
        user.plan = "pro"
        user.current_period_end = datetime.now(timezone.utc) + timedelta(days=30)
        db.commit()
        print(f"OK: usuário de teste pronto (id={user.id})")
        print(f"  email:    {TEST_EMAIL}")
        print(f"  senha:    {TEST_PASSWORD}")
        print(f"  plano:    {user.plan} ({user.subscription_status})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
