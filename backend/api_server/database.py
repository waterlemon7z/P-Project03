from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    String,
    Text,
    and_,
    create_engine,
    func,
    or_,
    select,
    update,
)
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def now() -> datetime:
    # Store UTC as naive timestamps consistently on SQLite and PostgreSQL.
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    type: Mapped[str] = mapped_column(String(10), index=True)
    status: Mapped[str] = mapped_column(String(12), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    claim_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class Store:
    def __init__(self, database_url: str):
        url = make_url(database_url)
        if url.drivername == "postgresql":
            url = url.set(drivername="postgresql+psycopg")
        if url.get_backend_name() == "sqlite" and url.database not in (
            None,
            "",
            ":memory:",
        ):
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)
        kwargs = (
            {"connect_args": {"check_same_thread": False, "timeout": 30}}
            if url.get_backend_name() == "sqlite"
            else {}
        )
        self.engine = create_engine(url, pool_pre_ping=True, **kwargs)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def initialize(self):
        Base.metadata.create_all(self.engine)

    def create(self, kind: str, payload: dict, analysis_id: str | None = None) -> str:
        analysis_id = analysis_id or str(uuid4())
        with self.sessions.begin() as session:
            session.add(
                Analysis(
                    id=analysis_id,
                    type=kind,
                    status="pending",
                    payload=payload,
                    created_at=now(),
                    updated_at=now(),
                )
            )
        return analysis_id

    @staticmethod
    def serialize(row: Analysis) -> dict:
        result = row.result or {}
        return {
            **result,
            "id": row.id,
            "type": row.type,
            "status": row.status,
            "error": row.error,
            "created_at": row.created_at.replace(tzinfo=UTC),
            "updated_at": row.updated_at.replace(tzinfo=UTC),
        }

    def get(self, analysis_id: str) -> dict | None:
        with self.sessions() as session:
            row = session.get(Analysis, analysis_id)
            return self.serialize(row) if row else None

    def history(
        self, kind: str | None, status: str | None, limit: int, offset: int
    ) -> dict:
        filters = []
        if kind:
            filters.append(Analysis.type == kind)
        if status:
            filters.append(Analysis.status == status)
        with self.sessions() as session:
            total = session.scalar(
                select(func.count()).select_from(Analysis).where(*filters)
            )
            rows = session.scalars(
                select(Analysis)
                .where(*filters)
                .order_by(Analysis.created_at.desc(), Analysis.id.desc())
                .limit(limit)
                .offset(offset)
            ).all()
            return {
                "items": [self.serialize(row) for row in rows],
                "total": total,
                "limit": limit,
                "offset": offset,
            }

    def claim(self, lease_seconds: float) -> tuple[str, str, dict, str] | None:
        eligible = or_(
            Analysis.status == "pending",
            and_(
                Analysis.status == "processing",
                Analysis.updated_at < now() - timedelta(seconds=lease_seconds),
            ),
        )
        with self.sessions.begin() as session:
            row = session.scalar(
                select(Analysis).where(eligible).order_by(Analysis.created_at).limit(1)
            )
            if row is None:
                return None
            token = str(uuid4())
            # The conditional UPDATE arbitrates competing workers on either supported DB.
            changed = session.execute(
                update(Analysis)
                .where(Analysis.id == row.id, eligible)
                .values(status="processing", claim_token=token, updated_at=now()),
                execution_options={"synchronize_session": False},
            ).rowcount
            return (row.id, row.type, row.payload, token) if changed else None

    def finish(
        self, analysis_id: str, token: str, result: dict | None, error: str | None
    ) -> bool:
        with self.sessions.begin() as session:
            changed = session.execute(
                update(Analysis)
                .where(
                    Analysis.id == analysis_id,
                    Analysis.claim_token == token,
                    Analysis.status == "processing",
                )
                .values(
                    status="failed" if error else "completed",
                    result=result,
                    error=error,
                    payload={},
                    claim_token=None,
                    updated_at=now(),
                )
            ).rowcount
            return bool(changed)
