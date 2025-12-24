-- ==========================================
-- USERS TABLE
-- ==========================================
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,              -- Discord user ID
    balance INT DEFAULT 0 CHECK (balance >= 0),
    xp INT DEFAULT 0,
    level INT DEFAULT 1,
    badges TEXT[] DEFAULT '{}',              -- Array of badge names
    inventory TEXT[] DEFAULT '{}',           -- Array of owned items
    created_at TIMESTAMP DEFAULT NOW(),
    last_active TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_balance ON users(balance);
CREATE INDEX IF NOT EXISTS idx_users_level ON users(level);

-- ==========================================
-- TRANSACTIONS TABLE (Immutable Ledger)
-- ==========================================
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    sender_id BIGINT NOT NULL,               -- User ID or 0 (Vault)
    receiver_id BIGINT NOT NULL,             -- User ID or 0 (Vault)
    amount INT NOT NULL,
    type VARCHAR(50) NOT NULL,               -- 'TICKET', 'BET', 'REWARD', 'PAYMENT', 'RAIN', 'CASINO_WIN', 'CASINO_LOSS', 'SHOP_BUY'
    metadata JSONB,                          -- Additional context (game type, session ID, etc.)
    timestamp TIMESTAMP DEFAULT NOW(),
    hash VARCHAR(256)                        -- SHA-256 of (sender_id + receiver_id + amount + timestamp)
);

CREATE INDEX IF NOT EXISTS idx_transactions_sender ON transactions(sender_id);
CREATE INDEX IF NOT EXISTS idx_transactions_receiver ON transactions(receiver_id);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type);
CREATE INDEX IF NOT EXISTS idx_transactions_timestamp ON transactions(timestamp DESC);

-- ==========================================
-- CINEMA SESSIONS TABLE
-- ==========================================
CREATE TABLE IF NOT EXISTS cinema_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    host_id BIGINT NOT NULL,                 -- Session creator
    guild_id BIGINT NOT NULL,                -- Discord server ID
    channel_id BIGINT NOT NULL,              -- Voice channel ID
    video_url TEXT,                          -- Currently playing video
    ticket_price INT DEFAULT 50,             -- Entry fee
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cinema_sessions_active ON cinema_sessions(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_cinema_sessions_guild ON cinema_sessions(guild_id);

-- ==========================================
-- CINEMA TICKETS TABLE
-- ==========================================
CREATE TABLE IF NOT EXISTS cinema_tickets (
    ticket_id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL,
    user_id BIGINT NOT NULL,
    purchased_at TIMESTAMP DEFAULT NOW(),
    has_remote BOOLEAN DEFAULT FALSE,        -- Can control playback
    
    CONSTRAINT unique_ticket UNIQUE (session_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_cinema_tickets_session ON cinema_tickets(session_id);
CREATE INDEX IF NOT EXISTS idx_cinema_tickets_user ON cinema_tickets(user_id);

-- ==========================================
-- PERSISTENT PLAYLISTS
-- ==========================================
CREATE TABLE IF NOT EXISTS playlists (
    playlist_id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    name VARCHAR(50) NOT NULL,
    songs JSONB NOT NULL DEFAULT '[]',       -- List of song objects
    created_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT unique_user_playlist_name UNIQUE (user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_playlists_user ON playlists(user_id);

-- ==========================================
-- SPECIAL ACCOUNTS
-- ==========================================
-- Vault Account: ID = 0 (for closed-loop economy)
INSERT INTO users (user_id, balance, xp, level) 
VALUES (0, 1000000, 0, 999) 
ON CONFLICT (user_id) DO NOTHING;
