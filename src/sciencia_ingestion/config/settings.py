from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]

def _resolve_local_path(repo_root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()

def _load_env(repo_root: Path) -> None:
    env_path = repo_root / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(env_path)
        return
    except Exception:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'").strip('"'))

def sqlite_path_from_db_url(db_url: str) -> Path:
    p = urlparse(db_url)
    if p.scheme != "sqlite":
        raise RuntimeError(f"Only sqlite DB_URL supported. Got: {db_url}")
    path = p.path
    if path.startswith("/") and len(path) >= 3 and path[2] == ":":
        path = path[1:]  # /D:/... -> D:/...
    if not path:
        raise RuntimeError(f"Invalid sqlite DB_URL: {db_url}")
    return Path(path)

@dataclass(frozen=True)
class Settings:
    db_url: str
    db_path: Path
    data_root: Path
    logs_dir: Path
    raw_dir: Path
    checkpoints_dir: Path
    failure_queue: Path

def load_settings() -> Settings:
    repo = _repo_root()
    _load_env(repo)

    data_root = _resolve_local_path(repo, os.getenv("SCIENCIAAI_DATA_DIR", ".local/scienciaai"))

    db_url = os.getenv("DB_URL")
    if db_url:
        db_path = sqlite_path_from_db_url(db_url)
    else:
        db_path = data_root / "ingestion.db"
        db_url = f"sqlite:///{db_path.as_posix()}"

    return Settings(
        db_url=db_url,
        db_path=db_path,
        data_root=data_root,
        logs_dir=data_root / "logs",
        raw_dir=data_root / "raw_samples" / "google_play",
        checkpoints_dir=data_root / "checkpoints" / "google_play",
        failure_queue=data_root / "queues" / "google_play_failed.jsonl",
    )
