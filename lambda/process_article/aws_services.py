import boto3
from botocore.exceptions import ClientError
from logger import log_debug

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

def get_parameter(name):
    """
    AWS Systems Manager Parameter Storeからパラメータを取得する関数

    Args:
        name (str): パラメータ名

    Returns:
        str: パラメータの値

    Raises:
        ClientError: Parameter Storeへのアクセス中にエラーが発生した場合
    """
    ssm = boto3.client('ssm')
    try:
        response = ssm.get_parameter(Name=name, WithDecryption=True)
        return response['Parameter']['Value']
    except ClientError as e:
        log_debug(f"Error retrieving parameter {name}", error=str(e))
        raise