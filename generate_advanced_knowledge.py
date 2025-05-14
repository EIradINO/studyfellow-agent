import json
from utils import client # Geminiクライアントをインポート
from google.genai import types # 型定義をインポート
import traceback

def generate_advanced_knowledge(conversation_json):
    """
    ユーザーの会話履歴を分析し、学習内容をさらに深掘りするための
    関連知識、応用例、または新たな視点を提供する文章を生成する。
    """
    try:
        print("--- generate_advanced_knowledge ---")
        
        # 会話履歴をJSON文字列に変換
        conversation_json_str = json.dumps(conversation_json, ensure_ascii=False, indent=2)

        system_instruction = (
            "あなたは知識豊富な教育アシスタントです。"
            "ユーザーの学習記録（会話履歴）を深く分析し、"
            "その内容をさらに発展させ、より深い理解へと導くための情報を提供してください。"
            "例えば、関連する高度な概念、学術的な背景、異なる分野での応用例、"
            "あるいはユーザーがまだ気づいていないかもしれない新たな問いかけなどを提示してください。"
            "最終的なアウトプットは、ユーザーの知的好奇心を刺激し、さらなる探求を促すような、"
            "読み応えのある自然な文章形式でお願いします。"
        )

        prompt = (
            "ユーザーの学習記録（会話履歴）は以下のJSON形式の通りです:\n"
            f"```json\n{conversation_json_str}\n```\n\n"
            "この学習内容に基づいて、ユーザーの知的好奇心を刺激し、"
            "さらなる学習意欲を掻き立てるような発展的な知識や洞察を、"
            "具体的な説明や例を交えながら、読みやすい文章で提供してください。"
        )

        print("\nCalling Gemini API for advanced knowledge generation...")
        response = client.models.generate_content(
            model="gemini-1.5-flash", # または適切なモデル
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction
            )
        )

        generated_text = response.text
        
        return generated_text # 生成されたテキストを返す（ログ出力以外にも利用できるように）

    except Exception as e:
        print(f"Error in generate_advanced_knowledge: {e}")
        traceback.print_exc()
        # エラーが発生した場合は、ログには出力するが、main.py側で処理が止まらないようにNoneやエラーメッセージを返す
        return "発展的知識の生成中にエラーが発生しました。" 