import asyncio
import os
from common.database.db import Database

# BANK CONFIG
BANK_ID = 0
GENESIS_SUPPLY = 1_000_000_000

async def migrate():
    print("⚠️  STARTING ECONOMY MIGRATION ⚠️")
    print("This will WIPE all user balances and inventory.")
    
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        # 1. Wipe Data
        print("1. Wiping `users` table...")
        await conn.execute("DELETE FROM users")
        
        # 2. Genesis Mint
        print(f"2. Minting GENESIS BLOCK: {GENESIS_SUPPLY:,} 💎 to Bank (ID: {BANK_ID})...")
        await conn.execute(
            """
            INSERT INTO users (user_id, balance, xp, level, inventory, badges)
            VALUES ($1, $2, 0, 1, $3, $4)
            """,
            BANK_ID, GENESIS_SUPPLY, [], ["🏦 Central Bank"]
        )
        
    print("✅ Migration Complete. The Economy is now Closed-Loop.")

if __name__ == "__main__":
    asyncio.run(migrate())
