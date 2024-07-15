import json
import boto3
import feedparser
from datetime import datetime, timezone, timedelta

# AWSのニュースフィードのURL
AWS_RSS_URL = "https://aws.amazon.com/about-aws/whats-new/recent/feed/"

def handler(event, context):
    news_items = get_aws_news()
    
    return {
        "articles": news_items
    }

def get_aws_news():
    current_date = datetime.now(timezone.utc)
    five_days_ago = current_date - timedelta(days=5)
    feed = feedparser.parse(AWS_RSS_URL)

    news_items = []
    for entry in feed.entries:
        try:
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            if published >= five_days_ago:
                news_items.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": published.isoformat()
                })
        except (AttributeError, TypeError):
            # published_parsed が存在しないか、不正な形式の場合はスキップ
            continue

    return news_items