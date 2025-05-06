import functions_framework
import flask
import os
from google.cloud import secretmanager
from supabase import create_client, Client
import traceback
from google import genai
from google.genai import types
from datetime import date, timedelta, datetime, timezone # timezone を追加
import json
from pydantic import BaseModel

class Quiz(BaseModel):
  question: str
  answer: str

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

api_key = get_secret(GEMINI_API_KEY_SECRET_ID)
client = genai.Client(api_key=api_key)

def update_comprehension(conversation_json):
    """会話jsonに加えcomprehensionのjsonも作成し保持（今はprint）"""
    # ここでcomprehensionのjsonも作成
    comprehension_json = {"dummy_comprehension": True}  # 仮のデータ
    print("--- update_comprehension ---")
    print("conversation_json:")
    import json
    print(json.dumps(conversation_json, ensure_ascii=False, indent=2))
    print("comprehension_json:")
    print(json.dumps(comprehension_json, ensure_ascii=False, indent=2))
    print("---------------------------")
    # 必要ならreturn comprehension_json
    return comprehension_json

def make_daily_report(conversation_json):
    """会話内容を元に、Gemini APIを使用して詳細な学習レポートを作成"""
    try:
        print(json.dumps(conversation_json, ensure_ascii=False, indent=2))

        # conversation_jsonを文字列に変換
        conversation_text = json.dumps(conversation_json, ensure_ascii=False, indent=2)

        system_instruction = (
            "あなたは経験豊富な学習メンターです。"
            "提供された会話履歴を分析し、ユーザーが今日何を学び、どのような点に苦労し、"
            "どのような進捗があったかを具体的に指摘してください。"
            "そして、今後の学習に役立つ具体的なアドバイスを、励ますように親しみやすい言葉で提供してください。"
        )
        
        prompt_contents = (
            f"会話履歴:\n```json\n{conversation_text}\n```\n\n"
        )

        response = client.models.generate_content(
            model="gemini-1.5-flash", # モデル名を gemini-1.5-flash に変更
            config=types.GenerateContentConfig(
                system_instruction=system_instruction
            ),
            contents=prompt_contents
        )
        print("response:" + response.text)
        return response.text

    except Exception as e:
        print(f"Error in make_daily_report: {e}")
        traceback.print_exc()
        return {
            "summary": "レポート生成中にエラーが発生しました。",
            "error_details": str(e),
            "source_conversations": conversation_json
        }

def make_daily_quizzes(conversation_json, report):
    """会話内容とレポートを元に問題を数問json形式で出力（今はprint）"""
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        config=types.GenerateContentConfig(
            system_instruction='あなたは経験豊富な学習メンターです。与えられた会話履歴と日報を元にユーザーの学力を上げるのに効果的と思われる問題を数問作成してください',
        ),
        contents='会話履歴:\n' + json.dumps(conversation_json, ensure_ascii=False, indent=2) + '\n\n日報:\n' + report,
        config={
            'response_mime_type': 'application/json',
            'response_schema': list[Quiz],
        },
    )

# Use the response as a JSON string.
    print(response.text)

    # Use instantiated objects.
    my_quizzes: list[Quiz] = response.parsed
    return my_quizzes
@functions_framework.http
def execute_daily_tasks(request: flask.Request):
    """その日の会話をjsonにまとめ、update_comprehension, make_daily_report, make_daily_quizzesに渡す"""
    try:
        supabase_url = get_secret(SECRET_URL_ID)
        supabase_key = get_secret(SECRET_KEY_ID)
        supabase: Client = create_client(supabase_url, supabase_key)
        print("Supabase client initialized.")

        # --- 直近24時間の会話履歴の取得と再現 ---
        jst = timezone(timedelta(hours=9), 'JST')
        now_jst = datetime.now(jst)
        twenty_four_hours_ago_jst = now_jst - timedelta(hours=24)
        start_time_str = twenty_four_hours_ago_jst.isoformat()
        end_time_str = now_jst.isoformat()
        print(f"直近24時間の取得範囲: {start_time_str} 〜 {end_time_str} (JST)")

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

        # ここから三つの関数に渡す
        comprehension_json = update_comprehension(conversation_json)
        report = make_daily_report(conversation_json)
        quizzes = make_daily_quizzes(conversation_json, report)
        print("--- 問題json ---")
        print(json.dumps(quizzes, ensure_ascii=False, indent=2))
        print("----------------")

        return "タスクを実行し、各種jsonをログ出力しました。", 200
    except Exception as e:
        print(f"An error occurred: {e}")
        traceback.print_exc()
        return "内部エラーが発生しました。", 500
