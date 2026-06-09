"""Task 1: helpers for collected legal documents."""

from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "legal"
VALID_EXTENSIONS = {".pdf", ".docx", ".doc"}


def setup_directory() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def list_legal_documents() -> list[Path]:
    setup_directory()
    return sorted(
        file for file in DATA_DIR.iterdir()
        if file.is_file() and file.suffix.lower() in VALID_EXTENSIONS and file.stat().st_size > 1024
    )


def task1_status() -> dict:
    files = list_legal_documents()
    return {
        "directory": str(DATA_DIR),
        "count": len(files),
        "complete": len(files) >= 3,
        "files": [file.name for file in files],
    }


if __name__ == "__main__":
    print(task1_status())
