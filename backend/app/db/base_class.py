from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Every model inherits from this. Kept in its own module (rather than in
    session.py) so Alembic can import just the metadata without pulling in
    the engine/session machinery.
    """

    pass
