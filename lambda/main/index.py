import json
import boto3
import os
from aws_news_fetcher import get_aws_news

def handler(event, context):
    news_items = get_aws_news()
    
    sfn_client = boto3.client('stepfunctions')
    
    input_data = {
        "articles": news_items
    }
    
    print(f"Step Functions input: {json.dumps(input_data)}")  # デバッグ用ログ
    
    response = sfn_client.start_execution(
        stateMachineArn=os.environ['STATE_MACHINE_ARN'],
        input=json.dumps(input_data)
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps(f'Step Functions execution started: {response["executionArn"]}')
    }