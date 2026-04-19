from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tci.settings import Settings


@contextmanager
def _session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def build_session_factory(
    settings: Settings,
) -> Callable[[], AbstractContextManager[Session]] | None:
    if not settings.database_url:
        return None

    engine = create_engine(settings.database_url, future=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)

    # 세션 생성 규칙을 한 곳에 고정해 라우트와 서비스가 트랜잭션 경계를 공유하게 한다.
    def session_factory() -> AbstractContextManager[Session]:
        return _session_scope(factory)

    return session_factory
