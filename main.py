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
def make_daily_report(request: flask.Request):
    """Supabaseからユーザーの理解度データと、直近24時間の会話履歴を取得し、user_idを除いたJSONでログ出力"""
    try:
        from datetime import datetime, timedelta, timezone
        import json
        # Supabaseクライアント初期化
        supabase_url = get_secret(SECRET_URL_ID)
        supabase_key = get_secret(SECRET_KEY_ID)
        supabase: Client = create_client(supabase_url, supabase_key)
        print("Supabase client initialized.")

        # --- 理解度データの取得とログ出力 ---
        comprehension_res = supabase.table('user_comprehension').select('*').execute()
        comprehensions = comprehension_res.data
        sub_res = supabase.table('user_comprehension_sub').select('*').execute()
        subs = sub_res.data
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
        print("--- User Comprehension Summary JSON ---")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("---------------------------------------")

        # --- 直近24時間の会話履歴の取得と再現 ---
        jst = timezone(timedelta(hours=9), 'JST')
        now_jst = datetime.now(jst)
        twenty_four_hours_ago_jst = now_jst - timedelta(hours=24)
        start_time_str = twenty_four_hours_ago_jst.isoformat()
        end_time_str = now_jst.isoformat()

        # messages取得
        messages_res = supabase.table('messages') \
            .select('*') \
            .gte('created_at', start_time_str) \
            .lte('created_at', end_time_str) \
            .order('created_at') \
            .execute()
        messages = messages_res.data

        # posts取得
        posts_res = supabase.table('posts') \
            .select('*') \
            .gte('created_at', start_time_str) \
            .lte('created_at', end_time_str) \
            .order('created_at') \
            .execute()
        posts = posts_res.data

        # post_messages_to_ai取得
        post_ai_res = supabase.table('post_messages_to_ai') \
            .select('*') \
            .gte('created_at', start_time_str) \
            .lte('created_at', end_time_str) \
            .order('created_at') \
            .execute()
        post_messages_to_ai = post_ai_res.data

        # messages: room_idごとにまとめ、created_at順
        messages_by_room = {}
        for msg in messages:
            room_id = msg['room_id']
            if room_id not in messages_by_room:
                messages_by_room[room_id] = []
            messages_by_room[room_id].append({
                "role": msg['role'],
                "content": msg['content'],
                "created_at": msg['created_at']
            })
        # posts, post_messages_to_ai: post_idで紐付け、created_at順
        posts_dict = {post['id']: post for post in posts}
        post_ai_by_post = {}
        for ai_msg in post_messages_to_ai:
            post_id = ai_msg['post_id']
            if post_id not in post_ai_by_post:
                post_ai_by_post[post_id] = []
            post_ai_by_post[post_id].append({
                "role": ai_msg['role'],
                "content": ai_msg['content'],
                "created_at": ai_msg['created_at']
            })
        # postsごとにユーザーとAIの会話を再現
        posts_conversations = []
        for post in posts:
            conv = []
            # ユーザー投稿
            conv.append({
                "role": "user",
                "comment": post['comment'],
                "created_at": post['created_at']
            })
            # AI返答
            ai_msgs = post_ai_by_post.get(post['id'], [])
            conv.extend(sorted(ai_msgs, key=lambda x: x['created_at']))
            posts_conversations.append({
                "post_id": post['id'],
                "conversation": conv
            })
        # 全体json
        conversation_json = {
            "messages_by_room": messages_by_room,
            "posts_conversations": posts_conversations
        }
        print("--- 直近24時間の会話再現JSON ---")
        print(json.dumps(conversation_json, ensure_ascii=False, indent=2))
        print("----------------------------------")

        return "ユーザー理解度データと会話履歴をJSONでログ出力しました。", 200
    except Exception as e:
        print(f"An error occurred: {e}")
        traceback.print_exc()
        return "内部エラーが発生しました。", 500
