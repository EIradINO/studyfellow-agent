import os
from google.cloud import secretmanager
from google import genai
import config
import traceback

secret_client = secretmanager.SecretManagerServiceClient()

def get_secret(secret_id):
    """Secret Manager から指定されたシークレットの最新バージョンを取得する"""
    current_project_id = os.environ.get("GCP_PROJECT", config.PROJECT_ID)
    if not current_project_id:
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

api_key = get_secret(config.GEMINI_API_KEY_SECRET_ID)
client = genai.Client(api_key=api_key) 