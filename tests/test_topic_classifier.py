from backend.app.services.html_source_crawler import HTMLSourceCrawler
from backend.app.services.source_registry import SourceDefinition
from backend.app.services.topic_classifier import classify_topic


def test_classify_topic_prefers_economy_keywords():
    topic, confidence = classify_topic(
        title="한은 금리 동결, 환율 변동성 확대",
        raw_content="한국은행이 기준금리를 동결했고 시장은 물가와 환율 흐름을 주시하고 있다.",
        source_name="연합뉴스",
    )
    assert topic == "경제"
    assert confidence >= 0.6


def test_html_source_crawler_extracts_article_links():
    source = SourceDefinition(
        name="Test News",
        group="kr-news",
        source_type="html",
        base_url="https://example.com/",
        start_url="https://example.com/",
        region="KR",
        priority=100,
        article_prefixes=("https://example.com/article/",),
    )
    html = """
    <html>
      <body>
        <a href="/article/1">기사1</a>
        <a href="/article/2">기사2</a>
        <a href="/about">소개</a>
      </body>
    </html>
    """
    links = HTMLSourceCrawler()._extract_article_links(source, html, limit=10)
    assert links == [
        "https://example.com/article/1",
        "https://example.com/article/2",
    ]


def test_html_source_crawler_aggregates_multiple_paragraphs():
    html = """
    <html>
      <body>
        <article>
          <p>첫 문장입니다.</p>
          <p>둘째 문장입니다.</p>
          <script>ignored()</script>
        </article>
      </body>
    </html>
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    text = HTMLSourceCrawler._extract_content(soup, ("article p",))
    assert text == "첫 문장입니다. 둘째 문장입니다."


def test_html_source_crawler_respects_article_excludes():
    source = SourceDefinition(
        name="BBC Test",
        group="global-news",
        source_type="html",
        base_url="https://www.bbc.com/",
        start_url="https://www.bbc.com/news",
        region="GLOBAL",
        priority=80,
        article_contains=("/news/articles/",),
        article_excludes=("/sport/", "/live/"),
    )
    assert HTMLSourceCrawler._is_article_link(source, "https://www.bbc.com/news/articles/c123") is True
    assert HTMLSourceCrawler._is_article_link(source, "https://www.bbc.com/sport/football/articles/c123") is False
