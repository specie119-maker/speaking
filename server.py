import os
import ssl
import json
import random
import asyncio
import edge_tts
import whisper
from http.server import HTTPServer, SimpleHTTPRequestHandler

# SSL 인증서 문제 우회 (Mac Python 3.14 환경)
ssl._create_default_https_context = ssl._create_unverified_context

PORT = 8000
VOICE_NAME = "en-US-AriaNeural"

print("🎤 Whisper STT 모델을 로드 중입니다. 잠시만 기다려주세요...")
stt_model = whisper.load_model("tiny")
print("✅ Whisper STT 모델 로드 완료!")

CONVERSATIONS = [
    {
        "prompt": "Hello! Welcome to our coffee shop. What can I get started for you today?",
        "kr": "안녕하세요! 커피숍에 오신 것을 환영합니다. 무엇을 주문하시겠어요?",
        "sampleReplies": [
            {"keyword": "hot", "reply": "Hot coffee sounds wonderful! What size would you like?", "kr": "따뜻한 커피 좋죠! 어떤 사이즈로 드릴까요?"},
            {"keyword": "iced", "reply": "Ice coffee coming right up! What size for you?", "kr": "아이스 커피 바로 준비할게요! 사이즈는 무엇으로 드릴까요?"},
            {"keyword": "coffee", "reply": "Great choice! Would you like that iced or hot?", "kr": "좋은 선택입니다! 아이스로 드릴까요, 따뜻하게 드릴까요?"},
            {"keyword": "water", "reply": "Sure! I can get you a bottle of water right away.", "kr": "네! 바로 생수 한 병 준비해 드릴게요."},
            {"default": True, "reply": "Hot coffee sounds wonderful! What size would you like?", "kr": "따뜻한 커피 좋죠! 어떤 사이즈로 준비해 드릴까요?"}
        ]
    }
]

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
                print(f"🎙 [Whisper 인식 성공]: '{transcribed_text}'")

                if not transcribed_text:
                    transcribed_text = "I want hot coffee"

                lower = transcribed_text.lower()
                conv = CONVERSATIONS[0]
                reply_obj = next((r for r in conv["sampleReplies"] if r.get("keyword") and r["keyword"] in lower), None)
                if not reply_obj:
                    reply_obj = next(r for r in conv["sampleReplies"] if r.get("default"))

                asyncio.run(edge_tts.Communicate(reply_obj["reply"], VOICE_NAME).save("ai_reply.mp3"))

                response_data = {
                    "recognized": transcribed_text,
                    "ai_text": reply_obj["reply"],
                    "ai_kr": reply_obj["kr"],
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
    print(f"🚀 실시간 Whisper 음성 인식 웹 서버가 http://localhost:{PORT} 에서 실행 중입니다.")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
