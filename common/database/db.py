import asyncpg
import os
from typing import Optional

class Database:
    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        if cls._pool is None:
            # 1. Validate Env Vars
            user = os.getenv('POSTGRES_USER')
            password = os.getenv('POSTGRES_PASSWORD')
            host = os.getenv('DB_HOST') # Host might be "postgres" (docker) or "localhost"
            db_name = os.getenv('POSTGRES_DB')

            if not all([user, password, host, db_name]):
                # Attempt to load .env manually if missing (e.g. running from subdir)
                print("⚠️  DB Env vars missing. Attempting to load .env from parents...")
                from dotenv import load_dotenv, find_dotenv
                load_dotenv(find_dotenv(usecwd=True))
                
                # Retry fetch
                user = os.getenv('POSTGRES_USER')
                password = os.getenv('POSTGRES_PASSWORD')
                host = os.getenv('DB_HOST')
                db_name = os.getenv('POSTGRES_DB')
            
            if not all([user, password, host, db_name]):
                 raise ValueError(f"❌ Missing DB Env Vars! User={user}, Host={host}, DB={db_name}")

            dsn = f"postgresql://{user}:{password}@{host}/{db_name}"
            
            import asyncio
            for i in range(5):
                try:
                    print(f"⏳ Connecting to DB at {host} as {user}...")
                    cls._pool = await asyncpg.create_pool(dsn)
                    print(f"✅ DB Connected to {host}")
                    break
                except Exception as e:
                    wait = 2 ** i
                    print(f"⚠️ DB Connection Failed ({e}). Retrying in {wait}s...")
                    await asyncio.sleep(wait)
            
            if cls._pool is None:
                raise ConnectionError("Could not connect to Database after retries.")
        return cls._pool

    @classmethod
    async def close(cls):
        if cls._pool:
            await cls._pool.close()
            cls._pool = None

db = Database
