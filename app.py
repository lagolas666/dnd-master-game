from flask import Flask, render_template, request, jsonify, session, Response
from models import DNDMaster, DiceRoller
import re
import uuid
import base64

app = Flask(__name__)
app.secret_key = "dnd_secret_key_2026"

master = DNDMaster()

# Хранилище сгенерированных изображений (временное)
image_storage = {}

# Ограничиваем размер истории (не более 20 сообщений)
MAX_HISTORY = 20

def get_history():
    if 'history' not in session:
        session['history'] = [{'role': 'master', 'text': master.get_start_message()}]
        session['waiting_for_roll'] = False
        session['pending_action'] = None
    if len(session['history']) > MAX_HISTORY:
        session['history'] = session['history'][-MAX_HISTORY:]
    return session['history']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/history', methods=['GET'])
def history():
    return jsonify({
        'history': get_history(),
        'waiting_for_roll': session.get('waiting_for_roll', False)
    })

@app.route('/image/<image_id>', methods=['GET'])
def get_image(image_id):
    """Возвращает изображение по ID"""
    if image_id in image_storage:
        # Возвращаем изображение как PNG
        image_data = base64.b64decode(image_storage[image_id])
        return Response(image_data, mimetype='image/png')
    return "Image not found", 404

@app.route('/summary', methods=['GET'])
def summary():
    history = get_history()
    recent_history = history[-15:]
    history_text = ""
    for msg in recent_history:
        role = "Мастер" if msg['role'] == 'master' else "Игрок"
        history_text += f"{role}: {msg['text'][:200]}\n"
    
    summary_text = master.summarize_history(history_text)
    history.append({'role': 'master', 'text': f"📜 **КРАТКИЙ ПЕРЕСКАЗ:**\n{summary_text}"})
    
    if len(history) > MAX_HISTORY:
        session['history'] = history[-MAX_HISTORY:]
    else:
        session['history'] = history
    
    return jsonify({'summary': summary_text, 'history': session['history']})

@app.route('/generate_image', methods=['GET'])
def generate_image():
    """Генерирует изображение на основе истории с улучшенным промптом"""
    history = get_history()
    
    # Берём последние 10 сообщений для лучшего контекста
    recent = history[-10:]
    history_text = ""
    for msg in recent:
        role = "Мастер" if msg['role'] == 'master' else "Игрок"
        history_text += f"{role}: {msg['text'][:300]}\n"
    
    # Генерируем детальный промпт через GPT
    image_prompt = master.generate_image_prompt(history_text)
    print(f"🎨 Итоговый промпт для изображения: {image_prompt}")
    
    # Генерируем изображение
    image_base64 = master.generate_image(image_prompt)
    
    if image_base64:
        image_id = str(uuid.uuid4())
        image_storage[image_id] = image_base64
        
        # Очищаем старые изображения
        if len(image_storage) > 10:
            oldest_keys = list(image_storage.keys())[:-10]
            for key in oldest_keys:
                del image_storage[key]
        
        # Сохраняем в историю с детальным промптом
        history.append({
            'role': 'master', 
            'text': f"🎨 **СГЕНЕРИРОВАННОЕ ИЗОБРАЖЕНИЕ**\n\n**Промпт:** {image_prompt[:200]}...", 
            'image_id': image_id
        })
        
        if len(history) > MAX_HISTORY:
            session['history'] = history[-MAX_HISTORY:]
        else:
            session['history'] = history
        
        print(f"✅ Изображение сохранено с ID: {image_id}")
            
        return jsonify({'image_id': image_id, 'prompt': image_prompt, 'history': session['history']})
    else:
        history.append({'role': 'master', 'text': "❌ **НЕ УДАЛОСЬ СГЕНЕРИРОВАТЬ ИЗОБРАЖЕНИЕ**\nПопробуйте позже или измените запрос."})
        session['history'] = history
        return jsonify({'error': 'Не удалось сгенерировать изображение'}, 500)

@app.route('/send', methods=['POST'])
def send():
    data = request.json
    user_message = data.get('message', '')
    dice_result = data.get('dice_result', None)
    
    if user_message == "!начать заново":
        session.clear()
        session['history'] = [{'role': 'master', 'text': master.get_start_message()}]
        session['waiting_for_roll'] = False
        session['pending_action'] = None
        return jsonify({'history': session['history'], 'waiting_for_roll': False})
    
    history = get_history()
    
    if dice_result is not None and session.get('pending_action'):
        action = session['pending_action']
        print(f"🎲 Обработка броска {dice_result} для действия: {action}")
        
        answer = master.ask(f"РЕЗУЛЬТАТ: {dice_result}\nИгрок пытался: {action}")
        
        history.append({'role': 'user', 'text': f"🎲 Результат броска: {dice_result}"})
        history.append({'role': 'master', 'text': answer})
        
        session['waiting_for_roll'] = master.needs_roll(answer)
        if not session['waiting_for_roll']:
            session['pending_action'] = None
        
        if len(history) > MAX_HISTORY:
            session['history'] = history[-MAX_HISTORY:]
        else:
            session['history'] = history
        
        return jsonify({
            'answer': answer,
            'history': session['history'],
            'waiting_for_roll': session['waiting_for_roll']
        })
    
    if user_message and user_message.strip():
        print(f"📝 Действие: {user_message}")
        answer = master.ask(user_message)
        
        history.append({'role': 'user', 'text': user_message})
        history.append({'role': 'master', 'text': answer})
        
        if master.needs_roll(answer):
            session['waiting_for_roll'] = True
            session['pending_action'] = user_message
            print(f"⏳ Требуется бросок для: {user_message}")
        else:
            session['waiting_for_roll'] = False
            session['pending_action'] = None
        
        if len(history) > MAX_HISTORY:
            session['history'] = history[-MAX_HISTORY:]
        else:
            session['history'] = history
        
        return jsonify({
            'answer': answer,
            'history': session['history'],
            'waiting_for_roll': session['waiting_for_roll']
        })
    
    return jsonify({'error': 'no_message'})

@app.route('/roll', methods=['POST'])
def roll():
    data = request.json
    dice_str = data.get('dice', 'd20')
    match = re.match(r'd(\d+)', dice_str)
    sides = int(match.group(1)) if match else 20
    total, description = DiceRoller.roll(sides)
    return jsonify({'total': total, 'description': description})

if __name__ == '__main__':
    app.run(debug=True)