import boto3
import os

# DynamoDBの設定
SERVICES_TABLE_NAME = os.environ['SERVICES_TABLE_NAME']
dynamodb = boto3.resource('dynamodb')
services_table = dynamodb.Table(SERVICES_TABLE_NAME)

def add_service_to_dynamodb(service_name, abbreviation):
    services_table.put_item(
        Item={
            'service_name': service_name,
            'abbreviation': abbreviation
        }
    )

def initialize_dynamodb_services():
    initial_services = [
        ("Amazon Q", "Amazon Q"),
        ("AWS Neuron", "AWS Neuron"),
        ("AWS App Studio", "AWS App Studio"),
        ("AWS Identity and Access Management", "AWS IAM"),
        ("Amazon Managed Workflows for Apache Airflow", "Amazon MWAA"),
        ("Amazon Elastic Compute Cloud", "Amazon EC2"),
        ("Amazon Simple Storage Service", "Amazon S3"),
        ("Amazon Relational Database Service", "Amazon RDS"),
        ("Amazon ECS", "Amazon ECS"),
        ("Amazon ECR", "Amazon ECR"),
        ("Amazon EMR", "Amazon EMR"),
        ("Amazon Cognito", "Amazon Cognito"),
        ("AWS Backup", "AWS Backup"),
        ("AWS Systems Manager", "AWS Systems Manager"),
    ]
    
    for service_name, abbreviation in initial_services:
        add_service_to_dynamodb(service_name, abbreviation)
    
    print("Initialization of DynamoDB services completed.")

if __name__ == "__main__":
    initialize_dynamodb_services()