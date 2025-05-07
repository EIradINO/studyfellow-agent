import json
import traceback
from google.genai import types # `types` を直接インポート
from utils import client # client は utils で初期化されたものを使用
from models import Quiz # Quiz モデルをインポート

def make_daily_quizzes(conversation_json, report):
    """会話内容とレポートを元に問題を数問json形式で出力"""
    try:
        print("--- make_daily_quizzes ---")
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents='会話履歴:\n' + json.dumps(conversation_json, ensure_ascii=False, indent=2) + '\n\n日報:\n' + str(report) + '\n\nこの会話と日報をもとに、ユーザーの学力向上に役立つ問題を数問作成してください。問題はquestionとanswerの両方を含み、JSONリスト形式で返してください。',
            generation_config=types.GenerateContentConfig(
                system_instruction='あなたは経験豊富な学習メンターです。学習者の理解度に合わせた効果的な問題を作成するのが得意です。',
                response_mime_type='application/json'
            )
        )

        # response.textからJSONを解析する
        try:
            json_data = json.loads(response.text)
            
            if not isinstance(json_data, list):
                if isinstance(json_data, dict) and "questions" in json_data:
                    json_data = json_data.get("questions", [])
                else:
                    print(f"Expected JSON array but got: {type(json_data)}")
                    return []
            
            quizzes = []
            for item in json_data:
                try:
                    if "question" in item and "answer" in item:
                        quiz = Quiz(question=item["question"], answer=item["answer"])
                        quizzes.append(quiz)
                    else:
                        print(f"Skipping quiz item missing required fields: {item}")
                except Exception as e:
                    print(f"Error converting item to Quiz: {e}, item: {item}")
            
            if not quizzes:
                print("No valid quizzes were found in the response")
            else:
                print(f"Successfully parsed {len(quizzes)} quizzes")
            
            return quizzes
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON from Gemini response: {e}")
            print(f"Raw text: {response.text}")
            return []
        except Exception as e:
            print(f"Unexpected error while processing quizzes: {e}")
            traceback.print_exc()
            return []
            
    except Exception as e:
        print(f"Error in make_daily_quizzes: {e}")
        traceback.print_exc()
        return [] 