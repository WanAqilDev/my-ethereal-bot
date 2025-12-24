# Ethereal Trifid: The Ultimate Discord Ecosystem 🎵🍿💎

A robust, multi-service Discord ecosystem featuring Music, Economy, Gambling, Cinema, and Custom Activities.

![Monorepo](https://img.shields.io/badge/Architecture-Monorepo-blue)
![Discord.py](https://img.shields.io/badge/Bots-Discord.py%202.0-7289DA)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688)
![React](https://img.shields.io/badge/Web-React%20%2B%20Vite-61DAFB)

## Features

### 🤖 Bot 1: Music & Economy (Omni-Bot)
*   **Music**: High-quality playback (`yt-dlp`), Persistent Queue (Redis), Audio Filters (Bass Boost, Nightcore), Playlists, Looping, Seeking.
*   **Economy**: Persistent Postgres Database, Daily Rewards, Shop System (30+ items).
*   **Casino**: `!coinflip` (50% odds), `!slots` (5% jackpot), `!rain` (share wealth).
*   **Levels**: Chat/Voice XP system with tiered income bonuses.

### 🤖 Bot 2: Cinema & Activities
*   **Cinema**: Create private sessions (`!cinema create`), buy tickets, and watch synchronized video with friends.
*   **Sync Engine**: Real-time Socket.IO synchronization guarantees all viewers see the same frame.

### 🌐 Web Activity & API
*   **React App**: A beautiful "Letter League"-style web activity for Cinema (and future Arcade games).
*   **API**: FastAPI backend handling auth, economy transactions, and socket events.

### ⚠️ Critical Note: Privileged Intents
The bots require **Privileged Intents** to function (reading messages, checking voice states).
1.  Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2.  Select your Application -> **Bot** tab.
3.  Scroll down to **Privileged Gateway Intents**.
4.  Enable **Message Content Intent**, **Server Members Intent**, and **Presence Intent**.
5.  Save Changes. *If skipped, the bot will crash on startup.*

---

## 🚀 Deployment Guide

### Method 1: Docker (Standard) - *Recommended*
1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/WanAqilDev/my-ethereal-bot.git
    cd my-ethereal-bot
    ```
2.  **Configure Environment**:
    Create a `.env` file (copy `.env.example` if available) with your keys:
    ```ini
    POSTGRES_PASSWORD=secret
    MUSIC_BOT_TOKEN=...
    CINEMA_BOT_TOKEN=...
    # ... see docker-compose.yml for full list
    ```
3.  **Run**:
    ```bash
    docker-compose up -d --build
    ```

### Method 2: Portainer (GUI)
1.  Go to your Portainer Dashboard -> **Stacks** -> **Add stack**.
2.  **Repository**: Select "Git Repository" and enter `https://github.com/WanAqilDev/my-ethereal-bot.git`.
3.  **Compose Path**: `docker-compose.yml`.
4.  **Environment Variables**: Manually add every variable from your `.env` file (Tokens, Passwords, etc.).
5.  Click **Deploy the stack**.

### Method 3: Proxmox CT (LXC Container)
Running inside a lightweight Linux Container (LXC) on Proxmox.

1.  **Create CT**:
    *   Template: Ubuntu 22.04 or Debian 12.
    *   Resources: 2GB RAM, 2 Cores recommended.
    *   **IMPORTANT**: In Options, enable **Nesting** and **FUSE** (required for Docker inside LXC).

2.  **Install Docker inside CT**:
    Open the CT Console and run:
    ```bash
    apt update && apt install -y curl
    curl -fsSL https://get.docker.com | sh
    apt install -y docker-compose-plugin
    ```

3.  **Deploy**:
    Follow the **Method 1 (Docker)** steps inside the CT console.

### Method 4: Manual / Native (No Docker)
Best for Windows Server or low-spec VPS.
1.  **Install Prerequisites**: Python 3.9+, PostgreSQL, Redis, Node.js, FFmpeg.
2.  **Setup Database**: Ensure Postgres and Redis are running.
3.  **Install Python Dependencies**:
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install -r bot-music-casino/requirements.txt
    pip install -r bot-cinema/requirements.txt
    pip install -r api/requirements.txt
    pip install -e common/
    ```
4.  **Run Services** (in separate terminals):
    ```bash
    python bot-music-casino/main.py
    python bot-cinema/main.py
    uvicorn api.main:app --reload
    ```
5.  **Run Frontend**:
    ```bash
    cd activity && npm install && npm run dev
    ```

---

## 🛠️ Configuration
*   **Casino Odds**: Edit `bot-music-casino/cogs/economy_cog.py` to change `Win Rates` and `Multipliers`.
*   **Shop Items**: Edit `shop` command in `economy_cog.py`.

## 🤝 Contributing
1.  Fork the repository.
2.  Create a feature branch.
3.  Submit a Pull Request.

## 📄 License
MIT License
