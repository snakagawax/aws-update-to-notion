import json
import logging
import os
import traceback
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import boto3
import pytz
import requests
from botocore.exceptions import ClientError
from bs4 import BeautifulSoup
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

# ロガーの設定
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def log_debug(message, **kwargs):
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": "DEBUG",
        "message": message
    }
    for key, value in kwargs.items():
        if isinstance(value, bytes):
            log_entry[key] = value.decode('utf-8', errors='replace')
        elif isinstance(value, (int, float, str, bool, type(None))):
            log_entry[key] = value
        else:
            log_entry[key] = str(value)
    logger.info(json.dumps(log_entry, ensure_ascii=False))


def get_parameter(name):
    ssm = boto3.client('ssm')
    try:
        response = ssm.get_parameter(Name=name, WithDecryption=True)
        return response['Parameter']['Value']
    except ClientError as e:
        log_debug(f"Error retrieving parameter {name}", error=str(e))
        raise


# 環境変数から値を取得
NOTION_API_KEY_PARAM = os.environ['NOTION_API_KEY_PARAM']
NOTION_DB_ID_PARAM = os.environ['NOTION_DB_ID_PARAM']
OPENAI_API_KEY_PARAM = os.environ['OPENAI_API_KEY_PARAM']
SERVICES_TABLE_NAME = os.environ['SERVICES_TABLE_NAME']

try:
    NOTION_API_KEY = get_parameter(NOTION_API_KEY_PARAM)
    DB_ID = get_parameter(NOTION_DB_ID_PARAM)
    OPENAI_API_KEY = get_parameter(OPENAI_API_KEY_PARAM)
    log_debug("Parameters retrieved successfully")
except Exception as e:
    log_debug("Error retrieving parameters", error=str(e))
    raise

client = OpenAI(api_key=OPENAI_API_KEY)
NOTION_API_URL = "https://api.notion.com/v1/pages"
dynamodb = boto3.resource('dynamodb')
services_table = dynamodb.Table(SERVICES_TABLE_NAME)


def get_aws_service_list():
    try:
        response = services_table.scan()
        additional_services = [
            (item['service_name'], item['abbreviation'])
            for item in response['Items']
        ]
        service_dict = {full: abbr for full, abbr in additional_services}
        services = set(service_dict.keys()).union(set(service_dict.values()))
        service_list = sorted(list(services))
        log_debug("AWS service list retrieved", service_count=len(service_list))
        return service_list, service_dict
    except ClientError as e:
        log_debug("Error retrieving AWS service list", error=str(e))
        raise


def tag_article(article_title, service_list, service_dict):
    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

    prompt = f"""You are an AI assistant that tags AWS article titles with 
    relevant AWS service names. Your task is to identify the specific AWS 
    service mentioned in the given article title. Follow these rules strictly:

    1. Use the exact AWS service names as provided in the list, preferring 
       abbreviations when available.
    2. For services with known abbreviations (e.g., "AWS IAM" for "AWS Identity 
       and Access Management"), use the abbreviation.
    3. If the article mentions a specific feature of a service, tag it with 
       the main service name or its abbreviation.
    4. For new services like Amazon Q, use the exact name as provided in the 
       list.
    5. If multiple services are mentioned, return only the most relevant one.
    6. If no relevant service is found, if the article is about a general AWS 
       feature, program, or internal tool (like AWS Partner Central), respond 
       with 'Not Found'.
    7. Respond with ONLY the relevant AWS service name or 'Not Found'. Do not 
       include any other text.
    8. Be precise in matching service names. Only use the exact names from the 
       provided list.

    AWS service names (with abbreviations when available):
    {', '.join([f"{full} ({abbr})" if full != abbr else full 
                for full, abbr in service_dict.items()])}
    {', '.join(service for service in service_list 
               if service not in service_dict.keys() 
               and service not in service_dict.values())}

    Article title: {article_title}

    Your response:"""

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 300,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2,
        "top_p": 0.99,
        "top_k": 250
    })

    try:
        log_debug("Invoking Bedrock model for tagging",
                  article_title=article_title)
        response = bedrock.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            contentType="application/json",
            accept="application/json",
            body=body
        )
        response_body = json.loads(response['body'].read())
        result = response_body['content'][0]['text'].strip()

        if result != 'Not Found' and (result in service_list or
                                      result in service_dict.values()):
            log_debug("Article tagged successfully",
                      article_title=article_title, tag=result)
            return [result]
        log_debug("No relevant tag found", article_title=article_title)
        return []
    except Exception as e:
        log_debug("Error tagging article", error=str(e),
                  traceback=traceback.format_exc(),
                  article_title=article_title)
        return []


@retry(stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=1, min=4, max=10))
def call_openai_api(messages):
    return client.chat.completions.create(
        model="gpt-4",
        messages=messages
    )


