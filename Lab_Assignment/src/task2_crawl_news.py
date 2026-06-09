"""Task 2: crawl or seed news articles into data/landing/news."""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"

ARTICLE_URLS = [
    "https://vnexpress.net/dien-vien-hai-huu-tin-bi-de-nghi-truy-to-7-15-nam-tu-4530802.html",
    "https://vietnammedia.vnanet.vn/news/dieu-tra-vu-nguoi-mau-dien-vien-andrea-aybar-lien-quan-ma-tuy-141332.htm",
    "https://dantri.com.vn/phap-luat/andrea-aybar-chi-dan-la-vu-dien-hinh-ve-nghe-si-su-dung-ma-tuy-tai-tphcm-20251208100850146.htm",
    "https://tienphong.vn/nhieu-nghe-si-viet-bi-bat-vi-dinh-vao-ma-tuy-post1649760.tpo",
    "https://ngoisao.vnexpress.net/nam-than-lai-nga-nhikolai-dinh-bi-bat-4762594.html",
]


def setup_directory() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


async def crawl_article(url: str) -> dict:
    """Fetch one article as raw HTML with required metadata.

    The repository also includes seeded JSON records, so this function is useful
    when network access is available but not required for tests.
    """
    request = Request(url, headers={"User-Agent": "Day08-RAG-Pipeline/1.0"})
    html = await asyncio.to_thread(lambda: urlopen(request, timeout=15).read().decode("utf-8", "ignore"))
    title_start = html.lower().find("<title>")
    title_end = html.lower().find("</title>")
    title = url
    if title_start != -1 and title_end != -1:
        title = html[title_start + len("<title>"):title_end].strip()
    return {
        "url": url,
        "title": title,
        "date_crawled": datetime.now(timezone.utc).isoformat(),
        "content_markdown": html,
    }


async def crawl_all() -> list[Path]:
    setup_directory()
    output_paths = []
    for index, url in enumerate(ARTICLE_URLS, 1):
        article = await crawl_article(url)
        output_path = DATA_DIR / f"article_{index:02d}.json"
        output_path.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")
        output_paths.append(output_path)
    return output_paths


def list_news_articles() -> list[Path]:
    setup_directory()
    return sorted(file for file in DATA_DIR.iterdir() if file.suffix.lower() in {".json", ".html", ".md", ".txt"})


if __name__ == "__main__":
    print([path.name for path in list_news_articles()])
