# Contributing

## Local Setup

1. Create `.venv`
2. Install dependencies from `requirements.txt`
3. Copy `.env.example` to `.env`
4. Fill in local credentials
5. Run `python -m scripts.self_check`

## Before Opening a Pull Request

- Run the relevant gate scripts under `scripts/`
- Make sure no real interview media, transcripts, or reports are included
- Make sure `.env` and any secrets are excluded
- Keep UI changes consistent with the shared shell in `ui/theme.py`

## Scope Guidance

- `part_a/`: input validation, audio extraction, COS, ASR
- `part_b/`: QA extraction, analysis, report generation
- `pages/` and `ui/`: Streamlit UX
- `services/`: orchestration and persistence

## Pull Request Notes

- Keep changes focused
- Include test commands in the PR description
- Mention any required environment or API changes

