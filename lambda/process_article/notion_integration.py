import requests
from datetime import datetime, timezone
import json
from common import log_debug, log_info, log_error, get_parameter

def add_to_notion(processed_article, notion_api_key_param, notion_db_id_param):
    """
    処理された記事の内容をNotionデータベースに追加する関数

    Args:
        processed_article (dict): 処理された記事の情報
        notion_api_key_param (str): Notion API キーを格納するパラメータ名
        notion_db_id_param (str): Notion データベース ID を格納するパラメータ名

    Returns:
        str: 作成されたNotionページのID、既存ページの場合はそのID、エラー時はNone
    """
    notion_api_key = get_parameter(notion_api_key_param)
    db_id = get_parameter(notion_db_id_param)

    headers = {
        "Authorization": f"Bearer {notion_api_key}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    # 既存のページをチェック
    existing_page_id = check_existing_notion_page(notion_api_key, db_id, processed_article['link'])
    if existing_page_id:
        log_info("Article already exists in Notion, skipping addition", article_link=processed_article['link'])
        return existing_page_id

    def split_content(content, max_length=2000):
        words = content.split()
        chunks = []
        current_chunk = []

        for word in words:
            if len(' '.join(current_chunk + [word])) <= max_length:
                current_chunk.append(word)
            else:
                chunks.append(' '.join(current_chunk))
                current_chunk = [word]

        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks

    content_blocks = split_content(processed_article['translated_content'])
    original_blocks = split_content(processed_article['original_content'])

    children = [
        {"object": "block", "type": "heading_2", "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": "要約"}}]
        }},
    ] + [
        {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {
            "rich_text": [{"type": "text", "text": {"content": line.lstrip('- ')}}]
        }}
        for line in processed_article['summary'].split('\n') if line.strip()
    ] + [
        {"object": "block", "type": "heading_2", "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": "内容"}}]
        }},
    ] + [
        {"object": "block", "type": "paragraph", "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": block}}]
        }}
        for block in content_blocks
    ] + [
        {"object": "block", "type": "heading_2", "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": "参考"}}]
        }},
    ] + [
        {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {
            "rich_text": [{"type": "text", "text": {"content": url}}]
        }}
        for url in processed_article['urls']
    ] + [
        {"object": "block", "type": "heading_2", "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": "原文"}}]
        }},
    ] + [
        {"object": "block", "type": "paragraph", "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": block}}]
        }}
        for block in original_blocks
    ]

    # 公開日時の処理
    if 'published' in processed_article and processed_article['published']:
        try:
            published_date = datetime.fromisoformat(processed_article['published'].replace('Z', '+00:00'))
            iso_date = published_date.isoformat()
        except ValueError:
            log_debug("Invalid date format, using current time", date=processed_article['published'])
            published_date = datetime.now(timezone.utc)
            iso_date = published_date.isoformat()
    else:
        log_debug("No published date provided, using current time")
        published_date = datetime.now(timezone.utc)
        iso_date = published_date.isoformat()

    data = {
        "parent": {"database_id": db_id},
        "properties": {
            "タイトル": {
                "title": [{"text": {"content": processed_article['title'][:2000]}}]
            },
            "URL": {
                "url": processed_article['link']
            },
            "公開日時": {
                "date": {"start": iso_date}
            }
        },
        "children": children
    }

    if processed_article['tags']:
        data["properties"]["タグ"] = {
            "multi_select": [{"name": tag} for tag in processed_article['tags']]
        }

    try:
        response = requests.post("https://api.notion.com/v1/pages", headers=headers, json=data)
        response.raise_for_status()
        return response.json()["id"]
    except requests.exceptions.RequestException as e:
        log_debug(
            "Error adding to Notion",
            error=str(e),
            status_code=e.response.status_code if hasattr(e, 'response') else None,
            content=e.response.content.decode('utf-8') if hasattr(e, 'response') else None,
            request_data=json.dumps(data, ensure_ascii=False)
        )
        return None

def check_existing_notion_page(notion_api_key, db_id, article_link):
    """
    Notionデータベース内に同じリンクを持つページが存在するかチェックする関数

    Args:
        notion_api_key (str): Notion API キー
        db_id (str): Notion データベース ID
        article_link (str): チェックする記事のリンク

    Returns:
        str: 既存ページのID、存在しない場合はNone
    """
    headers = {
        "Authorization": f"Bearer {notion_api_key}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    data = {
        "filter": {
            "property": "URL",
            "url": {
                "equals": article_link
            }
        }
    }

    try:
        response = requests.post(f"https://api.notion.com/v1/databases/{db_id}/query", headers=headers, json=data)
        response.raise_for_status()
        results = response.json().get("results", [])
        if results:
            log_debug("Found existing Notion page", article_link=article_link, page_id=results[0]["id"])
            return results[0]["id"]
        log_debug("No existing Notion page found", article_link=article_link)
        return None
    except requests.exceptions.RequestException as e:
        log_error("Error checking existing Notion page", error=str(e), article_link=article_link)
        return None