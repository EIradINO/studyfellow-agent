import functions_framework
import flask
import os
from google.cloud import secretmanager
from supabase import create_client, Client
import traceback # エラー出力用にインポート

# --- 設定 ---
PROJECT_ID = "studyfellow" # Cloud Functionsが自動で設定
SECRET_KEY_ID = "supabase-service-role-key" # Service Role Key のシークレット名
SECRET_URL_ID = "supabase-url"             # Supabase URL のシークレット名
# -------------

# Secret Manager クライアントの初期化 (関数の外で一度だけ)
secret_client = secretmanager.SecretManagerServiceClient()

def get_secret(secret_id):
    """Secret Manager から指定されたシークレットの最新バージョンを取得する"""
    # 元のコード: グローバル変数 PROJECT_ID を使用
    if not PROJECT_ID:
       raise ValueError("GCP_PROJECT environment variable not set.")

    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest" # 元のコード

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
        # 1. Supabase URL と Service Role Key を安全に取得
        supabase_url = get_secret(SECRET_URL_ID)
        supabase_key = get_secret(SECRET_KEY_ID)

        # 2. Supabase クライアント初期化
        supabase: Client = create_client(supabase_url, supabase_key)
        print("Supabase client initialized.")

        # 3. users テーブルからデータを取得 (auth.users)
        # Service Role Keyなら auth スキーマにもアクセス可能
        # Supabase の Python クライアントでは、auth.users テーブルへの直接アクセスは
        # 推奨されていないか、バージョンによって挙動が変わる可能性があります。
        # `auth` スキーマを明示的に指定するか、RPCを使うのがより確実です。
        try:
            # 方法A: スキーマを明示的に指定
            # response = supabase.schema('auth').table('users').select("id, email, created_at", count='exact').execute()

            # 方法B: RPC (Remote Procedure Call) を使う (事前にSupabase側で関数定義が必要な場合もある)
            # 例: Supabase SQL Editor で `create function get_all_users() returns table(...) ...` のように関数を作成
            # response = supabase.rpc('get_all_users', {}).execute()

            # 一旦、デフォルトの検索パスに 'auth' が含まれることを期待して試す
            # response = supabase.table('users', schema='auth').select("id, email, created_at", count='exact').execute()
            # 方法Aを適用
            # response = supabase.schema('auth').table('users').select("id, email, created_at", count='exact').execute()
            # print(f"Supabase response received. Count: {response.count}")

            # user_documents テーブルから全カラムを取得
            response = supabase.table('user_documents').select("*", count='exact').execute()
            print(f"Supabase response received. Count: {response.count}")

        except Exception as db_err:
             # print(f"Error querying Supabase 'auth.users': {db_err}")
             # print("Make sure the 'auth' schema is accessible or try using RPC.")
             print(f"Error querying Supabase 'user_documents': {db_err}")
             raise # DBエラーを再発生させる

        user_count = response.count if response.count is not None else len(response.data)
        # print(f"Successfully retrieved {user_count} users from Supabase.")
        print(f"Successfully retrieved {user_count} user documents from Supabase.")
        # print(f"Users data sample: {response.data[:5]}") # データサンプルをログ出力（個人情報注意）
        print(f"User documents data sample: {response.data[:5]}") # データサンプルをログ出力

        # return f"Successfully retrieved {user_count} users.", 200
        return f"Successfully retrieved {user_count} user documents.", 200

    except Exception as e:
        print(f"An error occurred in the function: {e}")
        traceback.print_exc() # ここでもスタックトレースを出力
        return "An internal error occurred.", 500