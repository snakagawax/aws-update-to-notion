import boto3
from botocore.exceptions import ClientError
from common import log_debug, log_info, log_error

def get_aws_service_list(table_name):
    """
    DynamoDBテーブルからAWSサービスのリストを取得する関数

    Args:
        table_name (str): DynamoDBテーブルの名前

    Returns:
        tuple: (service_list, service_dict)
            service_list (list): AWSサービス名のリスト
            service_dict (dict): サービス名とその略称の辞書

    Raises:
        ClientError: DynamoDBへのアクセス中にエラーが発生した場合
    """
    dynamodb = boto3.resource('dynamodb')
    services_table = dynamodb.Table(table_name)

    try:
        response = services_table.scan()
        items = response['Items']
        
        # ページネーションの処理
        while 'LastEvaluatedKey' in response:
            response = services_table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response['Items'])

        service_dict = {item['service_name']: item['abbreviation'] for item in items}
        service_list = list(set(service_dict.keys()).union(set(service_dict.values())))
        
        log_debug("AWS service list retrieved", service_count=len(service_list))
        return service_list, service_dict
    except ClientError as e:
        log_error("Error retrieving AWS service list", error=str(e))
        raise