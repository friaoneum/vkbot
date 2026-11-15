# voice.py - Отправка голосовых сообщений
import os
import subprocess
import requests
from vk_utils import vk, send_message
import shutil

# Находим путь к ffmpeg
FFMPEG_PATH = shutil.which('ffmpeg')
if not FFMPEG_PATH:
    # Если ffmpeg не найден в PATH, укажи путь вручную
    FFMPEG_PATH = r"D:\Programs\ffmpeg\bin\ffmpeg.exe"  # 👈 ЗАМЕНИ НА СВОЙ ПУТЬ!
    print(f"⚠️ FFmpeg не найден в PATH, использую: {FFMPEG_PATH}")
else:
    print(f"✅ FFmpeg найден: {FFMPEG_PATH}")

def convert_to_ogg(input_path):
    """Конвертирует MP3 в Ogg Opus"""
    output_path = input_path.rsplit('.', 1)[0] + '.ogg'
    
    if os.path.exists(output_path):
        print(f"✅ Файл уже сконвертирован: {output_path}")
        return output_path
    
    # 👇 Проверяем, существует ли входной файл
    if not os.path.exists(input_path):
        print(f"❌ Входной файл не найден: {input_path}")
        return None
    
    # 👇 Используем полный путь к ffmpeg
    cmd = [
        FFMPEG_PATH,  # 👈 полный путь
        '-i', input_path,
        '-c:a', 'libopus',
        '-ar', '16000',
        '-ac', '1',
        '-b:a', '48000',
        output_path
    ]
    
    print(f"🔄 Конвертация: {input_path} → {output_path}")
    print(f"🔍 Команда: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ Конвертация завершена")
        print(f"📝 stdout: {result.stdout}")
        print(f"📝 stderr: {result.stderr}")
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка конвертации: {e}")
        print(f"📝 stdout: {e.stdout}")
        print(f"📝 stderr: {e.stderr}")
        return None
    except Exception as e:
        print(f"❌ Неизвестная ошибка: {e}")
        return None

def send_audio_message(peer_id, audio_path):
    """Отправляет голосовое сообщение"""
    try:
        
        upload_url = vk.docs.getMessagesUploadServer(
            type="audio_message",
            peer_id=peer_id
        )['upload_url']
        
        with open(audio_path, "rb") as f:
            file_data = f.read()
            
        files = {'file': (os.path.basename(audio_path), file_data, 'multipart/form-data')}
        response = requests.post(upload_url, files=files).json()
        
        if 'file' not in response:
            return False
        
        result = vk.docs.save(file=response['file'])
        
        # 👇 ПРАВИЛЬНАЯ ОБРАБОТКА: для audio_message результат — словарь, не список
        if not result:
            return False
        
        # Проверяем, что это audio_message
        if 'audio_message' in result:
            audio = result['audio_message']
            attachment = f"audio_message{audio['owner_id']}_{audio['id']}_{audio.get('access_key', '')}"
        else:
            return False
        
        send_message(peer_id, "", attachment=attachment)
        return True
        
    except Exception as e:
        print(f"❌ [ОШИБКА] {e}")
        import traceback
        traceback.print_exc()
        return False
        
def get_audio_path(name):
    """Возвращает путь к файлу (сначала ищет .ogg, потом .mp3)"""
    ogg_path = os.path.join("audio", f"{name}.ogg")
    if os.path.exists(ogg_path):
        return ogg_path
    
    mp3_path = os.path.join("audio", f"{name}.mp3")
    if os.path.exists(mp3_path):
        return convert_to_ogg(mp3_path)
    
    return None

def get_available_audio_files():
    """Возвращает список доступных файлов (без расширения)"""
    audio_dir = "audio"
    if not os.path.exists(audio_dir):
        os.makedirs(audio_dir)
        print(f"📁 Создана папка audio")
        return []
    
    files = []
    for f in os.listdir(audio_dir):
        if f.endswith(".ogg") or f.endswith(".mp3"):
            files.append(f.rsplit('.', 1)[0])
    
    return sorted(set(files))