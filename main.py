import functions_framework
import flask
import os
from google.cloud import secretmanager
from supabase import create_client, Client
import traceback
import google.generativeai as genai # Geminiライブラリをインポート

PROJECT_ID = "studyfellow"
# 自動検出じゃ無いけどセキュリティ的に大丈夫なのか
SECRET_KEY_ID = "supabase-service-role-key" 
SECRET_URL_ID = "supabase-url"
GEMINI_API_KEY_SECRET_ID = "gemini-api-key" # Gemini API キーのシークレット名

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
    """(変更) 固定テキストをログ出力し、リクエストテーマで詩を生成して返す""" # Docstring 変更
    print("Function triggered: get_supabase_users (Combined Gemini Ops)") # ログメッセージ変更
    try:
        # 1. Gemini API キーを安全に取得・設定
        api_key = get_secret(GEMINI_API_KEY_SECRET_ID)
        genai.configure(api_key=api_key)
        print("Gemini API configured.")

        # 2. === 固定プロンプトでテキスト生成 & ログ出力 ===
        try:
            fixed_prompt = "Google Cloud Functionsの主な役割について、2-3文で簡単に説明してください。"
            print(f"Generating text for logging with fixed prompt: {fixed_prompt}")
            log_model = genai.GenerativeModel('gemini-1.5-flash') # ログ用
            log_response = log_model.generate_content(fixed_prompt, stream=False)
            log_response.resolve()
            if hasattr(log_response, 'text'):
                print("--- Generated Text for Log ---")
                print(log_response.text)
                print("------------------------------")
            else:
                print(f"Failed to generate text for log. Feedback: {log_response.prompt_feedback}")
        except Exception as log_err:
            print(f"Error during text generation for log: {log_err}")
            # ログ生成エラーは関数全体を停止させない

        # 3. === リクエストテーマで詩を生成 & レスポンスとして返す ===
        theme = request.args.get("theme", "Google Cloud と AI") # デフォルトテーマ
        print(f"Generating poem for response with theme: {theme}")

        poem_model = genai.GenerativeModel('gemini-1.5-flash') # 詩生成用
        poem_prompt = f"「{theme}」についての短い詩を作成してください。"
        poem_response = poem_model.generate_content(poem_prompt, stream=False)
        poem_response.resolve()

        # 4. 詩の結果をHTTPレスポンスとして返す
        if hasattr(poem_response, 'text'):
            generated_poem = poem_response.text
            print("Poem generated successfully for response.")
            return flask.Response(generated_poem, mimetype='text/plain; charset=utf-8')
        else:
            print(f"Failed to generate poem for response. Feedback: {poem_response.prompt_feedback}")
            return flask.Response(f"詩を生成できませんでした。理由: {poem_response.prompt_feedback}", status=500, mimetype='text/plain; charset=utf-8')

    except Exception as e:
        print(f"An error occurred in the function: {e}")
        traceback.print_exc()
        return flask.Response("処理中にエラーが発生しました。", status=500, mimetype='text/plain; charset=utf-8')