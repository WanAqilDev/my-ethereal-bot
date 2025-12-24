import asyncio
import os
from common.database.db import Database

async def init_db():
    print("Initializing Database...")
    pool = await Database.get_pool()
    
    # Read schema
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path, 'r') as f:
        schema_sql = f.read()
    
    async with pool.acquire() as conn:
        print("Executing Schema...")
        await conn.execute(schema_sql)
        print("Schema executed successfully.")

    await Database.close()

if __name__ == "__main__":
    asyncio.run(init_db())
