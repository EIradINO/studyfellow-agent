import json
from supabase import create_client, Client
import traceback
from utils import get_secret, client # client は utils で初期化されたものを使用
import config
from google.genai import types

def update_comprehension(conversation_json):
    """
    現在の学力データと今日の会話履歴をGeminiに入力し、
    学力データの中で更新すべき箇所を示すJSONを生成する。
    """
    try:
        print("--- update_comprehension ---")
        # 1. 現在の学力データをSupabaseから取得・整形
        supabase_url = get_secret(config.SECRET_URL_ID)
        supabase_key = get_secret(config.SECRET_KEY_ID)
        supabase: Client = create_client(supabase_url, supabase_key)
        print("Supabase client initialized for current comprehension data.")

        comprehension_res = supabase.table('user_comprehension').select('*').execute()
        comprehensions = comprehension_res.data
        sub_res = supabase.table('user_comprehension_sub').select('*').execute()
        subs = sub_res.data

        current_comprehension_data_dict = {}
        for comp in comprehensions:
            comp_id = comp['id']
            current_comprehension_data_dict[comp_id] = {
                "subject": comp['subject'],
                "comprehension": comp['comprehension'],
                "explanation": comp['explanation'] if 'explanation' in comp else None,
                "fields": []
            }
        for sub in subs:
            comp_id = sub['comprehension_id']
            if comp_id in current_comprehension_data_dict:
                current_comprehension_data_dict[comp_id]["fields"].append({
                    "field": sub['field'],
                    "comprehension": sub['comprehension'],
                    "explanation": sub['explanation'] if 'explanation' in sub else None
                })
        current_comprehension_data_list = list(current_comprehension_data_dict.values())
        
        print("Current comprehension data fetched and processed:")
        print(json.dumps(current_comprehension_data_list, ensure_ascii=False, indent=2))

        # 2. Gemini API呼び出しのための準備
        current_comprehension_data_str = json.dumps(current_comprehension_data_list, ensure_ascii=False, indent=2)
        conversation_json_str = json.dumps(conversation_json, ensure_ascii=False, indent=2)

        system_instruction = (
            "あなたは学習データ分析のエキスパートです。"
            "ユーザーの現在の総合的な学力データと、その日の学習記録（会話履歴）を分析してください。"
            "そして、学力データの中で、今日の学習内容を反映して更新すべき箇所（理解度が向上した分野や、説明文を更新すべき分野）を特定し、"
            "指定されたJSON形式で提案してください。"
        )

        prompt = (
            "現在のユーザーの学力データは以下の通りです(JSON形式):\n"
            f"```json\n{current_comprehension_data_str}\n```\n\n"
            "本日のユーザーの学習記録（会話履歴）は以下の通りです(JSON形式):\n"
            f"```json\n{conversation_json_str}\n```\n\n"
            "これらの情報に基づいて、ユーザーの学力データ（特に各分野の'comprehension'値や'explanation'）の中で、"
            "本日の学習内容を反映して更新すべき箇所を特定してください。\n"
            "更新提案を以下のJSON形式で出力してください:\n"
            "{\n"
            '  "levelUpField": ["理解度が向上したか内容が更新された分野名1", "分野名2"],\n'
            '  "updateExplanation": {\n'
            '    "説明を更新すべき分野名1": "この分野の新しい説明文",\n'
            '    "説明を更新すべき分野名2": "この分野の新しい説明文"\n'
            "  }\n"
            "}\n"
            "もし該当する更新がない場合は、levelUpFieldに空のリスト[]を、updateExplanationに空のオブジェクト{}を返してください。"
        )

        print("\nCalling Gemini API for comprehension update suggestions...")
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config=types.GenerationConfig( 
                system_instruction=system_instruction, 
                response_mime_type="application/json"
            )
        )
        
        print("Raw Gemini response for comprehension update:" + response.text)

        # 3. Geminiからのレスポンスをパース
        try:
            update_suggestion_json = json.loads(response.text)
            print("Parsed update suggestion JSON from Gemini:")
            print(json.dumps(update_suggestion_json, ensure_ascii=False, indent=2))
            print("---------------------------")
            return update_suggestion_json
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON from Gemini response for comprehension update: {e}")
            print(f"Raw text was: {response.text}")
            return {"levelUpField": [], "updateExplanation": {}}

    except Exception as e:
        print(f"Error in update_comprehension: {e}")
        traceback.print_exc()
        return {"levelUpField": [], "updateExplanation": {}} 