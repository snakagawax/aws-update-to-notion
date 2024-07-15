# AWS News Processing and Notion Integration

## 概要

このプロジェクトは、AWS の最新ニュースを自動的に取得し、処理して、Notion データベースに追加するシステムです。AWS CDK を使用してインフラストラクチャをデプロイし、AWS Lambda 関数と Step Functions を利用してワークフローを管理します。

## 主な機能

- AWS の最新ニュースフィードから過去 5 日間の記事を取得
- 記事のタイトルに基づいて関連する AWS サービスをタグ付け
- 記事の内容をスクレイピングし、日本語に翻訳
- 翻訳された内容の要約を生成
- 処理された記事を Notion データベースに追加

## セットアップ

1. リポジトリをクローンします：

   ```
   git clone[リポジトリ URL]
   cd[プロジェクトディレクトリ]
   ```

2. 仮想環境を作成し、アクティベートします：

   ```
   python -m venv .venv
   source .venv/bin/activate
   ```

3. 必要なパッケージをインストールします：

   ```
   pip install -r requirements.txt
   ```

4. AWS CDK をインストールします：

   ```
   npm install -g aws-cdk
   ```

5. CDK スタックをデプロイします：

   ```
   cdk deploy
   ```

6. パラメータストアに環境変数を設定
    - `/update2notion/notion-api-key`: Notion API キー
    - `/update2notion/notion-db-id: Notion データベース ID
    - `/update2notion/openai-api-key`: OpenAI API キー
   ```
   aws ssm put-parameter --name "/update2notion/notion-api-key" --value secret_hogehoge" --type SecureString
   aws ssm put-parameter --name "/update2notion/notion-db-id" --value "hogehoge" --type SecureString
   aws ssm put-parameter --name "/update2notion/openai-api-key" --value "sk-hogehoge" --type SecureString
   ```

## 使用方法

デプロイが完了すると、Step Functions のステートマシンが作成されます。このステートマシンを定期的に実行するように設定することで、最新の AWS ニュースを自動的に処理し、Notion データベースに追加できます。

手動で実行する場合は、AWS コンソールから Step Functions のステートマシンを開き、実行を開始します。

## 主要コンポーネント

1. `fetch_news` Lambda 関数: AWS のニュースフィードから最新の記事を取得します。
2. `process_article` Lambda 関数: 記事の内容をスクレイピングし、翻訳、要約、タグ付けを行い、Notion に追加します。
3. Step Functions: 全体のワークフローを管理し、複数の記事の並行処理を可能にします。
4. DynamoDB テーブル: AWS サービス名とその略称を管理します。
