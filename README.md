# scienciaai-data-ingestion

## Quick Setup

1. Copy `.env.example` to `.env`.
2. Keep the default `SCIENCIAAI_DATA_DIR=.local/scienciaai` for a portable local setup, or point it at any writable directory on your machine.
3. Leave `DB_URL` unset to default to `<SCIENCIAAI_DATA_DIR>/ingestion.db`, or set it explicitly to an absolute SQLite path.
4. Install dependencies from `requirements.txt` in your virtual environment.

## Minimal Smoke Path

```bash
python scripts/collect_recent_window.py --app-id com.openai.chatgpt --target-days 21 --per-page 100 --max-pages 500 --num-buckets 10 --sample-per-bucket 100 --seed 0 --lang en --country us
python scripts/google_play_recent_window_raw_to_sqlite.py --raw-file ./data/checkpoints/com.openai.chatgpt_recent_window_raw_f942add8.jsonl --app-id com.openai.chatgpt --lang en --country us --batch-size 500
python scripts/verify_sqlite.py
```

## Evidence

Curated Phase I evidence is kept under `documents/` and `reports/current_chatgpt_20k_assessment/`.
Noisy machine-local run artifacts are intentionally kept out of canonical history.

## Project Status

See [documents/PHASE_I_INGESTION_VALIDATION_SUMMARY.md](documents/PHASE_I_INGESTION_VALIDATION_SUMMARY.md) for the current validated status and reviewable Phase I conclusions.

