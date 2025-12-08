# Discord Music Bot 🎵

A feature-rich Discord music bot built with `discord.py` and `yt-dlp`. Supports playing music from YouTube, volume control, queue management, and more.

## Features

- 🎶 Play music from YouTube (URL or search terms)
- ⏯️ Pause, Resume, Stop, Skip
- 🔊 Volume Control (`!volume 0-100`)
- 📜 Queue System
- 🚀 Robust playback (pipes audio directly to ffmpeg)

## Prerequisites

- **Python 3.8+**
- **FFmpeg** (Included in Docker, but required for local run)
- **Discord Bot Token** (Get one from the [Discord Developer Portal](https://discord.com/developers/applications))

## 🛠️ Local Setup & Running

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/WanAqilDev/sturdy-succotash.git
    cd sturdy-succotash
    ```

2.  **Create a virtual environment (optional but recommended):**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Install FFmpeg:**
    *   **Linux (Debian/Ubuntu):** `sudo apt install ffmpeg`
    *   **Windows:** Download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add to PATH.
    *   **MacOS:** `brew install ffmpeg`
    *   *Note: The bot is configured to look for `./ffmpeg` in the root directory by default if you downloaded a static binary. If you installed it globally, you might need to adjust the executable path in `music_cog.py`.*

5.  **Configure Environment:**
    Create a `.env` file in the root directory:
    ```env
    DISCORD_TOKEN=your_discord_bot_token_here
    ```

6.  **Run the bot:**
    ```bash
    python main.py
    ```

## 🐳 Running with Docker

You can run the bot in a container without installing Python or FFmpeg on your host machine.

1.  **Build the image:**
    ```bash
    sudo docker build -t discord-music-bot .
    ```
    *Note: If you encounter network errors, try restarting the docker service or checking your DNS settings.*

2.  **Run the container:**
    Replace `your_token_here` with your actual bot token.
    ```bash
    sudo docker run -d --name music-bot -e DISCORD_TOKEN=your_token_here discord-music-bot
    ```

## ☁️ Private Hosting Guide

To host this 24/7 on a VPS (Virtual Private Server) like DigitalOcean, Linode, or AWS EC2:

### Option 1: Using Docker (Recommended)
1.  SSH into your VPS.
2.  Install Docker.
3.  Clone the repo and follow the **Running with Docker** steps above.
4.  To ensure it restarts automatically:
    ```bash
    docker run -d --restart unless-stopped --name music-bot -e DISCORD_TOKEN=your_token_here discord-music-bot
    ```

### Option 2: Using Systemd (Linux Service)
1.  Follow the **Local Setup** steps on your VPS.
2.  Create a service file: `sudo nano /etc/systemd/system/musicbot.service`
3.  Paste the following (adjust paths/user):
    ```ini
    [Unit]
    Description=Discord Music Bot
    After=network.target

    [Service]
    User=root
    WorkingDirectory=/path/to/sturdy-succotash
    ExecStart=/path/to/sturdy-succotash/.venv/bin/python main.py
    Restart=always

    [Install]
    WantedBy=multi-user.target
    ```
4.  Enable and start:
    ```bash
    sudo systemctl start musicbot
    ```

### Option 3: Synology NAS

1.  **Install Container Manager**:
    *   Log in to your Synology DSM.
    *   Open **Package Center**.
    *   Search for and install **Container Manager** (formerly Docker).

2.  **Enable SSH**:
    *   Go to **Control Panel** > **Terminal & SNMP**.
    *   Check **Enable SSH service**.

3.  **Deploy**:
    *   SSH into your NAS: `ssh your_username@your_nas_ip`
    *   Clone the repo and run the Docker commands:
        ```bash
        git clone https://github.com/WanAqilDev/sturdy-succotash.git
        cd sturdy-succotash
        sudo docker build -t discord-music-bot .
        sudo docker run -d --name music-bot -e DISCORD_TOKEN=your_token_here --restart always discord-music-bot
        ```
