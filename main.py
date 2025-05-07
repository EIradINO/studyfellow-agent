import functions_framework
import flask
from supabase import create_client, Client # Client は execute_daily_tasks で型ヒント用
import traceback
from datetime import timedelta, datetime, timezone
import json

# ローカルモジュールのインポート
from utils import get_secret # Gemini client は各サービスファイルがutilsから直接インポート・使用
from config import SECRET_URL_ID, SECRET_KEY_ID # Supabase接続情報
from comprehension_service import update_comprehension
from report_service import make_daily_report
from quiz_service import make_daily_quizzes
# models.Quiz は quiz_service.py で使われるため、main.pyでは直接不要

@functions_framework.http
def execute_daily_tasks(request: flask.Request):
    """その日の会話をjsonにまとめ、各サービス関数に渡す"""
    try:
        supabase_url = get_secret(SECRET_URL_ID)
        supabase_key = get_secret(SECRET_KEY_ID)
        supabase: Client = create_client(supabase_url, supabase_key)
        print("Supabase client initialized in main.")

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
            conv.append({
                "role": "user",
                "comment": post['comment'],
                "created_at": post['created_at']
            })
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

        # 各サービス関数呼び出し
        comprehension_update_suggestion = update_comprehension(conversation_json)
        daily_report_text = make_daily_report(conversation_json) # conversation_json を渡す
        daily_quizzes = make_daily_quizzes(conversation_json, daily_report_text) # report も渡す

        print("--- 理解度更新提案 JSON ---")
        print(json.dumps(comprehension_update_suggestion, ensure_ascii=False, indent=2))
        print("-------------------------")

        print("--- デイリーレポート ---")
        # daily_report_text が辞書の場合（エラー時など）も考慮
        if isinstance(daily_report_text, dict) and "summary" in daily_report_text:
            print(daily_report_text["summary"])
        else:
            print(daily_report_text) 
        print("--------------------")

        print("--- 問題json ---")
        if daily_quizzes: # daily_quizzes がNoneや空でないことを確認
            try:
                quizzes_as_dicts = [quiz.model_dump() for quiz in daily_quizzes] # Pydantic V2の場合
                print(json.dumps(quizzes_as_dicts, ensure_ascii=False, indent=2))
            except AttributeError: # Pydantic V1の場合など model_dump がない場合
                try:
                    quizzes_as_dicts = [quiz.dict() for quiz in daily_quizzes] # Pydantic V1の場合
                    print(json.dumps(quizzes_as_dicts, ensure_ascii=False, indent=2))
                except Exception as e_dict:
                    print(f"Failed to serialize quizzes to JSON using .dict(): {e_dict}")
                    print(f"Quizzes data: {daily_quizzes}")
            except Exception as e_model_dump:
                 print(f"Failed to serialize quizzes with model_dump: {e_model_dump}")
                 print(f"Quizzes data: {daily_quizzes}")
        else:
            print("生成された問題はありませんでした。")
        print("----------------")

        return "タスクを実行し、各種jsonをログ出力しました。", 200
    except Exception as e:
        print(f"An error occurred in execute_daily_tasks: {e}")
        traceback.print_exc()
        return "内部エラーが発生しました。", 500
