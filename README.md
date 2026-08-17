# Telegram Playlist & Video Batch Downloader

A high-speed Python script to download video series, playlists, or course modules sequentially (from oldest to newest) from any Telegram channel or group.

## Features

- **Sequential Downloading**: Downloads videos in original order (Part 1, Part 2, etc.) using `reverse=True`.
- **High-Speed Parallel Downloads**: Uses multi-worker async architecture to bypass Telegram's per-connection speed throttle.
- **Smart Resume**: Logs successfully downloaded video IDs in `_completed.log` to skip already downloaded content if restarted.
- **File Size Filter**: Automatically skips videos larger than your limit (Default: 200MB).
- **Interactive Progress Bar**: Live speed, remaining time, and progress updates using Rich console.

## Configuration

Open the script and edit your channel details:

```python
API_ID = 12345678  # Your Telegram API ID
API_HASH = "YOUR_API_HASH"  # Your Telegram API Hash

# Channel/Group target:
# Public:  CHANNEL_LINK = "channel_username"
# Private: CHANNEL_LINK = -1001234567890
CHANNEL_LINK = -1003246768376
