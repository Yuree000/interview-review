# Interview Review

Local-first interview review workspace built with Streamlit.

The app takes a recorded interview, generates a transcript with speaker attribution, extracts high-value QA pairs, produces AI reference answers for each question, and renders a readable review report. It also supports resume import, single-run history, cross-interview comparison, and a global capability profile.

> **Note:** This tool is primarily designed for **Chinese-language interviews**. The ASR processing, QA extraction, and reporting pipelines are optimized for Mandarin Chinese content.

## Features

- Local Windows workflow for large interview audio and video files
- Tencent Cloud ASR transcription with COS upload for large media
- High-value QA extraction from full interview transcript
- AI reference answers and per-question review
- Markdown review report generation
- Resume import from `PDF / DOCX / TXT / MD`
- History, growth comparison, dashboard, and profile pages

## Tech Stack

- Python
- Streamlit
- Tencent Cloud ASR (Chinese ASR optimized)
- Tencent Cloud COS
- Kimi / Moonshot API

## Requirements

- Windows
- Python 3.11+ recommended
- FFmpeg and FFprobe available in PATH
- Tencent Cloud credentials for ASR and COS
- Kimi / Moonshot API key

## Quick Start

1. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

2. Copy the example environment file:

```bash
copy .env.example .env
```

3. Fill in the required values in `.env`.

4. Run the built-in self-check:

```bash
.\.venv\Scripts\python.exe -m scripts.self_check
```

5. Start the app:

```bash
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Or use the Windows helper:

```bash
.\start_app.bat
```

Environment check only:

```bash
.\start_app.bat --check
```

## Environment Variables

Required in normal use:

- `TENCENT_SECRET_ID`
- `TENCENT_SECRET_KEY`
- `ASR_REGION`
- `COS_REGION`
- `COS_BUCKET`
- `LLM_API_KEY`

Important optional values:

- `ASR_ENGINE_MODEL`
- `COS_PREFIX`
- `COS_URL_EXPIRE_SECONDS`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `LLM_STRUCTURED_MODEL`
- `FFMPEG_BINARY`
- `FFPROBE_BINARY`

See `.env.example` for the full template.

## Usage Flow

1. Open `New Analysis`
2. Choose a local interview media file
3. Run the full pipeline
4. Review:
   - transcript text
   - extracted QA pairs
   - AI reference answers
   - final report
5. Use `History`, `Growth`, and `Profile` for follow-up review

## Project Structure

- `app.py`: app entry
- `pages/`: Streamlit pages
- `ui/`: shared UI shell and analysis renderers
- `part_a/`: validation, audio extraction, COS, ASR
- `part_b/`: QA extraction, analysis, reporting
- `services/`: repository and orchestration services
- `scripts/`: self-check and gate runners
- `tests/`: gate and runtime tests

## Development Checks

```bash
.\.venv\Scripts\python.exe -m scripts.self_check
.\.venv\Scripts\python.exe -m scripts.run_phase1_gate
.\.venv\Scripts\python.exe -m scripts.run_phase2_gate
.\.venv\Scripts\python.exe -m scripts.run_phase3_gate
.\.venv\Scripts\python.exe -m scripts.run_phase4_gate
.\.venv\Scripts\python.exe -m scripts.run_phase5_gate
.\.venv\Scripts\python.exe -m scripts.run_phase6_gate
```

## Security Notes

- Never commit `.env`
- Never commit real interview videos, transcripts, reports, or resumes
- Rotate any credential that was ever shared in chat, screenshots, or documents
- Use a low-privilege Tencent Cloud key for development

See `SECURITY.md`.

## Contributing

See `CONTRIBUTING.md`.

## License

This project is released under the MIT License. See `LICENSE`.

## Limitations

- **Language Support**: Currently optimized for **Chinese (Mandarin)** interviews only. English and other language support is planned for future releases.
- **Cloud Dependency**: Requires Tencent Cloud ASR/COS services (China region). You may need to adapt the code for other cloud providers in your region.
- **Platform**: Primarily tested on Windows. Linux/macOS support is experimental.
