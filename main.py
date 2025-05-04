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
    current_project_id = os.environ.get("GCP_PROJECT")
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
    """(変更) 過去24時間のSupabaseメッセージ(JST基準)を取得し、Geminiで要約してログ出力""" # Docstring 変更
    print("Function triggered: get_supabase_users (Summarize last 24h messages in JST with Gemini)") # ログ変更
    try:
        # 1. Supabase クライアント初期化
        supabase_url = get_secret(SECRET_URL_ID)
        supabase_key = get_secret(SECRET_KEY_ID)
        supabase: Client = create_client(supabase_url, supabase_key)
        print("Supabase client initialized.")

        # 2. 現在時刻から過去24時間の範囲を取得 (JST)
        jst = timezone(timedelta(hours=9), 'JST') # 日本標準時 (UTC+9)
        now_jst = datetime.now(jst)
        twenty_four_hours_ago_jst = now_jst - timedelta(hours=24)
        start_time_str = twenty_four_hours_ago_jst.isoformat()
        end_time_str = now_jst.isoformat()
        print(f"Querying messages created between {start_time_str} (JST, inclusive) and {end_time_str} (JST, inclusive)")

        # 3. Supabase で過去24時間(JST基準)のメッセージ内容を取得
        messages_content = []
        try:
            response = supabase.table('messages') \
                             .select('content') \
                             .gte('created_at', start_time_str) \
                             .lte('created_at', end_time_str) \
                             .order('created_at') \
                             .execute()

            if response.data:
                messages_content = [msg['content'] for msg in response.data if msg.get('content')]
                print(f"Retrieved {len(messages_content)} messages from the last 24 hours (JST).")
            else:
                print("No messages found in the last 24 hours (JST).")
                return f"No messages found between {start_time_str} and {end_time_str} (JST).", 200

        except Exception as db_err:
            print(f"Error querying Supabase 'messages': {db_err}")
            traceback.print_exc()
            raise

        # 4. メッセージ内容を結合
        combined_text = "\n\n---\n\n".join(messages_content)

        if not combined_text.strip():
             print("Combined message content is empty.")
             return "No content found in the retrieved messages.", 200

        # 5. Gemini API で要約
        try:
            print("Configuring Gemini API...")
            api_key = get_secret(GEMINI_API_KEY_SECRET_ID)
            genai.configure(api_key=api_key)

            print("Generating summary with Gemini...")
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"以下の複数のメッセージ内容（過去24時間分、日本時間基準）を理解し、全体を簡潔に要約してください:\n\n---\n{combined_text}\n---\n\n要約:"

            gemini_response = model.generate_content(prompt, stream=False)
            gemini_response.resolve() # エラーチェック

            if hasattr(gemini_response, 'text'):
                summary = gemini_response.text
                print("--- Gemini Summary (JST Last 24h) ---")
                print(summary)
                print("-------------------------------------")
                return f"Successfully summarized {len(messages_content)} messages from the last 24 hours (JST). Summary logged.", 200
            else:
                print(f"Failed to generate summary. Feedback: {gemini_response.prompt_feedback}")
                return f"要約を生成できませんでした。理由: {gemini_response.prompt_feedback}", 500

        except Exception as gemini_err:
            print(f"Error during Gemini summarization: {gemini_err}")
            traceback.print_exc()
            return "Error during summarization process.", 500

    except Exception as e:
        print(f"An error occurred in the function: {e}")
        traceback.print_exc()
        return "An internal error occurred.", 500