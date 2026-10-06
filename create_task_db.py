import os

os.environ["DATABASE_URL"] = "sqlite:///./blog_task.sqlite"

from database import Base, engine
import models  # noqa: F401 - registers all ORM tables on Base

Base.metadata.create_all(bind=engine)
print("Created blog_task.sqlite with tables:", ", ".join(Base.metadata.tables))
