import json
from utils import client
from google.genai import types

def generate_learning_insights(conversation_json):
    """
    ユーザーの会話履歴を分析し、学習内容に関する発展的な情報やアドバイスを生成する
    """
    try:
        print("--- generate_learning_insights ---")
        
        # 会話履歴をJSON文字列に変換
        conversation_json_str = json.dumps(conversation_json, ensure_ascii=False, indent=2)

        system_instruction = (
            "あなたは教育の専門家です。"
            "ユーザーの学習記録（会話履歴）を分析し、"
            "以下の観点から発展的な情報やアドバイスを自然な文章形式で提供してください：\n"
            "1. 学習内容の関連分野や応用例\n"
            "2. より深い理解のための追加の学習トピック\n"
            "3. 実践的な演習や問題の提案\n"
            "4. 学習内容を日常生活や他の分野と結びつける方法"
        )

        prompt = (
            "ユーザーの学習記録（会話履歴）は以下の通りです(JSON形式):\n"
            f"```json\n{conversation_json_str}\n```\n\n"
            "この学習内容に関連して、以下の形式で発展的な情報を自然な文章形式で提供してください：\n\n"
            "【関連分野と応用例】\n"
            "学習内容に関連する分野や、実際の応用例について説明してください。\n\n"
            "【より深い理解のためのトピック】\n"
            "現在の学習内容をより深く理解するために、追加で学ぶと良いトピックを提案してください。\n\n"
            "【実践的な演習と問題】\n"
            "学習内容を定着させるための具体的な演習問題や実践方法を提案してください。\n\n"
            "【日常生活や他の分野との関連】\n"
            "学習内容が日常生活や他の分野でどのように活用できるか、具体的な例を挙げて説明してください。"
        )

        print("\nCalling Gemini API for learning insights...")
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction
            )
        )

        print("Raw Gemini response for learning insights:" + response.text)
        return response.text

    except Exception as e:
        print(f"Error in generate_learning_insights: {e}")
        import traceback
        traceback.print_exc()
        return "学習内容の分析中にエラーが発生しました。" 