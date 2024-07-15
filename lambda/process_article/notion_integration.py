import requests
from datetime import datetime, timezone
from common import log_debug, log_info, log_error, get_parameter

def add_to_notion(processed_article, notion_api_key_param, notion_db_id_param):
    """
    処理された記事の内容をNotionデータベースに追加する関数

    Args:
        processed_article (dict): 処理された記事の情報
        notion_api_key_param (str): Notion API キーを格納するパラメータ名
        notion_db_id_param (str): Notion データベース ID を格納するパラメータ名

    Returns:
        str: 作成されたNotionページのID、エラー時はNone
    """
    notion_api_key = get_parameter(notion_api_key_param)
    db_id = get_parameter(notion_db_id_param)

    headers = {
        "Authorization": f"Bearer {notion_api_key}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

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
            published_date = datetime.fromisoformat(processed_article['published'])
            if published_date.tzinfo is None:
                published_date = published_date.replace(tzinfo=timezone.utc)
            iso_date = published_date.isoformat()
        except ValueError:
            published_date = datetime.now(timezone.utc)
            iso_date = published_date.isoformat()
    else:
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