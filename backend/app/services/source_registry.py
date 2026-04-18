from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SourceDefinition:
    name: str
    group: str
    source_type: str
    base_url: str
    start_url: str
    region: str
    priority: int
    article_prefixes: tuple[str, ...] = field(default_factory=tuple)
    article_contains: tuple[str, ...] = field(default_factory=tuple)
    title_selectors: tuple[str, ...] = field(default_factory=tuple)
    content_selectors: tuple[str, ...] = field(default_factory=tuple)
    press_selectors: tuple[str, ...] = field(default_factory=tuple)
    latest_link_selectors: tuple[str, ...] = field(default_factory=tuple)
    article_excludes: tuple[str, ...] = field(default_factory=tuple)
    disabled: bool = False


SOURCE_DEFINITIONS: tuple[SourceDefinition, ...] = (
    SourceDefinition(
        name="Naver News Main",
        group="kr-news",
        source_type="html",
        base_url="https://news.naver.com/",
        start_url="https://news.naver.com/",
        region="KR",
        priority=100,
        article_prefixes=("https://n.news.naver.com/article/",),
        latest_link_selectors=("a[href^='https://n.news.naver.com/article/']", "a[href^='/article/']"),
        title_selectors=(".media_end_head_title", "h2#title_area"),
        content_selectors=("#dic_area", "#newsct_article"),
        press_selectors=(".media_end_head_top_press",),
    ),
    SourceDefinition(
        name="Daum News",
        group="kr-news",
        source_type="html",
        base_url="https://news.daum.net/",
        start_url="https://news.daum.net/",
        region="KR",
        priority=90,
        article_prefixes=("https://v.daum.net/v/",),
        latest_link_selectors=("a[href^='https://v.daum.net/v/']", "a[href^='/v/']"),
        title_selectors=("h3.tit_view", "h3.head_view"),
        content_selectors=(".article_view", ".news_view"),
        press_selectors=("#kakaoServiceLogo",),
    ),
    SourceDefinition(
        name="연합뉴스",
        group="kr-news",
        source_type="html",
        base_url="https://www.yna.co.kr/",
        start_url="https://www.yna.co.kr/news",
        region="KR",
        priority=95,
        article_contains=("/view/",),
        latest_link_selectors=("a[href*='/view/']",),
        title_selectors=(".tit01", "h1.tit", "h1"),
        content_selectors=(".story-news.article", "#articleWrap", ".article-txt"),
        press_selectors=(),
    ),
    SourceDefinition(
        name="KBS News",
        group="kr-news",
        source_type="html",
        base_url="https://news.kbs.co.kr/",
        start_url="https://news.kbs.co.kr/news/pc/main/main.html",
        region="KR",
        priority=85,
        article_contains=("/news/view.do",),
        latest_link_selectors=("a[href*='/news/view.do']",),
        title_selectors=(".headline-title", "h4#title", "h1"),
        content_selectors=("#cont_newstext", ".detail-body", ".news-contents", ".detail-contents"),
        press_selectors=(),
    ),
    SourceDefinition(
        name="Reuters World",
        group="global-news",
        source_type="html",
        base_url="https://www.reuters.com/",
        start_url="https://www.reuters.com/world/",
        region="GLOBAL",
        priority=92,
        article_prefixes=("https://www.reuters.com/world/", "https://www.reuters.com/business/"),
        latest_link_selectors=("a[href^='/world/']", "a[href^='/business/']"),
        title_selectors=("h1[data-testid='Heading']", "h1",),
        content_selectors=("[data-testid^='paragraph-']", "[data-testid='Body']", "article p"),
        press_selectors=(".article-body__byline",),
        disabled=True,
    ),
    SourceDefinition(
        name="BBC News",
        group="global-news",
        source_type="html",
        base_url="https://www.bbc.com/",
        start_url="https://www.bbc.com/news",
        region="GLOBAL",
        priority=88,
        article_contains=("/news/articles/", "/news/world-", "/news/business-", "/news/technology-"),
        latest_link_selectors=(
            "a[href^='/news/articles/']",
            "a[href^='https://www.bbc.com/news/articles/']",
            "a[href*='/news/world-']",
            "a[href*='/news/business-']",
            "a[href*='/news/technology-']",
        ),
        title_selectors=("h1",),
        content_selectors=("[data-component='text-block']", "main [data-component='text-block']", "article p"),
        press_selectors=(),
        article_excludes=("/sport/", "/travel/", "/culture/", "/video", "/live/", "/weather"),
    ),
    SourceDefinition(
        name="AP News",
        group="global-news",
        source_type="html",
        base_url="https://apnews.com/",
        start_url="https://apnews.com/",
        region="GLOBAL",
        priority=86,
        article_prefixes=("https://apnews.com/article/",),
        latest_link_selectors=("a[href^='/article/']", "a[href^='https://apnews.com/article/']"),
        title_selectors=("h1",),
        content_selectors=(".RichTextStoryBody p", ".RichTextStoryBody", "[data-key='article'] p", "article p"),
        press_selectors=(),
    ),
    SourceDefinition(
        name="GNews API",
        group="news-api",
        source_type="api",
        base_url="https://gnews.io/",
        start_url="https://gnews.io/api/v4/top-headlines",
        region="GLOBAL",
        priority=70,
    ),
    SourceDefinition(
        name="X Experimental",
        group="x-experimental",
        source_type="experimental_x",
        base_url="https://x.com/",
        start_url="https://x.com/",
        region="GLOBAL",
        priority=50,
    ),
)


def get_source_definitions(group: str | None = None) -> list[SourceDefinition]:
    if group is None:
        return [definition for definition in SOURCE_DEFINITIONS if not definition.disabled]
    return [definition for definition in SOURCE_DEFINITIONS if definition.group == group and not definition.disabled]
