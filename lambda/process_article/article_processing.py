import json
import traceback
import boto3
from bs4 import BeautifulSoup
import requests
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from logger import log_debug
from aws_services import get_parameter

def initialize_openai_client(openai_api_key_param):
    """
    OpenAI クライアントを初期化する関数

    Args:
        openai_api_key_param (str): OpenAI API キーを格納するパラメータ名

    Returns:
        OpenAI: 初期化された OpenAI クライアントインスタンス
    """
    openai_api_key = get_parameter(openai_api_key_param)
    return OpenAI(api_key=openai_api_key)

@retry(stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=1, min=4, max=10))
def call_openai_api(messages, openai_api_key_param):
    """
    OpenAI APIを呼び出す関数（リトライ機能付き）

    Args:
        messages (list): APIに送信するメッセージのリスト
        openai_api_key_param (str): OpenAI API キーを格納するパラメータ名

    Returns:
        dict: OpenAI APIのレスポンス
    """
    client = initialize_openai_client(openai_api_key_param)
    return client.chat.completions.create(
        model="gpt-4",
        messages=messages
    )

def tag_article(article_title, service_list, service_dict, openai_api_key_param):
    """
    記事のタイトルに基づいてAWSサービスのタグを付ける関数

    Args:
        article_title (str): 記事のタイトル
        service_list (list): AWSサービス名のリスト
        service_dict (dict): サービス名とその略称の辞書
        openai_api_key_param (str): OpenAI API キーを格納するパラメータ名

    Returns:
        list: タグのリスト
    """
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

    try:
        log_debug("Invoking OpenAI model for tagging",
                  article_title=article_title)
        response = call_openai_api([
            {"role": "system", "content": "You are an AI assistant that tags AWS article titles."},
            {"role": "user", "content": prompt}
        ], openai_api_key_param)
        
        result = response.choices[0].message.content.strip()

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

def translate_text(text, openai_api_key_param):
    """
    テキストを英語から日本語に翻訳する関数

    Args:
        text (str): 翻訳する英語のテキスト
        openai_api_key_param (str): OpenAI API キーを格納するパラメータ名

    Returns:
        str: 翻訳された日本語のテキスト
    """
    try:
        log_debug("Translating text", text_length=len(text))
        response = call_openai_api([
            {"role": "system", "content": "You are a helpful assistant that "
                                          "translates English to Japanese."},
            {"role": "user", "content": f"Translate the following English "
                                        f"text to Japanese:\n\n{text}"}
        ], openai_api_key_param)
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

def generate_summary(text, openai_api_key_param):
    """
    日本語テキストの要約を生成する関数

    Args:
        text (str): 要約する日本語のテキスト
        openai_api_key_param (str): OpenAI API キーを格納するパラメータ名

    Returns:
        str: 生成された要約
    """
    try:
        log_debug("Generating summary", text_length=len(text))
        response = call_openai_api([
            {"role": "system", "content": "You are a helpful assistant that "
                                          "summarizes Japanese text in the "
                                          "most important 3 bullet points."},
            {"role": "user", "content": f"以下の日本語テキストの最も重要な3つの"
                                        f"ポイントを箇条書きで簡潔に要約してくだ"
                                        f"さい：\n\n{text}"}
        ], openai_api_key_param)
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

def scrape_and_translate_article_content(url, openai_api_key_param):
    """
    記事のコンテンツをスクレイピングし、翻訳と要約を行う関数

    Args:
        url (str): 記事のURL
        openai_api_key_param (str): OpenAI API キーを格納するパラメータ名

    Returns:
        dict: スクレイピング、翻訳、要約された記事の内容
    """
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
            translated_content = translate_text(content, openai_api_key_param)
            summary = generate_summary(translated_content, openai_api_key_param)

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