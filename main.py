import functions_framework
import flask
import os
from google.cloud import secretmanager
from supabase import create_client, Client
import traceback
import google.generativeai as genai # 再度インポート
from datetime import date, timedelta, datetime, timezone # timezone を追加

PROJECT_ID = "studyfellow"
# 自動検出じゃ無いけどセキュリティ的に大丈夫なのか
SECRET_KEY_ID = "supabase-service-role-key" 
SECRET_URL_ID = "supabase-url"
GEMINI_API_KEY_SECRET_ID = "gemini-api-key" # 再度有効化

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
    """Supabaseからユーザーの理解度データを包括的に取得し、user_idを除いたJSONでログ出力"""
    try:
        # Supabaseクライアント初期化
        supabase_url = get_secret(SECRET_URL_ID)
        supabase_key = get_secret(SECRET_KEY_ID)
        supabase: Client = create_client(supabase_url, supabase_key)
        print("Supabase client initialized.")

        # user_comprehension全件取得
        comprehension_res = supabase.table('user_comprehension').select('*').execute()
        comprehensions = comprehension_res.data

        # user_comprehension_sub全件取得
        sub_res = supabase.table('user_comprehension_sub').select('*').execute()
        subs = sub_res.data

        # comprehension_idで紐付け
        comprehension_dict = {}
        for comp in comprehensions:
            comp_id = comp['id']
            comprehension_dict[comp_id] = {
                "subject": comp['subject'],
                "comprehension": comp['comprehension'],
                "explanation": comp['explanation'],
                "subs": []
            }

        for sub in subs:
            comp_id = sub['comprehension_id']
            if comp_id in comprehension_dict:
                comprehension_dict[comp_id]["subs"].append({
                    "field": sub['field'],
                    "comprehension": sub['comprehension'],
                    "explanation": sub['explanation']
                })
        result = list(comprehension_dict.values())
        import json
        print("--- User Comprehension Summary JSON ---")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("---------------------------------------")
        return "ユーザー理解度データをJSONでログ出力しました。", 200
    except Exception as e:
        print(f"An error occurred: {e}")
        traceback.print_exc()
        return "内部エラーが発生しました。", 500
