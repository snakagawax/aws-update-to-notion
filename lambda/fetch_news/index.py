import json
import boto3
import feedparser

def handler(event, context):
    # AWS のニュースフィードの URL
    rss_url = "https://aws.amazon.com/about-aws/whats-new/recent/feed/"
    
    # フィードを解析
    feed = feedparser.parse(rss_url)
    
    # 記事のリストを作成
    articles = []
    for entry in feed.entries[:10]:  # 最新の10記事を取得
        articles.append({
            "title": entry.title,
            "link": entry.link,
            "published": entry.published
        })
    
    return {
        "articles": articles
    }