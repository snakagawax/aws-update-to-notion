import os
import boto3
import json
import time
from botocore.exceptions import ClientError
from common import log_debug, log_info, log_error

# 環境変数からDynamoDBテーブル名を取得
SERVICES_TABLE_NAME = os.environ['SERVICES_TABLE_NAME']

def get_all_aws_services():
    iam = boto3.client('iam')
    
    # ジョブの作成
    job_id = iam.generate_service_last_accessed_details(
        Arn='arn:aws:iam::aws:policy/AdministratorAccess'
    )['JobId']
    
    # ジョブの完了を待つ
    while True:
        response = iam.get_service_last_accessed_details(JobId=job_id)
        if response['JobStatus'] == 'COMPLETED':
            break
        time.sleep(1)
    
    services = []
    marker = None
    
    # ページネーションを使用して全てのサービスを取得
    while True:
        if marker:
            response = iam.get_service_last_accessed_details(JobId=job_id, Marker=marker)
        else:
            response = iam.get_service_last_accessed_details(JobId=job_id)
        
        services.extend([service['ServiceName'] for service in response['ServicesLastAccessed']])
        
        if 'Marker' in response:
            marker = response['Marker']
        else:
            break
    
    return services

def process_service_name(name):
    # AWS サービス
    if name.startswith("AWS "):
        main_name = name[4:]
        if main_name.startswith("IAM Identity Center"):
            return "AWS IAM Identity Center"
        if main_name.startswith("IoT") or main_name == "FreeRTOS":
            return "AWS IoT"
        if main_name.startswith("Elemental"):
            return "AWS Elemental"
        if main_name.startswith("Systems Manager"):
            return "AWS SSM"
        if main_name.startswith("Amplify"):
            return "AWS Amplify"
        if main_name.startswith("License Manager"):
            return "AWS License Manager"
        if main_name.startswith("Application Auto Scaling"):
            return "AWS Application Auto Scaling"
        if main_name.startswith("Migration Hub"):
            return "AWS Migration Hub"
        if main_name.startswith("Billing"):
            return "AWS Billing"
        parts = main_name.split()
        if len(parts) > 3:
            return "AWS " + " ".join(parts[:4])
        else:
            return name
    # Amazon サービス
    elif name.startswith("Amazon "):
        main_name = name[7:]
        if main_name.startswith("EC2") or main_name.startswith("Elastic"):
            if "Container" in main_name or "Kubernetes" in main_name:
                return name  # Keep original name for container and Kubernetes services
            return "Amazon EC2"
        if main_name.startswith("CloudWatch"):
            return "Amazon CloudWatch"
        if main_name.startswith("Route 53"):
            return "Amazon Route 53"
        if main_name.startswith("S3"):
            return "Amazon S3"
        parts = main_name.split()
        if len(parts) > 1:
            return "Amazon " + parts[0]
        else:
            return name
    else:
        return name

