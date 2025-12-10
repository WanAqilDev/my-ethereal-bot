# Changelog

All notable changes to this project will be documented in this file.

## [v1.1.0] - 2025-12-11

### Added
- **Prefetching System**: Automatically downloads the next 2 songs in the queue for gapless playback.
- **Persistent Volume**: Volume level now persists across songs and sessions (until stop/leave).
- **Queue System**:
    - Added `!queue` command with a pretty Embed display.
    - Added `!skip` command with graceful fade-out.
    - Added `!clear` command to empty the queue.
    - Enforced a **20 song limit** to prevent abuse.
- **Smart Caching**:
    - Downloads songs to a local `./cache` directory.
    - Automatically plays from cache if available, falling back to stream if not.
    - Auto-deletes files after playback to save disk space.

### Changed
- **Queue Display**: Now shows "Now Playing", "Up Next" (Top 10), and total count.
- **Playback Logic**: Optimized to handle local files and streams seamlessly.

## [v1.0.0] - 2025-12-09

### Added
- Initial Release.
- Basic `!play` command (streaming only).
- Basic `!join` and `!leave` commands.
- Docker support with `Dockerfile` and `docker-compose.yml`.
- GitHub Actions workflow for GHCR publishing.
