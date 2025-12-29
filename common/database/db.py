import asyncpg
import os
from typing import Optional

class Database:
    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        if cls._pool is None:
            dsn = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('POSTGRES_DB')}"
            
            import asyncio
            for i in range(5):
                try:
                    cls._pool = await asyncpg.create_pool(dsn)
                    print(f"✅ DB Connected to {os.getenv('DB_HOST')}")
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
