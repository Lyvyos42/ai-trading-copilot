"""
SQLAlchemy ORM models package.
Imports all models so that foreign keys and tables are registered in Base.metadata.
"""
import app.models.user  # noqa: F401
import app.models.signal  # noqa: F401
import app.models.portfolio  # noqa: F401
import app.models.news  # noqa: F401
import app.models.alert  # noqa: F401
import app.models.memory  # noqa: F401
