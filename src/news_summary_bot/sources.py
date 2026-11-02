# name, RSS(優先), トップページ(フォールバック), 本文の無料度
from typing import TypedDict


class Source(TypedDict):
    name: str
    rss: str
    web: str
    paywall: str


US_SOURCES: list[Source] = [
    {
        "name": "Bloomberg",
        "rss": "https://feeds.bloomberg.com/markets/news.rss",
        "web": "https://www.bloomberg.com/markets",
        "paywall": "原則有料",
    },
    {
        "name": "WSJ",
        "rss": "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain",
        "web": "https://www.wsj.com/news/latest-headlines",
        "paywall": "ほぼ有料",
    },
    {
        "name": "Financial Times",
        "rss": "https://www.ft.com/rss/home",
        "web": "https://www.ft.com/markets",
        "paywall": "有料",
    },
    {
        "name": "The Economist",
        "rss": "https://www.economist.com/finance-and-economics/rss.xml",
        "web": "https://www.economist.com/",
        "paywall": "有料",
    },
    {
        "name": "CNBC",
        "rss": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "web": "https://www.cnbc.com/",
        "paywall": "多く無料",
    },
    {
        "name": "MarketWatch",
        "rss": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "web": "https://www.marketwatch.com/",
        "paywall": "多く無料",
    },
    {
        "name": "Investing.com日本版",
        "rss": "https://jp.investing.com/rss/news.rss",
        "web": "https://jp.investing.com/news/",
        "paywall": "多く無料",
    },
]

JP_SOURCES: list[Source] = [
    {
        "name": "Nikkei",
        "rss": "",  # 未指定のため空文字(型定義上 rss は必須)
        "web": "https://www.nikkei.com/",
        "paywall": "一部有料",
    },
    {
        "name": "Yahoo!ニュース 経済",
        "rss": "https://news.yahoo.co.jp/rss/categories/business.xml",
        "web": "https://news.yahoo.co.jp/categories/business",
        "paywall": "無料",
    },
    {
        "name": "NHK 経済",
        "rss": "https://news.web.nhk/n-data/conf/na/rss/cat5.xml",
        "web": "https://www3.nhk.or.jp/news/",
        "paywall": "無料",
    },
    {
        "name": "JPX マーケットニュース",
        "rss": "https://www.jpx.co.jp/rss/markets_news.xml",
        "web": "https://www.jpx.co.jp/",
        "paywall": "無料",
    },
    {
        "name": "日経ビジネス",
        "rss": "https://business.nikkei.com/rss/sns/nb.rdf",
        "web": "https://business.nikkei.com/",
        "paywall": "一部有料",
    },
]
