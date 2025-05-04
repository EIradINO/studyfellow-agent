import functions_framework
import flask
import os
import traceback
from datetime import datetime, timedelta, timezone
import pytz # 日本時間のため
from google.cloud import secretmanager
from supabase import create_client, Client
# import google.generativeai as genai # Gemini API用  <--- これをコメントアウト

# --- 設定 ---
PROJECT_ID = "studyfellow" # GCPプロジェクトID (環境変数から取るのが望ましいが、一旦ハードコード)
SUPABASE_KEY_ID = "supabase-service-role-key" # Supabase Service Role Key のシークレット名
SUPABASE_URL_ID = "supabase-url"             # Supabase URL のシークレット名
GEMINI_API_KEY_ID = "gemini-api-key"         # Gemini API Key のシークレット名
# -------------

# クライアントの初期化 (グローバルスコープで一度だけ)
secret_client = secretmanager.SecretManagerServiceClient()
supabase_client = None # 関数内で初期化
genai_configured = False # Gemini API設定済みフラグ

def get_secret(secret_id):
    """Secret Manager からシークレットを取得v1.1"""
    # GCP_PROJECT 環境変数が設定されていない問題への対応
    project_id_to_use = os.environ.get("GCP_PROJECT", PROJECT_ID) # 環境変数を優先、なければハードコード値
    if not project_id_to_use:
         # 環境変数もハードコード値もない場合はエラー
         raise ValueError("GCP_PROJECT not found in environment variables or hardcoded setting.")

    name = f"projects/{project_id_to_use}/secrets/{secret_id}/versions/latest"
    try:
        response = secret_client.access_secret_version(request={"name": name})
        print(f"Successfully accessed secret: {secret_id}")
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Error accessing secret {secret_id} (Project: {project_id_to_use}): {e}")
        traceback.print_exc()
        raise

def initialize_supabase():
    """Supabase クライアントを初期化"""
    global supabase_client
    if supabase_client is None:
        try:
            supabase_url = get_secret(SUPABASE_URL_ID)
            supabase_key = get_secret(SUPABASE_KEY_ID)
            supabase_client = create_client(supabase_url, supabase_key)
            print("Supabase client initialized successfully.")
        except Exception as e:
            print(f"Failed to initialize Supabase client: {e}")
            raise # 初期化失敗は致命的なのでエラーを再発生

def configure_gemini():
    """Gemini APIを設定"""
    global genai_configured
    if not genai_configured:
        try:
            api_key = get_secret(GEMINI_API_KEY_ID)
            # genai.configure(api_key=api_key)
            genai_configured = True
            print("Gemini API configured successfully.")
        except Exception as e:
            print(f"Failed to configure Gemini API: {e}")
            raise # APIキー取得失敗は致命的

@functions_framework.http
def summarize_recent_messages(request: flask.Request):
    """
    過去24時間のメッセージを取得し、room_idごとに会話を要約してログに出力する
    """
    print("Function triggered: summarize_recent_messages")

    # --- ↓↓↓ 一時的にコメントアウト ↓↓↓ ---
    # try:
    #     # Supabase と Gemini を初期化 (未初期化の場合)
    #     initialize_supabase()
    #     configure_gemini()
    #
    #     # 1. 時間範囲の計算 (JSTで過去24時間)
    #     jst = pytz.timezone('Asia/Tokyo')
    #     now_jst = datetime.now(jst)
    #     start_time_jst = now_jst - timedelta(hours=24)
    #     # Supabaseはタイムゾーン付きのUTC (timestamptz) を期待するためUTCに変換
    #     start_time_utc = start_time_jst.astimezone(timezone.utc).isoformat()
    #     print(f"Fetching messages created after: {start_time_utc} (UTC)")
    #
    #     # 2. Supabaseからmessagesテーブルのデータを取得
    #     try:
    #         # created_at が start_time_utc より大きいものを取得
    #         # TODO: "messages" テーブルと "created_at", "room_id", "content"(要約対象) カラムが存在する前提
    #         response = supabase_client.table('messages')\
    #                                   .select("id, room_id, created_at, content")\
    #                                   .gte('created_at', start_time_utc)\
    #                                   .order('created_at', desc=False)\
    #                                   .execute()
    #         messages = response.data
    #         print(f"Successfully retrieved {len(messages)} messages from Supabase.")
    #
    #     except Exception as db_err:
    #         print(f"Error querying Supabase 'messages': {db_err}")
    #         traceback.print_exc()
    #         return "Error querying database.", 500
    #
    #     if not messages:
    #         print("No recent messages found in the last 24 hours.")
    #         return "No recent messages to summarize.", 200
    #
    #     # 3. room_id ごとにメッセージをグループ化
    #     messages_by_room = {}
    #     for msg in messages:
    #         room_id = msg.get('room_id')
    #         if room_id:
    #             if room_id not in messages_by_room:
    #                 messages_by_room[room_id] = []
    #             # 要約用にシンプルなテキスト形式にする (例: "YYYY-MM-DD HH:MM:SS: content")
    #             # created_at を JST に変換して表示
    #             created_at_utc = datetime.fromisoformat(msg['created_at'].replace('Z', '+00:00'))
    #             created_at_jst = created_at_utc.astimezone(jst)
    #             formatted_time = created_at_jst.strftime('%Y-%m-%d %H:%M:%S')
    #             messages_by_room[room_id].append(f"{formatted_time}: {msg.get('content', '')}")
    #
    #     print(f"Messages grouped into {len(messages_by_room)} rooms.")
    #
    #     # 4. 各 room_id の会話を Gemini で要約
    #     summaries = {}
    #     model = genai.GenerativeModel('gemini-1.5-flash') # モデル指定
    #
    #     for room_id, conversation_lines in messages_by_room.items():
    #         print(f"Summarizing conversation for room_id: {room_id} ({len(conversation_lines)} messages)")
    #         conversation_text = "\n".join(conversation_lines)
    #
    #         # プロンプトを作成
    #         prompt = f"""以下の会話の要点を簡潔にまとめてください。
    #
    # 会話履歴:
    # ---
    # {conversation_text}
    # ---
    #
    # 要約:"""
    #
    #         try:
    #             # Gemini API 呼び出し
    #             response = model.generate_content(prompt)
    #             summary = response.text
    #             summaries[room_id] = summary
    #             # ログに要約を出力
    #             print(f"--- Summary for room_id: {room_id} ---")
    #             print(summary)
    #             print("--------------------------------------")
    #
    #         except Exception as gen_err:
    #             print(f"Error generating summary for room_id {room_id}: {gen_err}")
    #             summaries[room_id] = "Error during summarization."
    #             traceback.print_exc() # エラー詳細もログに出力
    #
    #     # 5. 完了ログ
    #     print("Finished summarizing conversations.")
    #     # 必要であれば、要約結果をまとめて返すことも可能
    #     # return flask.jsonify(summaries), 200
    #     return f"Successfully summarized conversations for {len(summaries)} rooms.", 200
    #
    # except Exception as e:
    #     print(f"An unexpected error occurred in the function: {e}")
    #     traceback.print_exc()
    #     return "An internal server error occurred.", 500
    # --- ↑↑↑ ---------------------- ↑↑↑ ---

    # --- ↓↓↓ 単純なレスポンスを返すように変更 ↓↓↓ ---
    print("Skipping initialization and processing for debugging.")
    return "Function container started successfully (debug mode).", 200
    # --- ↑↑↑ --------------------------------- ↑↑↑ ---