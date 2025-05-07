import json
import traceback
from google.genai import types # `types` を直接インポート
from utils import client # client は utils で初期化されたものを使用

def make_daily_report(conversation_json):
    """会話内容を元に、Gemini APIを使用して詳細な学習レポートを作成"""
    try:
        print("--- make_daily_report ---")
        # conversation_jsonの表示は必要に応じてコメント解除
        # print(json.dumps(conversation_json, ensure_ascii=False, indent=2))

        conversation_text = json.dumps(conversation_json, ensure_ascii=False, indent=2)

        system_instruction = (
            "あなたは経験豊富な学習メンターです。"
            "提供された会話履歴を分析し、ユーザーが今日何を学び、どのような点に苦労し、"
            "どのような進捗があったかを具体的に指摘してください。"
            "そして、今後の学習に役立つ具体的なアドバイスを、励ますように親しみやすい言葉で提供してください。"
        )
        
        prompt_contents = (
            f"会話履歴:\n```json\n{conversation_text}\n```\n\n"
            "上記会話履歴に基づいて、本日の学習のまとめとアドバイスを作成してください。"
        )

        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt_contents,
            generation_config=types.GenerateContentConfig(
                system_instruction=system_instruction
                # response_mime_type はテキストなので不要
            )
        )
        print("make_daily_report response:" + response.text)
        return response.text # テキストレポートを返す

    except Exception as e:
        print(f"Error in make_daily_report: {e}")
        traceback.print_exc()
        return {
            "summary": "レポート生成中にエラーが発生しました。",
            "error_details": str(e),
            "source_conversations": conversation_json
        } 