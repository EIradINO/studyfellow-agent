import functions_framework
import flask
import os
from google.cloud import secretmanager
from supabase import create_client, Client
import traceback
from datetime import date, timedelta, datetime # datetime関連をインポート

PROJECT_ID = "studyfellow"
# 自動検出じゃ無いけどセキュリティ的に大丈夫なのか
SECRET_KEY_ID = "supabase-service-role-key" 
SECRET_URL_ID = "supabase-url"
# GEMINI_API_KEY_SECRET_ID = "gemini-api-key" # 不要

secret_client = secretmanager.SecretManagerServiceClient()

def get_secret(secret_id):
    """Secret Manager から指定されたシークレットの最新バージョンを取得する"""
    # 環境変数 GCP_PROJECT を優先し、なければハードコードされた PROJECT_ID を使う
    current_project_id = os.environ.get("GCP_PROJECT", PROJECT_ID)
    if not current_project_id:
         # 環境変数もハードコード値もなければエラー
         print("ERROR: GCP_PROJECT cannot be determined.")
         raise ValueError("GCP_PROJECT cannot be determined.")

    name = f"projects/{current_project_id}/secrets/{secret_id}/versions/latest"

    try:
        response = secret_client.access_secret_version(request={"name": name})
        print(f"Successfully accessed secret: {secret_id}")
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Error accessing secret {secret_id}: {e}")
        traceback.print_exc()
        raise

@functions_framework.http
def get_supabase_users(request: flask.Request):
    """(変更) Supabase messagesテーブルから今日のレコード数をログ出力""" # Docstring 変更
    print("Function triggered: get_supabase_users (Querying today's messages)") # ログ変更
    try:
        # 1. Supabase クライアント初期化
        supabase_url = get_secret(SECRET_URL_ID)
        supabase_key = get_secret(SECRET_KEY_ID)
        supabase: Client = create_client(supabase_url, supabase_key)
        print("Supabase client initialized.")

        # 2. 今日の日付範囲を取得 (YYYY-MM-DD形式)
        today = date.today()
        tomorrow = today + timedelta(days=1)
        today_start_str = today.isoformat()
        tomorrow_start_str = tomorrow.isoformat()
        print(f"Querying messages created between {today_start_str} (inclusive) and {tomorrow_start_str} (exclusive)")

        # 3. Supabase で今日のメッセージ件数を取得
        try:
            response = supabase.table('messages') \
                             .select('id', count='exact') \
                             .gte('created_at', today_start_str) \
                             .lt('created_at', tomorrow_start_str) \
                             .execute()

            message_count = response.count
            print(f"Found {message_count} messages created today ({today_start_str}).")

            return f"Successfully queried messages. Count for today ({today_start_str}): {message_count}", 200

        except Exception as db_err:
            print(f"Error querying Supabase 'messages': {db_err}")
            traceback.print_exc() # エラー詳細を出力
            raise # DBエラーを再発生させる

    except Exception as e:
        print(f"An error occurred in the function: {e}")
        traceback.print_exc()
        return "An internal error occurred.", 500