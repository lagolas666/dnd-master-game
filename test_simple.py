import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("YA_API_KEY")
folder_id = os.getenv("FOLDER_ID")

print(f"API Key: {api_key[:20] if api_key else 'НЕТ'}...")
print(f"Folder ID: {folder_id if folder_id else 'НЕТ'}")

# ДЛЯ ТЕСТА исправьте на свой folder_id вручную если надо:
# folder_id = "b1gqvsc3mcnebhpq7fgl"  # раскомментируйте и вставьте свой

if not api_key or not folder_id:
    print("❌ Ключи не найдены в .env")
    exit()

url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

headers = {
    "Authorization": f"Api-Key {api_key}",
    "Content-Type": "application/json"
}

body = {
    "modelUri": f"gpt://{folder_id}/yandexgpt-lite",
    "completionOptions": {
        "stream": False,
        "temperature": 0.7,
        "maxTokens": 50
    },
    "messages": [
        {"role": "user", "text": "Привет! Скажи 'OK'"}
    ]
}

print("Отправляю запрос...")
response = requests.post(url, headers=headers, json=body)
print(f"Статус: {response.status_code}")
print(f"Ответ: {response.text[:300]}")