# 特別なケースの辞書
special_cases = {
    "AWS IAM Access Analyzer": "AWS IAM",
    "AWS Identity and Access Management": "AWS IAM",
    "AWS Identity and Access Management Roles Anywhere": "AWS IAM",
    "Amazon Elastic Container Registry": "Amazon ECR",
    "Amazon Elastic Container Service": "Amazon ECS",
    "Amazon Elastic Kubernetes Service": "Amazon EKS",
    "Amazon Elastic MapReduce": "Amazon EMR",
    "Amazon Elastic Block Store": "Amazon EBS",
    "Amazon Elastic File System": "Amazon EFS",
    "Amazon Managed Streaming for Apache Kafka": "Amazon MSK",
    "Amazon Managed Workflows for Apache Airflow": "Amazon MWAA",
    "Amazon Interactive Video Service": "Amazon IVS",
    "AWS Key Management Service": "AWS KMS",
    "AWS Security Token Service": "AWS STS",
    "AWS Resource Access Manager (RAM)": "AWS RAM",
    "AWS Private Certificate Authority": "AWS Private CA",
    "Application Discovery Arsenal": "AWS Application Discovery Service",
    "High-volume outbound communications": "Amazon Connect",
    "Tag Editor": "AWS Resource Groups",
    "Service Quotas": "AWS Service Quotas",
    "Amazon Elastic Inference": "Amazon Elastic Inference",
    "Amazon Elastic Transcoder": "Amazon Elastic Transcoder",
    "AWS Mainframe Modernization Application Testing provides tools and resources for automated functional equivalence testing for your migration projects.": "AWS Mainframe Modernization",
    "Apache Kafka APIs for Amazon MSK clusters": "Amazon MSK",
    "AWS Cost and Usage Report": "AWS Cost and Usage Report",
    "AWS Health APIs and Notifications": "AWS Health APIs and Notifications",
    "AWS Migration Hub Strategy Recommendations": "AWS Migration Hub",
    "AWS Partner central account management": "AWS Partner",
    "AWS Private CA Connector for Active Directory": "AWS Private CA",
    "AWS Private CA Connector for SCEP": "AWS Private CA",
    "AWS service providing managed private networks": "AWS Private Network",
    "AWS Support App in Slack": "AWS Support",
    "AWS Microservice Extractor for .NET": "AWS Microservice Extractor",
    "AWS App Mesh Preview": "AWS App Mesh",
    "AWS CodeDeploy secure host commands service": "AWS CodeDeploy",
    "Amazon Interactive Video Service Chat": "Amazon IVS",
    "Amazon Managed Blockchain Query": "Amazon Managed Blockchain",
    "AWS Migration Hub Refactor Spaces": "AWS Migration Hub",
    "Amazon WorkSpaces Thin Client": "Amazon WorkSpaces",
    "Amazon WorkSpaces Secure Browser": "Amazon WorkSpaces",
    "Amazon WorkMail Message Flow": "Amazon WorkMail",
    "Amazon Managed Service for Prometheus": "Amazon Managed Service for Prometheus",
    "Amazon Managed Streaming for Kafka Connect": "Amazon MSK",
    "AWS Mainframe Modernization Service": "AWS Mainframe Modernization",
    "Amazon Verified Permissions": "Amazon Verified Permissions",
    "AWS Application Cost Profiler Service": "AWS Application Cost Profiler",
    "AWS Billing And Cost Management Data Exports": "AWS Billing",
    "AWS Marketplace Management Portal": "AWS Marketplace",
    "Amazon Data Lifecycle Manager": "Amazon Data Lifecycle Manager",
    "Amazon Message Delivery Service": "Amazon Message Delivery Service",
    "Amazon Message Gateway Service": "Amazon Message Gateway Service",
    "AWS Network Manager Chat": "AWS Network Manager",
    "Amazon Simple Workflow Service": "Amazon Simple Workflow Service",
    "Amazon Managed Grafana": "Amazon Managed Grafana",
    "Amazon Security Lake": "Amazon Security Lake",
    "AWS Performance Insights": "Amazon RDS"
}

def update_dynamodb_table(services):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(SERVICES_TABLE_NAME)

    for service in services:
        if service in special_cases:
            abbreviated = special_cases[service]
        else:
            abbreviated = process_service_name(service)
        
        try:
            table.put_item(
                Item={
                    'service_name': service,
                    'abbreviation': abbreviated
                }
            )
        except ClientError as e:
            log_error(f"Error updating DynamoDB for service {service}", error=str(e))

def handler(event, context):
    try:
        log_info("Starting AWS services update process")
        aws_services = get_all_aws_services()
        log_info(f"Retrieved {len(aws_services)} AWS services")

        update_dynamodb_table(aws_services)
        log_info(f"DynamoDB table {SERVICES_TABLE_NAME} updated successfully")

        return {
            'statusCode': 200,
            'body': json.dumps(f'Successfully updated {len(aws_services)} AWS services')
        }

    except Exception as e:
        log_error("Error in Lambda handler", error=str(e))
        return {
            'statusCode': 500,
            'body': json.dumps('Error updating AWS services')
        }

if __name__ == "__main__":
    handler(None, None)