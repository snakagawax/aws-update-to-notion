import os
import json
import logging
import os
import traceback
from datetime import datetime, timezone

from common import log_debug, log_info, log_error, get_parameter
from aws_services import get_aws_service_list
from article_processing import process_article
from notion_integration import add_to_notion

# 環境変数から値を取得
NOTION_API_KEY_PARAM = os.environ['NOTION_API_KEY_PARAM']
NOTION_DB_ID_PARAM = os.environ['NOTION_DB_ID_PARAM']
OPENAI_API_KEY_PARAM = os.environ['OPENAI_API_KEY_PARAM']
SERVICES_TABLE_NAME = os.environ['SERVICES_TABLE_NAME']

def handler(event, context):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    log_info(f"Received event: {json.dumps(event)}")

    try:
        log_debug("Starting article processing",
                  article_title=event['title'],
                  article_link=event['link'])

        service_list, service_dict = get_aws_service_list(SERVICES_TABLE_NAME)
        
        # process_article 関数を使用して記事を処理
        processed_article = process_article(event, service_list, service_dict, OPENAI_API_KEY_PARAM)
        
        # 公開日時をprocessed_articleに追加
        processed_article['published'] = event.get('published')

        # Notionに追加（または既存ページIDを取得）
        notion_result = add_to_notion(processed_article, NOTION_API_KEY_PARAM, NOTION_DB_ID_PARAM)

        result = {
            'articleTitle': processed_article['title'],
            'tags': processed_article['tags'],
            'addedToNotion': notion_result is not None,
            'notionPageId': notion_result,
            'skipped': notion_result is not None and notion_result != processed_article['link']
        }
        log_info("Article processing completed", result=result)
        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }
    except Exception as e:
        error_info = {
            'error': str(e),
            'trace': traceback.format_exc()
        }
        log_error("Error processing article", error_info=error_info)
        return {
            'statusCode': 500,
            'body': json.dumps(error_info)
        }