import json
import traceback
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from common import log_debug, log_info, log_error, get_parameter

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
        model="gpt-4o",
        messages=messages
    )

def tag_article(article_title, article_content, service_list, service_dict, openai_api_key_param):
    """
    記事のタイトルと本文に基づいてAWSサービスのタグを1つ付ける関数（改善版）

    Args:
        article_title (str): 記事のタイトル
        article_content (str): 記事の本文
        service_list (list): AWSサービス名のリスト（この引数は使用しませんが、互換性のために残します）
        service_dict (dict): サービス名とその略称の辞書
        openai_api_key_param (str): OpenAI API キーを格納するパラメータ名

    Returns:
        list: 1つのタグを含むリスト、またはタグが見つからない場合は空のリスト
    """
    log_debug("Starting tag_article function", 
              article_title=article_title, 
              content_length=len(article_content),
              service_dict_length=len(service_dict))

    # service_dict から略称のリストを作成
    abbreviations = list(set(service_dict.values()))

    candidate_tags_prompt = f"""You are an AI assistant specialized in identifying the most relevant AWS service mentioned in technical articles. 
    Your task is to analyze the given article title and content, and identify the single most relevant AWS service.

    Rules:
    1. Identify the SINGLE most relevant AWS service, prioritizing the service mentioned in the title if applicable.
    2. Use the exact AWS service abbreviation as provided in the list, preserving the exact capitalization, spacing, and punctuation.
    3. If a specific feature of a service is mentioned, use the main service abbreviation.
    4. If no relevant service is found, respond with 'No relevant AWS service found'.
    5. Be precise in your identification - choose the service that best represents the main focus of the article.
    6. Do not confuse similar service names. Ensure you select the exact match from the provided list.
    7. Do not modify the service abbreviations in any way. Use them exactly as they appear in the list.

    Article title: {article_title}

    Article content (excerpt): {article_content[:2000]}  # 最初の2000文字を使用

    List of AWS service abbreviations (use exact abbreviations as provided):
    {', '.join(abbreviations)}

    Your response should be the single most relevant AWS service abbreviation, exactly as it appears in the list above:"""

    log_debug("Generated candidate tag prompt", prompt_length=len(candidate_tags_prompt))

    try:
        candidate_tag_response = call_openai_api([
            {"role": "system", "content": "You are an AI assistant that identifies the most relevant AWS service in technical articles."},
            {"role": "user", "content": candidate_tags_prompt}
        ], openai_api_key_param)
        
        log_debug("OpenAI API response received", response_length=len(str(candidate_tag_response)))

        candidate_tag = candidate_tag_response.choices[0].message.content.strip()
        log_debug("Received candidate tag from OpenAI", candidate_tag=candidate_tag)
        
        # 厳格なマッチング（完全一致）
        if candidate_tag in abbreviations:
            log_debug("Valid tag found (strict match)", valid_tag=candidate_tag)
            return [candidate_tag]
        
        # 緩和されたマッチング
        relaxed_match = None
        for abbr in abbreviations:
            if candidate_tag.lower() == abbr.lower():
                relaxed_match = abbr
                break
        
        if relaxed_match:
            log_debug("Valid tag found (relaxed match)", valid_tag=relaxed_match, original_suggestion=candidate_tag)
            return [relaxed_match]
        
        log_debug("No valid tag found", article_title=article_title, suggested_tag=candidate_tag)
        return []

    except Exception as e:
        log_debug("Error in tag_article", 
                  error=str(e),
                  error_type=type(e).__name__,
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

def process_article(event, service_list, service_dict, openai_api_key_param):
    """
    記事を処理する関数

    Args:
        event (dict): 処理する記事の情報
        service_list (list): AWSサービス名のリスト
        service_dict (dict): サービス名とその略称の辞書
        openai_api_key_param (str): OpenAI API キーを格納するパラメータ名

    Returns:
        dict: 処理された記事の情報
    """
    try:
        log_debug("Processing article", article_title=event['title'])
        
        article_content = scrape_and_translate_article_content(event['link'], openai_api_key_param)
        log_debug("Article content scraped and translated", article_title=event['title'], content_length=len(article_content['original_content']))
        
        log_debug("Starting tag_article", article_title=event['title'])
        tags = tag_article(event['title'], article_content['original_content'][:2000], service_list, service_dict, openai_api_key_param)
        log_debug("tag_article completed", article_title=event['title'], tags=tags)
        
        result = {
            'title': event['title'],
            'link': event['link'],
            'tags': tags,
            'summary': article_content['summary'],
            'translated_content': article_content['translated_content'],
            'original_content': article_content['original_content'],
            'urls': article_content['urls']
        }
        
        log_debug("Article processed successfully", article_title=event['title'], result=result)
        return result
    except Exception as e:
        log_debug("Error processing article", 
                  error=str(e), 
                  traceback=traceback.format_exc(),
                  article_title=event['title'])
        return {
            'title': event['title'],
            'link': event['link'],
            'error': str(e)
        }