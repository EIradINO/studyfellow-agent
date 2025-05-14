import functions_framework
import flask
from supabase import create_client, Client # Client は execute_daily_tasks で型ヒント用
import traceback
from datetime import timedelta, datetime, timezone
import json

# ローカルモジュールのインポート
from utils import get_secret # Gemini client は各サービスファイルがutilsから直接インポート・使用
from config import SECRET_URL_ID, SECRET_KEY_ID # Supabase接続情報
from report_service import make_daily_report
from quiz_service import make_daily_quizzes
from learning_insight_service import generate_learning_insights

@functions_framework.http
def execute_daily_tasks(request: flask.Request):
    """その日の会話をjsonにまとめ、各サービス関数に渡す"""
    try:
        supabase_url = get_secret(SECRET_URL_ID)
        supabase_key = get_secret(SECRET_KEY_ID)
        supabase: Client = create_client(supabase_url, supabase_key)
        print("Supabase client initialized in main.")

        # --- 全ユーザーのIDを取得 ---
        users_res = supabase.table('users').select('user_id').execute()
        if not users_res.data:
            print("No users found.")
            return "No users found.", 200
        
        user_ids = [user['user_id'] for user in users_res.data]
        print(f"Found {len(user_ids)} users: {user_ids}")

        all_user_task_results = []

        for user_id in user_ids:
            print(f"--- Processing tasks for user_id: {user_id} ---")
            try:
                # --- 直近24時間の会話履歴の取得と再現 (ユーザーごと) ---
                jst = timezone(timedelta(hours=9), 'JST')
                now_jst = datetime.now(jst)
                twenty_four_hours_ago_jst = now_jst - timedelta(hours=24)
                start_time_str = twenty_four_hours_ago_jst.isoformat()
                end_time_str = now_jst.isoformat()
                print(f"直近24時間の取得範囲: {start_time_str} 〜 {end_time_str} (JST) for user {user_id}")

                # messages取得 (user_idでフィルタリング)
                # messagesテーブルに user_id カラムが存在すると仮定
                messages_res = supabase.table('messages') \
                    .select('*') \
                    .eq('user_id', user_id) \
                    .gte('created_at', start_time_str) \
                    .lte('created_at', end_time_str) \
                    .order('created_at') \
                    .execute()
                messages = messages_res.data

                # posts取得 (user_idでフィルタリング)
                # postsテーブルに user_id カラムが存在すると仮定
                posts_res = supabase.table('posts') \
                    .select('*') \
                    .eq('user_id', user_id) \
                    .gte('created_at', start_time_str) \
                    .lte('created_at', end_time_str) \
                    .order('created_at') \
                    .execute()
                posts = posts_res.data

                # post_messages_to_ai取得
                # まずユーザーの投稿IDリストを取得
                user_post_ids = [post['id'] for post in posts]
                post_messages_to_ai = []
                if user_post_ids:
                    post_ai_res = supabase.table('post_messages_to_ai') \
                        .select('*') \
                        .in_('post_id', user_post_ids) \
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
                    "user_id": user_id, # ユーザーIDをjsonに含める
                    "messages_by_room": messages_by_room,
                    "posts_conversations": posts_conversations
                }
                print(f"--- 直近24時間の会話再現JSON for user {user_id} ---")
                print(json.dumps(conversation_json, ensure_ascii=False, indent=2))
                print("----------------------------------")

                # --- 1. タスクフォルダの作成 ---
                current_task_folder_id = None
                try:
                    folder_title = f"{now_jst.strftime('%Y-%m-%d')} の学習記録"
                    folder_description = "本日の学習活動のまとめ"
                    
                    insert_folder_res = supabase.table("user_task_folders").insert({
                        "user_id": user_id,
                        "title": folder_title,
                        "description": folder_description
                    }).execute()
                    
                    if insert_folder_res.data:
                        current_task_folder_id = insert_folder_res.data[0]['id']
                        print(f"Created task folder {current_task_folder_id} for user {user_id}")
                    else:
                        print(f"Failed to create task folder for user {user_id}. Response: {insert_folder_res}")
                        # フォルダ作成失敗時はこのユーザーの以降の処理をスキップ
                        all_user_task_results.append({
                            "user_id": user_id, "status": "error", 
                            "error_details": "Failed to create task folder",
                            "stage": "create_task_folder"
                        })
                        continue 
                except Exception as e_folder:
                    print(f"Exception creating task folder for user {user_id}: {e_folder}")
                    traceback.print_exc()
                    all_user_task_results.append({
                        "user_id": user_id, "status": "error", 
                        "error_details": str(e_folder),
                        "stage": "create_task_folder"
                    })
                    continue

                # 各サービス関数呼び出し
                daily_report_text = make_daily_report(conversation_json)
                daily_quizzes = make_daily_quizzes(conversation_json, daily_report_text)
                insights = generate_learning_insights(conversation_json)

                # --- 2. デイリークイズの保存 (user_tasks) ---
                if daily_quizzes:
                    tasks_to_insert = []
                    for quiz in daily_quizzes:
                        tasks_to_insert.append({
                            "user_id": user_id,
                            "question": quiz.question,
                            "answer": quiz.answer,
                            "task_folder_id": current_task_folder_id,
                            "status": "pending"
                            # "scheduled_at": None # 必要に応じて設定
                        })
                    
                    if tasks_to_insert:
                        try:
                            insert_tasks_res = supabase.table("user_tasks").insert(tasks_to_insert).execute()
                            if insert_tasks_res.data:
                                print(f"Inserted {len(insert_tasks_res.data)} tasks for user {user_id} into folder {current_task_folder_id}")
                            else:
                                print(f"Failed to insert tasks for user {user_id}. Response: {insert_tasks_res}")
                                # タスク保存失敗を記録するが、レポート保存は試みる場合もある
                        except Exception as e_tasks:
                            print(f"Exception inserting tasks for user {user_id}: {e_tasks}")
                            traceback.print_exc()
                else:
                    print(f"No quizzes generated for user {user_id}.")

                # --- 3. 日次レポートの保存 (user_daily_report) ---
                # daily_report_text や insights がエラー時に辞書型やNoneになる可能性を考慮
                basic_report_str = daily_report_text
                if isinstance(daily_report_text, dict):
                    basic_report_str = daily_report_text.get("summary", "レポート生成エラー")
                elif not isinstance(daily_report_text, str):
                    basic_report_str = str(daily_report_text)

                advanced_report_str = insights
                if not isinstance(insights, str):
                    advanced_report_str = str(insights) # またはエラーを示す文字列

                try:
                    report_to_insert = {
                        "user_id": user_id,
                        "basic_report": basic_report_str,
                        "advanced_report": advanced_report_str,
                        "task_folder_id": current_task_folder_id 
                        # 前提: user_daily_report.task_folder_id は user_task_folders.id を参照
                    }
                    insert_report_res = supabase.table("user_daily_report").insert(report_to_insert).execute()
                    if insert_report_res.data:
                        print(f"Inserted daily report for user {user_id} into folder {current_task_folder_id}")
                    else:
                        print(f"Failed to insert daily report for user {user_id}. Response: {insert_report_res}")
                except Exception as e_report:
                    print(f"Exception inserting daily report for user {user_id}: {e_report}")
                    traceback.print_exc()
                
                print(f"--- デイリーレポート for user {user_id} ---")
                # daily_report_text が辞書の場合（エラー時など）も考慮
                if isinstance(daily_report_text, dict) and "summary" in daily_report_text:
                    print(daily_report_text["summary"])
                else:
                    print(daily_report_text) 
                print("--------------------")

                print(f"--- 発展的な学習アドバイス for user {user_id} ---")
                print(insights)
                print("--------------------")

                print(f"--- 問題json for user {user_id} ---")
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

                all_user_task_results.append({
                    "user_id": user_id,
                    "status": "success",
                    "report_summary": daily_report_text["summary"] if isinstance(daily_report_text, dict) and "summary" in daily_report_text else daily_report_text[:100] + "..." if isinstance(daily_report_text, str) else "N/A",
                    "num_quizzes": len(daily_quizzes) if daily_quizzes else 0,
                    "insights_preview": insights[:100] + "..." if isinstance(insights, str) else "N/A"
                })
            except Exception as e_user:
                print(f"Error processing tasks for user_id {user_id}: {e_user}")
                traceback.print_exc()
                all_user_task_results.append({
                    "user_id": user_id,
                    "status": "error",
                    "error_details": str(e_user)
                })
                continue # 次のユーザーの処理へ

        print("--- All user processing finished ---")
        print(json.dumps(all_user_task_results, ensure_ascii=False, indent=2))
        return f"Tasks executed for {len(user_ids)} users. See logs for details.", 200
    except Exception as e:
        print(f"An error occurred in execute_daily_tasks: {e}")
        traceback.print_exc()
        return "内部エラーが発生しました。", 500

# supabase処理と、instant_report削除