from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _migrate_sqlite() -> None:
    """Add columns introduced after the initial schema (SQLite has no ALTER via create_all)."""
    from sqlalchemy import inspect, text

    additions = {
        "users": [
            ("password_hash", "VARCHAR(255) DEFAULT '' NOT NULL"),
            ("role", "VARCHAR(20) DEFAULT 'user' NOT NULL"),
            ("stripe_customer_id", "VARCHAR(255)"),
            ("stripe_subscription_id", "VARCHAR(255)"),
            ("subscription_status", "VARCHAR(20) DEFAULT 'none' NOT NULL"),
            ("plan", "VARCHAR(40)"),
            ("current_period_end", "DATETIME"),
        ],
        "workspaces": [
            ("logo_path", "VARCHAR(500)"),
            ("brand", "JSON DEFAULT '{}'"),
        ],
        "projects": [
            ("mode", "VARCHAR(20) DEFAULT 'generative' NOT NULL"),
            ("workspace_id", "INTEGER"),
        ],
        "scenes": [
            ("visual_source", "VARCHAR(20) DEFAULT 'ai_image' NOT NULL"),
            ("source_segment_id", "INTEGER"),
            ("source_asset_id", "INTEGER"),
        ],
        "platform_accounts": [
            ("workspace_id", "INTEGER"),
        ],
        "publications": [
            ("social_post_id", "INTEGER"),
        ],
    }
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in additions.items():
            if table not in inspector.get_table_names():
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))

        # publications.project_id precisa ser nullable (posts sociais não têm project)
        tables = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        table_names = {r[0] for r in tables}
        if "publications" in table_names:
            info = conn.execute(text("PRAGMA table_info(publications)")).fetchall()
            # (cid, name, type, notnull, dflt_value, pk)
            col_by_name = {row[1]: row for row in info}
            project_notnull = col_by_name.get("project_id", (None, None, None, 0))[3]
            has_social = "social_post_id" in col_by_name
            if project_notnull or not has_social:
                conn.execute(text("""
                    CREATE TABLE publications_new (
                        id INTEGER NOT NULL PRIMARY KEY,
                        project_id INTEGER,
                        social_post_id INTEGER,
                        account_id INTEGER NOT NULL,
                        status VARCHAR(20) NOT NULL DEFAULT 'scheduled',
                        scheduled_at DATETIME,
                        published_at DATETIME,
                        external_id VARCHAR(255),
                        error TEXT,
                        created_at DATETIME
                    )
                """))
                if has_social:
                    conn.execute(text("""
                        INSERT INTO publications_new
                            (id, project_id, social_post_id, account_id, status,
                             scheduled_at, published_at, external_id, error, created_at)
                        SELECT id, project_id, social_post_id, account_id, status,
                               scheduled_at, published_at, external_id, error, created_at
                        FROM publications
                    """))
                else:
                    conn.execute(text("""
                        INSERT INTO publications_new
                            (id, project_id, social_post_id, account_id, status,
                             scheduled_at, published_at, external_id, error, created_at)
                        SELECT id, project_id, NULL, account_id, status,
                               scheduled_at, published_at, external_id, error, created_at
                        FROM publications
                    """))
                conn.execute(text("DROP TABLE publications"))
                conn.execute(text("ALTER TABLE publications_new RENAME TO publications"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_publications_project_id ON publications (project_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_publications_social_post_id ON publications (social_post_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_publications_account_id ON publications (account_id)"))


def init_db() -> None:
    from app.db import models  # noqa: F401 (register models)

    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    settings.projects_dir.mkdir(parents=True, exist_ok=True)
    settings.music_dir.mkdir(parents=True, exist_ok=True)
    settings.library_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    if settings.database_url.startswith("sqlite"):
        _migrate_sqlite()
    _backfill_library_once()


def _backfill_library_once() -> None:
    """Copia mídias de projetos existentes para a biblioteca (só se ela estiver vazia)."""
    from app.core.logging import get_logger
    from app.db.models import LibraryAsset, Project, SourceAsset, User
    from app.modules.library.service import save_to_library

    logger = get_logger("library.backfill")
    db = SessionLocal()
    try:
        if db.query(LibraryAsset).count() > 0:
            return
        user = db.query(User).first()
        if user is None:
            return
        sources = (
            db.query(SourceAsset)
            .join(Project, Project.id == SourceAsset.project_id)
            .filter(Project.user_id == user.id)
            .order_by(SourceAsset.created_at.asc())
            .all()
        )
        seen: set[str] = set()
        for source in sources:
            key = f"{source.filename}:{source.kind}"
            if key in seen:
                continue
            path = settings.storage_dir / source.path
            if not path.is_file():
                continue
            seen.add(key)
            try:
                save_to_library(
                    db,
                    user_id=user.id,
                    source_path=path,
                    filename=source.filename,
                    kind=source.kind,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("backfill falhou para %s: %s", source.filename, exc)
        if seen:
            logger.info("biblioteca preenchida com %d mídia(s) existente(s)", len(seen))
    finally:
        db.close()
