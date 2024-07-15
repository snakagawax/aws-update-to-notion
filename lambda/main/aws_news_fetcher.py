import feedparser
import datetime

def get_aws_news():
    # AWS の "What's New with AWS?" RSS フィードの URL
    rss_url = "https://aws.amazon.com/about-aws/whats-new/recent/feed/"
    
    # フィードを解析
    feed = feedparser.parse(rss_url)
    
    # 現在の日時を取得
    now = datetime.datetime.now(datetime.timezone.utc)
    
    # 1週間前の日時を計算
    one_week_ago = now - datetime.timedelta(days=7)
    
    news_items = []
    for entry in feed.entries:
        # エントリーの公開日時をパース
        published = datetime.datetime.fromtimestamp(
            time.mktime(entry.published_parsed),
            tz=datetime.timezone.utc
        )
        
        # 1週間以内の記事のみを取得
        if published >= one_week_ago:
            news_items.append({
                "title": entry.title,
                "link": entry.link,
                "published": published.isoformat()
            })
    
    print(f"Fetched {len(news_items)} news items")  # デバッグ用ログ
    return news_items