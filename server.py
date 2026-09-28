import os
import ssl
import json
import asyncio
import edge_tts
import whisper
from http.server import HTTPServer, SimpleHTTPRequestHandler

ssl._create_default_https_context = ssl._create_unverified_context

PORT = 8000
VOICE_NAME = "en-US-AriaNeural"

print("🎤 Whisper STT 모델을 로드 중입니다. 잠시만 기다려주세요...")
stt_model = whisper.load_model("tiny")
print("✅ Whisper STT 모델 로드 완료!")

# 사용자 세션 메모리 (1단계: 왕초보 초단문 모드)
session_memory = {
    "level": 1,
    "step": 0
}

# 1단계 (왕초보 단문 회화): 3~4단어 이내 초간단 문장
LEVEL_1_STEPS = [
    {
        "step": 0,
        "ai_text": "Hi! What do you want?",
        "ai_kr": "안녕하세요! 무엇을 드릴까요?",
        "guide": "💡 'Coffee, please' (커피 주세요) 라고 쉽게 말해보세요!",
        "keywords": ["coffee", "water", "tea"]
    },
    {
        "step": 1,
        "ai_text": "Hot or iced?",
        "ai_kr": "따뜻하게 드릴까요, 차갑게 드릴까요?",
        "guide": "💡 'Hot, please' 또는 'Iced, please' 라고 말해보세요!",
        "keywords": ["hot", "iced", "ice"]
    },
    {
        "step": 2,
        "ai_text": "Small or Large?",
        "ai_kr": "스몰 또는 라지 사이즈?",
        "guide": "💡 'Large, please' 또는 'Small, please' 라고 말해보세요!",
        "keywords": ["large", "small", "medium"]
    },
    {
        "step": 3,
        "ai_text": "Here you go! Enjoy!",
        "ai_kr": "여기 있습니다! 맛있게 드세요!",
        "guide": "💡 'Thank you!' (감사합니다!) 라고 인사하고 마치세요!",
        "keywords": ["thank", "thanks", "bye"]
    }
]

def get_level1_response(user_text: str) -> dict:
    global session_memory
    lower = user_text.lower()
    current_step = session_memory["step"]

    # 다음 단계 진행
    next_step_idx = (current_step + 1) % len(LEVEL_1_STEPS)
    session_memory["step"] = next_step_idx
    
    step_data = LEVEL_1_STEPS[next_step_idx]
    
    return {
        "ai_text": step_data["ai_text"],
        "ai_kr": step_data["ai_kr"],
        "guide": step_data["guide"]
    }

class VoiceChatHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/api/stt":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)

            temp_audio = "temp_recording.webm"
            with open(temp_audio, "wb") as f:
                f.write(post_data)

            try:
                result = stt_model.transcribe(temp_audio, language="en")
                transcribed_text = result.get("text", "").strip()
                print(f"🎙 [Whisper 1단계 인식]: '{transcribed_text}'")

                if not transcribed_text:
                    transcribed_text = "Coffee, please"

                # 1단계 초단문 응답
                reply_obj = get_level1_response(transcribed_text)
                print(f"🤖 [AI 1단계 응답]: {reply_obj['ai_text']}")

                # 천천히 또박또박 음성 생성 (rate=-10% 천천히)
                asyncio.run(edge_tts.Communicate(reply_obj["ai_text"], VOICE_NAME, rate="-10%").save("ai_reply.mp3"))

                response_data = {
                    "recognized": transcribed_text,
                    "ai_text": reply_obj["ai_text"],
                    "ai_kr": reply_obj["ai_kr"],
                    "guide": reply_obj["guide"],
                    "audio_url": "/ai_reply.mp3"
                }

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode('utf-8'))

            except Exception as e:
                print(f"❌ STT 에러: {e}")
                self.send_response(500)
                self.end_headers()
            finally:
                if os.path.exists(temp_audio):
                    os.remove(temp_audio)
        else:
            self.send_error(404)

def run():
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, VoiceChatHandler)
    print(f"🚀 [1단계 왕초보 단문 모드] 서버가 http://localhost:{PORT} 에서 실행 중입니다.")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
