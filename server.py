import os
import ssl
import json
import random
import asyncio
import edge_tts
import whisper
from http.server import HTTPServer, SimpleHTTPRequestHandler

# SSL 인증서 처리
ssl._create_default_https_context = ssl._create_unverified_context

PORT = 8000
VOICE_NAME = "en-US-AriaNeural"

print("🎤 Whisper STT 모델을 로드 중입니다. 잠시만 기다려주세요...")
stt_model = whisper.load_model("tiny")
print("✅ Whisper STT 모델 로드 완료!")

# 사용자별 대화 세션 상태 저장소 (Multi-Turn Conversation Memory)
session_memory = {
    "step": 0,
    "drink": None,
    "size": None,
    "food": None
}

def get_next_ai_response(user_text: str) -> dict:
    """다단계(Multi-turn) 맥락을 기억하여 진짜 대화처럼 자연스럽게 응답 생성"""
    global session_memory
    lower = user_text.lower()
    step = session_memory["step"]

    # 1단계: 음료 주문 처리
    if step == 0 or any(k in lower for k in ["coffee", "americano", "latte", "tea", "water", "hot", "iced"]):
        if "hot" in lower:
            session_memory["drink"] = "hot coffee"
        elif "iced" in lower:
            session_memory["drink"] = "iced coffee"
        else:
            session_memory["drink"] = "coffee"
            
        session_memory["step"] = 1
        return {
            "ai_text": f"Sounds great! A {session_memory['drink']}. What size would you like: Small, Medium, or Large?",
            "ai_kr": f"좋습니다! {session_memory['drink']}로 준비해 드릴게요. 사이즈는 무엇으로 하시겠어요: 스몰, 미디엄, 라지?"
        }

    # 2단계: 사이즈 선택 처리
    elif step == 1 or any(k in lower for k in ["small", "medium", "large", "big", "regular"]):
        if "large" in lower or "big" in lower:
            session_memory["size"] = "Large"
        elif "small" in lower:
            session_memory["size"] = "Small"
        else:
            session_memory["size"] = "Medium"
            
        session_memory["step"] = 2
        drink = session_memory.get("drink", "coffee")
        return {
            "ai_text": f"Got it! One {session_memory['size']} {drink}. Would you like any bakery items with that, like a croissant or muffin?",
            "ai_kr": f"네, {session_memory['size']} 사이즈 {drink} 하나 확인했습니다. 크루아상이나 머핀 같은 베이커리 종류도 함께 주문하시겠어요?"
        }

    # 3단계: 사이드 디저트 주문 또는 거절 처리
    elif step == 2 or any(k in lower for k in ["croissant", "muffin", "cake", "no", "nothing", "just"]):
        if any(k in lower for k in ["no", "nothing", "just", "that's all", "enough"]):
            session_memory["food"] = "no bakery"
            food_msg = ""
        else:
            session_memory["food"] = "a delicious bakery item"
            food_msg = " and a fresh bakery item"

        session_memory["step"] = 3
        size = session_memory.get("size", "Medium")
        drink = session_memory.get("drink", "coffee")
        return {
            "ai_text": f"Perfect! That will be one {size} {drink}{food_msg}. Your total is $4.50. Will you be paying with cash or card?",
            "ai_kr": f"좋습니다! {size} {drink}{food_msg} 준비해 드릴게요. 총 금액은 4달러 50센트입니다. 현금으로 계산하시겠어요, 카드로 하시겠어요?"
        }

    # 4단계: 결제 및 마무리
    elif step == 3 or any(k in lower for k in ["card", "cash", "credit", "here"]):
        session_memory["step"] = 0  # 초기화
        return {
            "ai_text": "Thank you! Here is your order and receipt. Please enjoy your coffee and have a wonderful day!",
            "ai_kr": "감사합니다! 주문하신 음료와 영수증 여기 있습니다. 커피 맛있게 드시고 오늘 하루도 행복하세요!"
        }

    # 자유 안부 및 기타 대화 반응
    else:
        if any(k in lower for k in ["hi", "hello", "hey"]):
            return {
                "ai_text": "Hello there! Welcome! How can I help you today?",
                "ai_kr": "안녕하세요! 반갑습니다! 오늘 무엇을 도와드릴까요?"
            }
        elif any(k in lower for k in ["thank", "thanks"]):
            return {
                "ai_text": "You're very welcome! Let me know if you need anything else.",
                "ai_kr": "천만에요! 더 필요하신 게 있으면 언제든 말씀해 주세요."
            }
        else:
            return {
                "ai_text": f"I see! You said '{user_text}'. That sounds interesting! What would you like to do next?",
                "ai_kr": f"아 그렇군요! '{user_text}'라고 말씀하셨군요. 흥미롭네요! 다음엔 어떤 이야기를 나눠볼까요?"
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
                print(f"🎙 [Whisper 인식 성공]: '{transcribed_text}'")

                if not transcribed_text:
                    transcribed_text = "I want hot coffee"

                # 💡 맥락을 기억하는 다단계 대화 응답 생성
                reply_obj = get_next_ai_response(transcribed_text)
                print(f"🤖 [AI 다단계 대화 응답 (Step {session_memory['step']})]: {reply_obj['ai_text']}")

                # TTS 음성 생성
                asyncio.run(edge_tts.Communicate(reply_obj["reply_text"] if "reply_text" in reply_obj else reply_obj["ai_text"], VOICE_NAME).save("ai_reply.mp3"))

                response_data = {
                    "recognized": transcribed_text,
                    "ai_text": reply_obj["ai_text"],
                    "ai_kr": reply_obj["ai_kr"],
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
    print(f"🚀 다단계 실시간 AI 대화 서버가 http://localhost:{PORT} 에서 실행 중입니다.")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
