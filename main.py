import functions_framework
import flask
import os
from google.cloud import secretmanager
from supabase import create_client, Client
import traceback
import google.generativeai as genai # 再度インポート
from datetime import date, timedelta, datetime # datetime関連をインポート

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
    """(変更) 今日のSupabaseメッセージを取得し、Geminiで要約してログ出力""" # Docstring 変更
    print("Function triggered: get_supabase_users (Summarize today's messages with Gemini)") # ログ変更
    try:
        # 1. Supabase クライアント初期化
        supabase_url = get_secret(SECRET_URL_ID)
        supabase_key = get_secret(SECRET_KEY_ID)
        supabase: Client = create_client(supabase_url, supabase_key)
        print("Supabase client initialized.")

        # 2. 今日の日付範囲を取得
        today = date.today()
        tomorrow = today + timedelta(days=1)
        today_start_str = today.isoformat()
        tomorrow_start_str = tomorrow.isoformat()
        print(f"Querying messages created between {today_start_str} (inclusive) and {tomorrow_start_str} (exclusive)")

        # 3. Supabase で今日のメッセージ内容を取得
        messages_content = []
        try:
            response = supabase.table('messages') \
                             .select('content') \
                             .gte('created_at', today_start_str) \
                             .lt('created_at', tomorrow_start_str) \
                             .order('created_at') \
                             .execute()

            if response.data:
                messages_content = [msg['content'] for msg in response.data if msg.get('content')]
                print(f"Retrieved {len(messages_content)} messages from today.")
            else:
                print("No messages found for today.")
                return f"No messages found for today ({today_start_str}).", 200

        except Exception as db_err:
            print(f"Error querying Supabase 'messages': {db_err}")
            traceback.print_exc()
            raise

        # 4. メッセージ内容を結合
        combined_text = "\n\n---\n\n".join(messages_content)

        if not combined_text.strip():
             print("Combined message content is empty.")
             return "No content found in today's messages.", 200

        # 5. Gemini API で要約
        try:
            print("Configuring Gemini API...")
            api_key = get_secret(GEMINI_API_KEY_SECRET_ID)
            genai.configure(api_key=api_key)

            print("Generating summary with Gemini...")
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"以下の複数のメッセージ内容を理解し、全体を簡潔に要約してください:\n\n---\n{combined_text}\n---\n\n要約:"

            gemini_response = model.generate_content(prompt, stream=False)
            gemini_response.resolve() # エラーチェック

            if hasattr(gemini_response, 'text'):
                summary = gemini_response.text
                print("--- Gemini Summary ---")
                print(summary)
                print("----------------------")
                return f"Successfully summarized {len(messages_content)} messages from today. Summary logged.", 200
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