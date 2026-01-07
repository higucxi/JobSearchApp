from .database import sync_engine, Base
from .models import Job, JobSource, Application, SearchCache

def init_db():
    print("creating database tables...")
    Base.metadata.create_all(bind = sync_engine)
    print("database tables created successfully")

if __name__ == "__main__":
    init_db()