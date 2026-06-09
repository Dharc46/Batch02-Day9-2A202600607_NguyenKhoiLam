"""Environment loading helpers."""

from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_project_env() -> None:
    """Load the project .env file regardless of the current working directory."""
    load_dotenv(PROJECT_ROOT / ".env")
