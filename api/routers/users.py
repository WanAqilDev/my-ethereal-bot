from fastapi import APIRouter, HTTPException
from common.database.db import Database
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/users", tags=["users"])

class UserProfile(BaseModel):
    user_id: int
    balance: int
    xp: int
    level: int
    badges: List[str]
    inventory: List[str]

@router.get("/{user_id}", response_model=UserProfile)
async def get_user_profile(user_id: int):
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        if not row:
            # Create user if not exists? Or 404?
            # 404 is better for API, usually bot creates them.
            raise HTTPException(status_code=404, detail="User not found")
        
        return UserProfile(
            user_id=row['user_id'],
            balance=row['balance'],
            xp=row['xp'],
            level=row['level'],
            badges=row['badges'] or [],
            inventory=row['inventory'] or []
        )
