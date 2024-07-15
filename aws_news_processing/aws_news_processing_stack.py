import os
import subprocess
import sys
import shutil
from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as sfn_tasks,
    aws_events as events,
    aws_events_targets as targets,
    Duration,
    CfnOutput,
)
from constructs import Construct

class AwsNewsProcessingStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.create_resources()

    def create_resources(self):
        # DynamoDB table for storing service names
        services_table = dynamodb.Table(
            self, "AwsServiceTable",
            table_name="AwsNewsProcessingStack-AwsServiceTable",
            partition_key=dynamodb.Attribute(name="service_name", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )

        # IAM role for Lambda functions
        lambda_role = iam.Role(
            self, "LambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ]
        )

        # Add permissions to the Lambda role
        lambda_role.add_to_policy(iam.PolicyStatement(
            actions=["ssm:GetParameter"],
            resources=["*"]
        ))
        lambda_role.add_to_policy(iam.PolicyStatement(
            actions=["dynamodb:Scan", "dynamodb:PutItem"],
            resources=[services_table.table_arn]
        ))
        lambda_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "iam:GenerateServiceLastAccessedDetails",
                "iam:GetServiceLastAccessedDetails"
            ],
            resources=["*"]
        ))

        # Lambda function to update services
        update_services_lambda = _lambda.Function(
            self, "UpdateServicesLambdaFunction",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=_lambda.Code.from_asset(self.bundle_lambda_asset("lambda/update_services")),
            timeout=Duration.minutes(15),
            environment={
                "SERVICES_TABLE_NAME": services_table.table_name,
            },
            role=lambda_role,
        )

        # Lambda function to fetch news
        fetch_news_lambda = _lambda.Function(
            self, "FetchNewsLambdaFunction",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=_lambda.Code.from_asset(self.bundle_lambda_asset("lambda/fetch_news")),
            timeout=Duration.minutes(5),
            environment={
                "SERVICES_TABLE_NAME": services_table.table_name,
            },
            role=lambda_role,
        )

        # Lambda function for tagging and adding to Notion
        process_article_lambda = _lambda.Function(
            self, "ProcessArticleLambdaFunction",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=_lambda.Code.from_asset(self.bundle_lambda_asset("lambda/process_article")),
            timeout=Duration.minutes(5),
            environment={
                "SERVICES_TABLE_NAME": services_table.table_name,
                "NOTION_API_KEY_PARAM": "/update2notion/notion-api-key",
                "NOTION_DB_ID_PARAM": "/update2notion/notion-db-id",
                "OPENAI_API_KEY_PARAM": "/update2notion/openai-api-key",
            },
            role=lambda_role,
            memory_size=512,
        )

        # Step Functions IAM role
        step_functions_role = iam.Role(
            self, "StepFunctionsRole",
            assumed_by=iam.ServicePrincipal("states.amazonaws.com"),
        )

        # Grant Lambda invoke permissions to Step Functions
        update_services_lambda.grant_invoke(step_functions_role)
        fetch_news_lambda.grant_invoke(step_functions_role)
        process_article_lambda.grant_invoke(step_functions_role)

        # Step Functions definition
        update_services_task = sfn_tasks.LambdaInvoke(
            self, "UpdateServicesTask",
            lambda_function=update_services_lambda,
            output_path="$.Payload",
        )

        fetch_news_task = sfn_tasks.LambdaInvoke(
            self, "FetchNewsTask",
            lambda_function=fetch_news_lambda,
            output_path="$.Payload",
        )

        process_article_task = sfn_tasks.LambdaInvoke(
            self, "ProcessArticleTask",
            lambda_function=process_article_lambda,
            payload=sfn.TaskInput.from_json_path_at("$"),
            result_path="$.result",
        )

        map_state = sfn.Map(
            self, "ProcessArticlesMap",
            max_concurrency=5,
            items_path="$.articles",
            result_path="$.processedArticles",
        ).iterator(process_article_task)

        definition = update_services_task.next(fetch_news_task.next(map_state))

        state_machine = sfn.StateMachine(
            self, "AwsNewsProcessingStateMachine",
            definition=definition,
            timeout=Duration.minutes(30),
            role=step_functions_role,
        )

        # EventBridge ルールの作成
        rule = events.Rule(
            self, "ScheduleRule",
            schedule=events.Schedule.cron(
                minute="0",
                hour="21,3,9,15",  # UTC時間で6時間ごと（JST 06:00, 12:00, 18:00, 00:00に相当）
                month="*",
                week_day="*",
                year="*",
            ),
        )

        # StepFunctions ステートマシンをターゲットとして追加
        rule.add_target(targets.SfnStateMachine(state_machine))

        # Output the ARN of the state machine
        CfnOutput(self, "StateMachineArn", value=state_machine.state_machine_arn)

    def bundle_lambda_asset(self, asset_path):
        temp_dir = os.path.join(os.getcwd(), f'temp_lambda_build_{os.path.basename(asset_path)}')
        os.makedirs(temp_dir, exist_ok=True)
    
        try:
            for item in os.listdir(asset_path):
                s = os.path.join(asset_path, item)
                d = os.path.join(temp_dir, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
    
            if os.path.exists(os.path.join(temp_dir, 'requirements.txt')):
                subprocess.check_call([
                    sys.executable, '-m', 'pip', 'install', 
                    '-r', os.path.join(temp_dir, 'requirements.txt'), 
                    '-t', temp_dir, 
                    '--no-cache-dir',
                    '--upgrade'
                ])
    
            return temp_dir
    
        except Exception as e:
            print(f"Error in bundle_lambda_asset: {str(e)}")
            raise