import asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models import Target
from app.settings import get_settings

async def delete_all_targets():
    settings = get_settings()
    # The normal database_url connects as outreach_app which has Row-Level Security (RLS) enabled.
    # Without setting a user_id on the session, it sees (and deletes) 0 rows.
    # We use the migration_database_url (which connects as the table owner) to bypass RLS.
    db_url = settings.migration_database_url or settings.database_url.replace("outreach_app:outreach_app", "outreach:outreach")
    engine = create_async_engine(db_url)
    SessionFactory = async_sessionmaker(engine)
    
    async with SessionFactory() as session:
        await session.execute(delete(Target))
        await session.commit()
    print("Deleted all targets.")

if __name__ == "__main__":
    asyncio.run(delete_all_targets())
