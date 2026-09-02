import asyncio
import os
import random
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn
)

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION FROM ENV ---
API_ID = int(os.getenv('API_ID', 0))
API_HASH = os.getenv('API_HASH', '')
CHANNEL_LINK = os.getenv('CHANNEL_LINK')

# Fallback for channel link if it's an integer ID string
if CHANNEL_LINK and (CHANNEL_LINK.startswith('-') or CHANNEL_LINK.isdigit()):
    CHANNEL_LINK = int(CHANNEL_LINK)

DOWNLOAD_DIR = os.getenv('DOWNLOAD_DIR', 'MyDownloads')
MAX_DOWNLOADS = int(os.getenv('MAX_DOWNLOADS', 10))
MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', 200))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

COMPLETED_LOG = os.path.join(DOWNLOAD_DIR, "_completed.log")
SLEEP_CHANCE = 0.15
SLEEP_RANGE = (1.0, 2.5)

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

client = TelegramClient(
    'my_downloader_session',
    API_ID,
    API_HASH,
    connection_retries=None,
    request_retries=None,
    retry_delay=2,
    timeout=30,
    auto_reconnect=True,
)

queue = asyncio.Queue(maxsize=MAX_DOWNLOADS * 2)


def load_completed_ids():
    """Load previously downloaded message IDs to avoid re-downloading."""
    completed = set()
    if os.path.exists(COMPLETED_LOG):
        with open(COMPLETED_LOG, "r") as f:
            for line in f:
                line = line.strip()
                if line.isdigit():
                    completed.add(int(line))
    return completed


def mark_completed(message_id):
    """Mark a message ID as downloaded safely."""
    with open(COMPLETED_LOG, "a") as f:
        f.write(f"{message_id}\n")
        f.flush()
        os.fsync(f.fileno())


completed_ids = load_completed_ids()


async def downloader_worker(worker_id, progress):
    while True:
        message = await queue.get()
        if message is None:
            queue.task_done()
            break

        filename = message.file.name or f"file_{message.id}{message.file.ext or '.mp4'}"
        file_path = os.path.join(DOWNLOAD_DIR, filename)
        file_size = message.file.size or 0

        if message.id in completed_ids:
            queue.task_done()
            continue

        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass

        task_id = progress.add_task(f"[W{worker_id}] {filename[:15]}...", total=file_size)

        def progress_callback(current, total):
            progress.update(task_id, completed=current, total=total)

        try:
            await client.download_media(
                message,
                file=file_path,
                progress_callback=progress_callback,
            )

            mark_completed(message.id)
            completed_ids.add(message.id)

            if random.random() < SLEEP_CHANCE:
                await asyncio.sleep(random.uniform(*SLEEP_RANGE))

        except FloodWaitError as e:
            progress.console.print(
                f"[red][!] Worker {worker_id} rate limited. Waiting for {e.seconds} seconds...[/red]"
            )
            await asyncio.sleep(e.seconds)
            await queue.put(message)

        except Exception as e:
            progress.console.print(f"[red][x] Error downloading {filename}: {e}[/red]")

        finally:
            progress.remove_task(task_id)
            queue.task_done()


async def main():
    await client.start()
    print(f"[*] Downloader started | Folder: '{DOWNLOAD_DIR}' | Workers: {MAX_DOWNLOADS}")

    try:
        entity = await client.get_entity(CHANNEL_LINK)
    except Exception as e:
        print(f"[x] Failed to connect to channel/chat: {e}")
        return

    print(f"[*] Connected successfully! Downloading in parallel...\n")

    with Progress(
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=35),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        DownloadColumn(),
        "•",
        TransferSpeedColumn(),
        "•",
        TimeRemainingColumn(),
    ) as progress:

        workers = []
        for i in range(MAX_DOWNLOADS):
            workers.append(asyncio.create_task(downloader_worker(i + 1, progress)))

        skipped_large = 0
        async for message in client.iter_messages(entity, reverse=True):
            if message.media:
                size = message.file.size or 0
                if size > MAX_FILE_SIZE_BYTES:
                    skipped_large += 1
                    continue
                await queue.put(message)

        if skipped_large:
            print(f"[*] Skipped {skipped_large} files larger than {MAX_FILE_SIZE_MB}MB.")

        for _ in range(MAX_DOWNLOADS):
            await queue.put(None)

        await queue.join()
        await asyncio.gather(*workers)

    print("\n[+] All downloads completed successfully!")


if __name__ == '__main__':
    with client:
        client.loop.run_until_complete(main())
