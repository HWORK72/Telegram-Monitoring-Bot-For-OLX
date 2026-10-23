import os
import shutil
import subprocess
import sys
from pathlib import Path


def write_text_file(path: Path, content: str, executable: bool = False) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")
    if executable:
        os.chmod(path, 0o755)


def build_portable_package() -> None:
    root_dir: Path = Path(__file__).resolve().parent
    dist_dir: Path = root_dir / "dist" / "olx_bot"

    pyinstaller_cmd: list[str] = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--contents-directory",
        "internal",
        "--name",
        "olx_bot",
        "--collect-all",
        "curl_cffi",
        "--collect-all",
        "selectolax",
        "--collect-data",
        "certifi",
        "--hidden-import",
        "aiosqlite",
        "--hidden-import",
        "sqlalchemy.dialects.sqlite.aiosqlite",
        "--hidden-import",
        "aiohttp_socks",
        "main.py",
    ]

    subprocess.run(pyinstaller_cmd, check=True)

    env_source: Path = root_dir / ".env"
    env_target: Path = dist_dir / ".env"
    if env_source.exists():
        shutil.copy2(env_source, env_target)
    else:
        default_env: str = (
            "BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN\n"
            "ADMIN_IDS=8074283327\n"
            "PROXY_URL=\n"
            "IGNORE_BUMPED_OFFERS=false\n"
            "IGNORE_PROMOTED_OFFERS=false\n"
            "MAX_OFFER_AGE_MINUTES=30\n"
            "BATCH_OUTPUT_LIMIT=12\n"
            "MAX_PER_CATEGORY_PER_BATCH=2\n"
            "MAX_CONCURRENT_CHECKS=5\n"
            "POLL_INTERVAL_SECONDS=60\n"
            "POLL_JITTER_SECONDS=5\n"
            "REQUEST_TIMEOUT=15\n"
            "CURL_IMPERSONATE=chrome120\n"
            "LOG_LEVEL=INFO\n"
        )
        write_text_file(env_target, default_env)

    accounts_file: Path = dist_dir / "accounts.txt"
    write_text_file(accounts_file, "")

    start_mac: Path = dist_dir / "start.command"
    start_mac_content: str = (
        'cd "$(dirname "$0")"\n'
        "xattr -cr . 2>/dev/null || true\n"
        "chmod +x ./olx_bot\n"
        "./olx_bot\n"
    )
    write_text_file(start_mac, start_mac_content, executable=True)

    stop_mac: Path = dist_dir / "stop.command"
    stop_mac_content: str = "pkill -f olx_bot || true\n"
    write_text_file(stop_mac, stop_mac_content, executable=True)

    start_win: Path = dist_dir / "start.bat"
    start_win_content: str = (
        "@echo off\n"
        'cd /d "%~dp0"\n'
        "title OLX Monitor Bot\n"
        "olx_bot.exe\n"
        "pause\n"
    )
    write_text_file(start_win, start_win_content)

    stop_win: Path = dist_dir / "stop.bat"
    stop_win_content: str = (
        "@echo off\n"
        "taskkill /F /IM olx_bot.exe /T\n"
    )
    write_text_file(stop_win, stop_win_content)

    print(f"Portable build completed successfully at: {dist_dir}")


if __name__ == "__main__":
    build_portable_package()