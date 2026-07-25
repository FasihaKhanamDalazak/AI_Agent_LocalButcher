# Imported only by Alembic (migrations/env.py). Importing app.models here
# registers every table on Base.metadata, which is what autogenerate reads
# to diff "models" vs "actual database" and produce a migration.

from app.db.base_class import Base  # noqa: F401
from app.models import *  # noqa: F401,F403
