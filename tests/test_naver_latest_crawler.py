from bs4 import BeautifulSoup

from backend.app.services.issue_ingestion import build_unique_hash
from backend.app.services.naver_latest_crawler import NaverLatestNewsCrawler


def test_extract_article_fields_from_html():
    html = """
    <html>
      <head>
        <meta property="og:article:author" content="문화일보 | 네이버" />
      </head>
      <body>
        <div class="media_end_head_title">기사 제목</div>
        <span class="_ARTICLE_DATE_TIME" data-date-time="2026-04-16 17:00:09"></span>
        <span class="media_end_head_top_press">문화일보</span>
        <article id="dic_area">
          첫 문장입니다.
          <script>ignored()</script>
          <div>둘째 문장입니다.</div>
        </article>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")

    assert NaverLatestNewsCrawler._extract_title(soup) == "기사 제목"
    assert NaverLatestNewsCrawler._extract_press_name(soup) == "문화일보"
    assert NaverLatestNewsCrawler._extract_published_at(soup) is not None
    assert NaverLatestNewsCrawler._extract_content(soup) == "첫 문장입니다. 둘째 문장입니다."


def test_build_unique_hash_is_stable():
    article_url = "https://n.news.naver.com/article/021/0002785289"
    assert build_unique_hash(article_url) == build_unique_hash(article_url)