def translate_text(text):
    try:
        log_debug("Translating text", text_length=len(text))
        response = call_openai_api([
            {"role": "system", "content": "You are a helpful assistant that "
                                          "translates English to Japanese."},
            {"role": "user", "content": f"Translate the following English "
                                        f"text to Japanese:\n\n{text}"}
        ])
        translated_text = response.choices[0].message.content.strip()
        translated_lines = translated_text.split('\n')
        result = '\n'.join(translated_lines[1:]
                           if len(translated_lines) > 1
                           else translated_lines)
        log_debug("Text translated successfully",
                  original_length=len(text),
                  translated_length=len(result))
        return result
    except Exception as e:
        log_debug("Error translating text",
                  error=str(e), error_type=type(e).__name__)
        return f"翻訳エラー: {str(e)}"


def generate_summary(text):
    try:
        log_debug("Generating summary", text_length=len(text))
        response = call_openai_api([
            {"role": "system", "content": "You are a helpful assistant that "
                                          "summarizes Japanese text in the "
                                          "most important 3 bullet points."},
            {"role": "user", "content": f"以下の日本語テキストの最も重要な3つの"
                                        f"ポイントを箇条書きで簡潔に要約してくだ"
                                        f"さい：\n\n{text}"}
        ])
        summary = response.choices[0].message.content.strip()
        summary_lines = summary.split('\n')
        formatted_summary = '\n'.join([
            f"- {line.lstrip('•- ').strip()}"
            for line in summary_lines if line.strip()
        ])
        log_debug("Summary generated successfully",
                  summary_length=len(formatted_summary))
        return formatted_summary
    except Exception as e:
        log_debug("Error generating summary",
                  error=str(e), error_type=type(e).__name__)
        return "要約を生成できませんでした。エラー: " + str(e)


def scrape_and_translate_article_content(url):
    try:
        log_debug("Scraping article content", url=url)
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        content_div = soup.find('div', id='aws-page-content')
        if content_div:
            paragraphs = content_div.find_all('p')
            content = '\n\n'.join([p.get_text() for p in paragraphs])

            log_debug("Article content scraped", content_length=len(content))

            original_content = content
            translated_content = translate_text(content)
            summary = generate_summary(translated_content)

            urls = [
                a['href'] for a in content_div.find_all('a', href=True)
                if a['href'].startswith('http')
            ]

            log_debug("Article content processed",
                      url=url,
                      content_length=len(content),
                      translated_length=len(translated_content),
                      summary_length=len(summary),
                      url_count=len(urls))
            return {
                "summary": summary,
                "translated_content": translated_content,
                "original_content": original_content,
                "urls": urls
            }
        else:
            log_debug("Could not find content div", url=url)
            return {
                "summary": "記事の本文を抽出できませんでした。",
                "translated_content": "記事の本文を抽出できませんでした。",
                "original_content": "",
                "urls": []
            }
    except Exception as e:
        log_debug("Error scraping article content", error=str(e), url=url)
        return {
            "summary": "記事の本文を取得できませんでした。",
            "translated_content": "記事の本文を取得できませんでした。",
            "original_content": "",
            "urls": []
        }


def add_to_notion(item, tags, article_content):
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
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

    content_blocks = split_content(article_content['translated_content'])
    original_blocks = split_content(article_content['original_content'])

    children = [
        {"object": "block", "type": "heading_2", "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": "要約"}}]
        }},
    ] + [
        {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {
            "rich_text": [{"type": "text", "text": {"content": line.lstrip('- ')}}]
        }}
        for line in article_content['summary'].split('\n') if line.strip()
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
        for url in article_content['urls']
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

    if 'published' in item and item['published']:
        try:
            published_date = datetime.fromisoformat(item['published'])
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
        "parent": {"database_id": DB_ID},
        "properties": {
            "タイトル": {
                "title": [{"text": {"content": item['title'][:2000]}}]
            },
            "URL": {
                "url": item['link']
            },
            "公開日時": {
                "date": {"start": iso_date}
            }
        },
        "children": children
    }

    if tags:
        data["properties"]["タグ"] = {
            "multi_select": [{"name": tag} for tag in tags]
        }

    try:
        response = requests.post(NOTION_API_URL, headers=headers, json=data)
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


def handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")
    try:
        log_debug("Starting article processing",
                  article_title=event['title'],
                  article_link=event['link'])

        service_list, service_dict = get_aws_service_list()
        log_debug("AWS service list retrieved",
                  service_count=len(service_list))

        tags = tag_article(event['title'], service_list, service_dict)
        log_debug("Article tagged",
                  article_title=event['title'],
                  tags=tags)

        article_content = scrape_and_translate_article_content(event['link'])
        log_debug("Article content scraped and translated",
                  article_title=event['title'],
                  content_length=len(article_content['translated_content']))

        notion_result = add_to_notion(event, tags, article_content)

        result = {
            'articleTitle': event['title'],
            'tags': tags,
            'addedToNotion': notion_result is not None,
            'notionPageId': notion_result
        }
        log_debug("Article processing completed", result=result)
        return {
            'statusCode': 200 if notion_result else 500,
            'body': json.dumps(result)
        }
    except Exception as e:
        error_info = {
            'error': str(e),
            'trace': traceback.format_exc()
        }
        log_debug("Error processing article", error_info=error_info)
        return {
            'statusCode': 500,
            'body': json.dumps(error_info)
        }