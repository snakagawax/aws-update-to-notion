import json
import logging
import os
import traceback
from datetime import datetime, timezone

from logger import log_debug, log_info, log_error
from aws_services import get_aws_service_list
from article_processing import tag_article, scrape_and_translate_article_content
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
        tags = tag_article(event['title'], service_list, service_dict, OPENAI_API_KEY_PARAM)
        article_content = scrape_and_translate_article_content(event['link'], OPENAI_API_KEY_PARAM)
        notion_result = add_to_notion(event, tags, article_content, NOTION_API_KEY_PARAM, NOTION_DB_ID_PARAM)

        result = {
            'articleTitle': event['title'],
            'tags': tags,
            'addedToNotion': notion_result is not None,
            'notionPageId': notion_result
        }
        log_info("Article processing completed", result=result)
        return {
            'statusCode': 200 if notion_result else 500,
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