from __future__ import annotations
import logging
from pathlib import Path

def setup_logger(logs_dir: Path, run_id: str) -> logging.Logger:
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("sciencia_ingestion")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger

    fmt = logging.Formatter("%(asctime)sZ | %(levelname)s | %(message)s")
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    fp = logs_dir / f"google_play_sample_{run_id}.log"
    fh = logging.FileHandler(fp, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    logger.info(f"log_file={fp}")
    return logger
