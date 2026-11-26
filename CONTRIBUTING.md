# Contributing to UPSC Studio

Thank you for your interest in contributing!

## Getting started

1. Fork the repository.
2. Clone your fork locally.
3. Create a virtual environment and install dev dependencies:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -e ".[docs,dev]"
   ```
4. Create a feature branch: `git checkout -b feature/my-feature`
5. Make your changes.
6. Run the test suite: `python -m pytest -v`
7. Commit and push your branch.
8. Open a Pull Request.

## Code style

- Python 3.11+ with type hints.
- Pydantic v2 for data models.
- Keep modules focused — one responsibility per file.
- Write tests for new features.

## Commit messages

Use clear, imperative-mood messages:
- `Add syllabus mapping for Mains GS-III`
- `Fix CSAT isolation in benchmark auditor`
- `Update FFmpeg render pipeline for section-wise output`

## Reporting issues

Open a GitHub issue with:
- Steps to reproduce.
- Expected vs. actual behaviour.
- Python version and OS.

## Licence

By contributing, you agree that your contributions are licensed under the MIT licence.
