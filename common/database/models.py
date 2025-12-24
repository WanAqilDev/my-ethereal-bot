from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel

# We will use raw SQL with asyncpg, but these Pydantic models 
# help strictly define our data shapes for the API and Bot application logic.

class User(BaseModel):
    user_id: int
    balance: int = 0
    xp: int = 0
    level: int = 1
    badges: List[str] = []
    inventory: List[str] = []
    created_at: datetime
    last_active: datetime

class Transaction(BaseModel):
    id: int
    sender_id: int
    receiver_id: int
    amount: int
    type: str # 'TICKET', 'BET', 'REWARD', 'PAYMENT', 'RAIN', 'CASINO_WIN', 'CASINO_LOSS', 'SHOP_BUY'
    metadata: Optional[dict] = {}
    timestamp: datetime
    hash: str

class CinemaSession(BaseModel):
    session_id: str
    host_id: int
    guild_id: int
    channel_id: int
    video_url: Optional[str]
    ticket_price: int = 50
    is_active: bool = True
    created_at: datetime
