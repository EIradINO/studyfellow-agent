import functions_framework
import flask
import os
from google.cloud import secretmanager
from supabase import create_client, Client
import traceback

PROJECT_ID = "studyfellow"
# 自動検出じゃ無いけどセキュリティ的に大丈夫なのか
SECRET_KEY_ID = "supabase-service-role-key" 
SECRET_URL_ID = "supabase-url"
secret_client = secretmanager.SecretManagerServiceClient()

def get_secret(secret_id):
    """Secret Manager から指定されたシークレットの最新バージョンを取得する"""

    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"

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
    """Supabaseからユーザーリストを取得しログに出力するv1.4"""
    print("Function triggered: get_supabase_users")
    try:
        supabase_url = get_secret(SECRET_URL_ID)
        supabase_key = get_secret(SECRET_KEY_ID)

        supabase: Client = create_client(supabase_url, supabase_key)
        print("Supabase client initialized.")
        try:
            response = supabase.table('user_documents').select("*", count='exact').execute()
            print(f"Supabase response received. Count: {response.count}")

        except Exception as db_err:
             print(f"Error querying Supabase 'user_documents': {db_err}")
             raise 

        user_count = response.count if response.count is not None else len(response.data)
        print(f"Successfully retrieved {user_count} user documents from Supabase.")
        print(f"User documents data sample: {response.data[:5]}")

        return f"Successfully retrieved {user_count} user documents.", 200

    except Exception as e:
        print(f"An error occurred in the function: {e}")
        traceback.print_exc() 
        return "An internal error occurred.", 500