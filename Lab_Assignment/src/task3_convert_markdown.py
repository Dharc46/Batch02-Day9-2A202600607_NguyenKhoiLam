"""Task 3: convert landing files into markdown.

This module avoids requiring network-installed packages. It converts DOCX with
the Python standard library, PDF through the locally available `pdftotext`
binary, and legacy DOC through Word COM when available with a binary-text
fallback.
"""

import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree

try:
    from markitdown import MarkItDown
except Exception:  # Optional dependency; the fallback keeps the pipeline usable.
    MarkItDown = None

LANDING_DIR = Path(__file__).parent.parent / "data" / "landing"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "standardized"


def _clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_docx(filepath: Path) -> str:
    paragraphs = []
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(filepath) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    for paragraph in root.findall(".//w:p", namespace):
        runs = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
        if runs:
            paragraphs.append("".join(runs))
    return _clean_text("\n\n".join(paragraphs))


def _extract_pdf(filepath: Path) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(filepath))
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        text = _clean_text(text)
        if text:
            return text
    except Exception:
        pass

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        output_path = Path(tmp.name)
    try:
        commands = [
            ["pdftotext", "-layout", "-enc", "UTF-8", str(filepath), str(output_path)],
            ["pdftotext", str(filepath), str(output_path)],
        ]
        for command in commands:
            try:
                subprocess.run(command, check=True, capture_output=True, text=True)
                text = _clean_text(output_path.read_text(encoding="utf-8", errors="ignore"))
                if text:
                    return text
            except Exception:
                continue
        return _extract_pdf_binary(filepath)
    finally:
        output_path.unlink(missing_ok=True)


def _extract_pdf_binary(filepath: Path) -> str:
    data = filepath.read_bytes()
    decoded = data.decode("latin-1", errors="ignore")
    snippets = re.findall(r"[\wÀ-ỹĐđ ,.;:!?()/%+\-–—]{20,}", decoded)
    return _clean_text("\n".join(snippet.strip() for snippet in snippets if snippet.strip()))


def _extract_doc_with_word(filepath: Path) -> str:
    import win32com.client  # type: ignore

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        output_path = Path(tmp.name)
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    try:
        document = word.Documents.Open(str(filepath.resolve()), ReadOnly=True)
        document.SaveAs(str(output_path.resolve()), FileFormat=7)
        document.Close(False)
        return _clean_text(output_path.read_text(encoding="utf-8", errors="ignore"))
    finally:
        word.Quit()
        output_path.unlink(missing_ok=True)


def _extract_doc_binary(filepath: Path) -> str:
    data = filepath.read_bytes()
    decoded = data.decode("utf-16le", errors="ignore")
    snippets = re.findall(r"[\wÀ-ỹĐđ ,.;:!?()/%+\-–—\n]{20,}", decoded)
    text = "\n".join(snippet.strip() for snippet in snippets if snippet.strip())
    return _clean_text(text)


def extract_file_text(filepath: Path) -> str:
    suffix = filepath.suffix.lower()
    if MarkItDown:
        try:
            return _clean_text(MarkItDown().convert(str(filepath)).text_content)
        except Exception:
            pass
    if suffix == ".docx":
        return _extract_docx(filepath)
    if suffix == ".pdf":
        return _extract_pdf(filepath)
    if suffix == ".doc":
        try:
            return _extract_doc_with_word(filepath)
        except Exception:
            return _extract_doc_binary(filepath)
    return filepath.read_text(encoding="utf-8", errors="ignore")


def convert_legal_docs() -> None:
    legal_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)
    if not legal_dir.exists():
        return

    for filepath in sorted(legal_dir.iterdir()):
        if filepath.suffix.lower() not in {".pdf", ".docx", ".doc"}:
            continue
        output_path = output_dir / f"{filepath.stem}.md"
        text = extract_file_text(filepath)
        content = f"# {filepath.stem}\n\n**Source file:** {filepath.name}\n\n---\n\n{text}\n"
        output_path.write_text(content, encoding="utf-8")


def convert_news_articles() -> None:
    news_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)
    if not news_dir.exists():
        return

    for filepath in sorted(news_dir.iterdir()):
        if filepath.suffix.lower() != ".json":
            continue
        data = json.loads(filepath.read_text(encoding="utf-8"))
        header = (
            f"# {data.get('title', 'Unknown')}\n\n"
            f"**Source:** {data.get('url', 'N/A')}\n"
            f"**Crawled:** {data.get('date_crawled', 'N/A')}\n"
            f"**Published:** {data.get('published', 'N/A')}\n\n---\n\n"
        )
        body = data.get("content_markdown") or data.get("content") or ""
        (output_dir / f"{filepath.stem}.md").write_text(header + body, encoding="utf-8")


def convert_all() -> None:
    convert_legal_docs()
    convert_news_articles()


if __name__ == "__main__":
    convert_all()
