import os
import requests
import random
import time
from dotenv import load_dotenv

load_dotenv()

class DiceRoller:
    @staticmethod
    def roll(sides=20, count=1):
        results = [random.randint(1, sides) for _ in range(count)]
        total = sum(results)
        if count == 1:
            description = f"🎲 Результат броска d{sides}: **{total}**"
        else:
            description = f"🎲 Бросок {count}d{sides}: {', '.join(map(str, results))} = **{total}**"
        return total, description

class DNDMaster:
    def __init__(self):
        self.api_key = os.getenv("YA_API_KEY")
        self.folder_id = os.getenv("FOLDER_ID")
        self.url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        self.image_url = "https://llm.api.cloud.yandex.net/foundationModels/v1/imageGenerationAsync"
        
        print(f"API Key загружен: {'ДА' if self.api_key else 'НЕТ'}")
        print(f"Folder ID загружен: {'ДА' if self.folder_id else 'НЕТ'}")
        
        self.system_prompt = """
Ты — Dungeon Master в игре Dungeons & Dragons.

ПРАВИЛА:
1. Ты НИКОГДА не бросаешь кубики.
2. Когда игрок хочет что-то сделать, ты решаешь, нужен ли бросок.
3. Если нужен бросок — ответь: "Нужен бросок d20 на [навык]"
4. Если игрок прислал число (например "РЕЗУЛЬТАТ: 15"), ты ОБЯЗАН описать что произошло на основе этого числа.

ПРАВИЛА УСПЕХА:
- 1-5: провал с последствиями
- 6-10: провал
- 11-15: успех
- 16-19: хороший успех
- 20: критический успех
"""
    
    def get_start_message(self):
        starts = [
            "🎲 Ты просыпаешься в таверне 'Кривой пень'. На столе меч, 10 золотых и письмо. Что делаешь?",
            "🌲 Ты в тёмном лесу. Слышен волчий вой. У тебя меч, 7 золотых и амулет. Что делаешь?",
            "⛪ Ты на пороге заброшенного храма. У тебя посох, 15 золотых и свиток. Что делаешь?",
            "⚓ Ты в портовой гостинице. На столе карта, 12 золотых и бутылка рома. Что делаешь?",
            "🏔️ Ты на вершине горы у древних врат. В рюкзаке верёвка, 8 золотых и талисман. Что делаешь?"
        ]
        return random.choice(starts)
    
    def needs_roll(self, text):
        keywords = ["нужен бросок", "брось", "кинь кубик", "d20"]
        lower = text.lower()
        return any(kw in lower for kw in keywords)
    
    def summarize_history(self, history_text):
        prompt = f"""Сделай краткий пересказ этой истории игры в D&D (3-5 предложений).

История:
{history_text[:2000]}

Пересказ:"""
        
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }
        
        body = {
            "modelUri": f"gpt://{self.folder_id}/yandexgpt-lite",
            "completionOptions": {"stream": False, "temperature": 0.7, "maxTokens": 200},
            "messages": [{"role": "user", "text": prompt}]
        }
        
        response = requests.post(self.url, headers=headers, json=body)
        
        if response.status_code == 200:
            return response.json()["result"]["alternatives"][0]["message"]["text"]
        return "❌ Не удалось создать пересказ"
    
    def generate_image_prompt(self, history_text):
        """Создаёт промпт для генерации изображения на основе истории"""
        lines = history_text.strip().split('\n')
        last_action = lines[-1] if lines else "герой в подземелье"
        
        templates = [
            f"фэнтези сцена: {last_action[:50]}, dark fantasy, магический свет, подземелье",
            f"D&D приключение: {last_action[:50]}, эпичное фэнтези, детализированная иллюстрация",
            f"герой в мире Dungeons & Dragons, {last_action[:50]}, стиль фэнтези-арт"
        ]
        
        return random.choice(templates)
    
    def generate_image(self, prompt_text):
        """Генерирует изображение через Yandex Art"""
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }
        
        full_prompt = f"{prompt_text}, фэнтези арт, dark fantasy, магическая атмосфера, детализировано, 4k"
        
        body = {
            "modelUri": f"art://{self.folder_id}/yandex-art/latest",
            "generationOptions": {
                "seed": random.randint(1, 999999),
                "aspectRatio": {"widthRatio": 1, "heightRatio": 1}
            },
            "messages": [
                {"weight": 1, "text": full_prompt}
            ]
        }
        
        try:
            response = requests.post(self.image_url, headers=headers, json=body)
            
            if response.status_code == 200:
                operation_id = response.json()["id"]
                print(f"🖼️ Операция генерации: {operation_id}")
                
                result_url = f"https://llm.api.cloud.yandex.net/operations/{operation_id}"
                for attempt in range(45):
                    time.sleep(1)
                    result_response = requests.get(result_url, headers=headers)
                    if result_response.status_code == 200:
                        result_data = result_response.json()
                        if "response" in result_data and "image" in result_data["response"]:
                            print("✅ Изображение сгенерировано!")
                            return result_data["response"]["image"]
                        elif "done" in result_data and result_data["done"]:
                            break
                return None
            else:
                print(f"❌ Ошибка: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Исключение: {e}")
            return None
    
    def ask(self, message):
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }
        
        body = {
            "modelUri": f"gpt://{self.folder_id}/yandexgpt-lite",
            "completionOptions": {"stream": False, "temperature": 0.8, "maxTokens": 250},
            "messages": [
                {"role": "system", "text": self.system_prompt},
                {"role": "user", "text": message}
            ]
        }
        
        response = requests.post(self.url, headers=headers, json=body)
        
        if response.status_code == 200:
            return response.json()["result"]["alternatives"][0]["message"]["text"]
        return f"❌ Ошибка: {response.status_code}"