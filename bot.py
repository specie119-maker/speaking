import os
import json
import logging
import random
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import edge_tts
import whisper

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# 환경 변수 로드
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
NOTIFY_HOUR = int(os.getenv("NOTIFY_HOUR", 21))
NOTIFY_MINUTE = int(os.getenv("NOTIFY_MINUTE", 0))
VOICE_NAME = os.getenv("VOICE_NAME", "en-US-AvaNeural")

SUBSCRIBERS_FILE = "subscribers.json"
EXPRESSIONS_FILE = "expressions.json"

# 로깅 설정
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Whisper STT 모델 (Lazy Loading)
whisper_model = None

def get_whisper_model():
    global whisper_model
    if whisper_model is None:
        logger.info("🎤 Whisper STT 모델(base)을 로드 중입니다...")
        whisper_model = whisper.load_model("base")
    return whisper_model

def load_subscribers():
    if os.path.exists(SUBSCRIBERS_FILE):
        try:
            with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            logger.error(f"구독자 파일 로드 실패: {e}")
    return set()

def save_subscribers(subscribers):
    with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(subscribers), f, ensure_ascii=False, indent=2)

def load_expressions():
    if os.path.exists(EXPRESSIONS_FILE):
        try:
            with open(EXPRESSIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"회화 문장 파일 로드 실패: {e}")
    return []

# 동적 문장 생성기 (수동 업데이트 필요 없이 자동으로 주제별 생성)
TOPICS = [
    ("카페/식당 주문", [
        ("Can I get an iced Americano with an extra shot?", "아이스 아메리카노에 샷 추가해서 한 잔 주시겠어요?", "샷 추가를 요청할 때 'with an extra shot'이라고 합니다."),
        ("Do you have any recommendations for dessert?", "디저트 추천해 주실 만한 것이 있나요?", "메뉴 추천을 물어볼 때 'Do you have recommendations?'라고 표현합니다."),
        ("Could we get the bill, please?", "계산서 좀 가져다주시겠어요?", "식사 후 계산서를 요청할 때 쓰는 정중한 표현입니다.")
    ]),
    ("여행/길 찾기", [
        ("Excuse me, how can I get to the city center from here?", "실례합니다, 여기서 시내 중심가까지 어떻게 가나요?", "길을 물어볼 때 가장 대표적인 구문입니다."),
        ("Could you take a photo of us, please?", "저희 사진 한 장만 찍어주시겠어요?", "여행지에서 사진 촬영 부탁할 때 무조건 쓰이는 문장입니다."),
        ("Is there a subway station nearby?", "근처에 지하철역이 있나요?", "'nearby'는 근처에라는 의미로 유용하게 쓰입니다.")
    ]),
    ("일상 대화/안부", [
        ("How was your day? Everything going well?", "오늘 하루 어땠어요? 잘 진행되고 있나요?", "친구나 동료에게 부드럽게 안부를 물어보는 문장입니다."),
        ("I'm planning to relax and watch a movie tonight.", "오늘 밤에는 편하게 쉬면서 영화를 볼 계획이에요.", "주말이나 저녁 계획을 말할 때 자연스럽습니다."),
        ("That sounds like a wonderful idea!", "정말 멋진 생각인 것 같네요!", "상대방의 아이디어에 호응할 때 사용해 보세요.")
    ])
]

def get_random_or_generated_expression():
    expressions = load_expressions()
    # 기존 데이터베이스 또는 동적 템플릿 조합
    if expressions and random.random() < 0.6:
        return random.choice(expressions)
    
    category, items = random.choice(TOPICS)
    en, kr, tip = random.choice(items)
    return {
        "english": en,
        "korean": kr,
        "tip": f"[{category}] {tip}"
    }

async def generate_voice_file(text: str, filename: str = "voice.mp3") -> str:
    """Edge-TTS를 이용하여 고품질 미국식 원어민 음성 파일 생성"""
    communicate = edge_tts.Communicate(text, VOICE_NAME)
    await communicate.save(filename)
    return filename

async def send_daily_prompt(chat_id: int, app: Application):
    """지정된 사용자에게 텍스트와 음성(TTS) 메시지 전송"""
    item = get_random_or_generated_expression()
    
    text_message = (
        f"🎧 **[오늘의 1분 영어 회화 배달]**\n\n"
        f"🗣 **English:**\n{item['english']}\n\n"
        f"🇰🇷 **한국어:**\n{item['korean']}\n\n"
        f"💡 **학습 팁:** {item.get('tip', '')}\n\n"
        f"🎙 **[음성 대화 해보기]**\n"
        f"아래 음성을 듣고, **텔레그램 음성 메시지 버튼(🎤)**을 눌러 직접 영어로 답장해 보세요! 제가 발음을 듣고 답장을 보내드릴게요!"
    )

    voice_path = f"voice_{chat_id}.mp3"
    try:
        await generate_voice_file(item['english'], voice_path)
        await app.bot.send_message(chat_id=chat_id, text=text_message, parse_mode="Markdown")
        
        with open(voice_path, "rb") as voice_file:
            await app.bot.send_voice(chat_id=chat_id, voice=voice_file, caption="🎙 원어민 발음 듣기 (듣고 음성으로 답장해 보세요!)")
            
    except Exception as e:
        logger.error(f"메시지/음성 전송 중 오류 (Chat ID: {chat_id}): {e}")
    finally:
        if os.path.exists(voice_path):
            os.remove(voice_path)

# 양방향 음성 주고받기 핸들러 (사용자가 보낸 음성 녹음 처리)
async def handle_user_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_voice = update.message.voice
    
    await update.message.reply_text("🎧 보내주신 음성을 듣고 인식하는 중입니다...")
    
    input_voice_file = f"user_voice_{chat_id}_{update.message.message_id}.ogg"
    reply_voice_file = f"reply_voice_{chat_id}_{update.message.message_id}.mp3"
    
    try:
        # 1. 사용자의 텔레그램 음성 파일 다운로드
        file = await context.bot.get_file(user_voice.file_id)
        await file.download_to_drive(input_voice_file)
        
        # 2. Whisper STT로 발음/음성 텍스트 변환
        model = get_whisper_model()
        transcription = model.transcribe(input_voice_file, language="en")
        recognized_text = transcription.get("text", "").strip()
        
        if not recognized_text:
            await update.message.reply_text("😅 음성이 명확히 들리지 않았어요. 다시 한번 영어로 크게 말씀해 주시겠어요?")
            return

        # 3. AI 피드백 및 답변 생성
        reply_text_en = f"Great job speaking! I heard you say: '{recognized_text}'. Keep up the wonderful practice!"
        reply_text_kr = f"📝 **[내가 말한 내용 인식 결과]**\n\"`{recognized_text}`\"\n\n👍 발음이 아주 좋으십니다! 매일 이렇게 영어로 한 문장씩 말해봐요."

        await update.message.reply_text(reply_text_kr, parse_mode="Markdown")

        # 4. AI 음성 답변(TTS) 생성 및 답장 전송
        await generate_voice_file(reply_text_en, reply_voice_file)
        with open(reply_voice_file, "rb") as voice_reply:
            await app.bot.send_voice(chat_id=chat_id, voice=voice_reply, caption="🎙 AI 회화 튜터의 음성 답장")

    except Exception as e:
        logger.error(f"음성 처리 오류: {e}")
        await update.message.reply_text("오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")
    finally:
        if os.path.exists(input_voice_file):
            os.remove(input_voice_file)
        if os.path.exists(reply_voice_file):
            os.remove(reply_voice_file)

# 명령어 핸들러: /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers = load_subscribers()
    
    if chat_id not in subscribers:
        subscribers.add(chat_id)
        save_subscribers(subscribers)
        
    welcome_text = (
        f"🎉 **양방향 영어 회화 음성 튜터 봇에 오신 것을 환영합니다!**\n\n"
        f"• 매일 저녁 {NOTIFY_HOUR:02d}:{NOTIFY_MINUTE:02d}분에 오늘의 회화와 **원어민 음성**을 자동으로 보내드립니다.\n"
        f"• **직접 영어로 말하고 싶다면?** 텔레그램 마이크 버튼(🎤)을 눌러 음성 메시지를 보내보세요!\n"
        f"  봇이 당신의 음성을 듣고 발음 인식 결과와 **음성 답장**을 보내드립니다.\n\n"
        f"📌 **명령어:**\n"
        f"• `/today` : 지금 바로 오늘의 회화 메시지 받기\n"
        f"• `/help` : 이용 안내"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

# 명령어 핸들러: /today
async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text("🎙 오늘의 회화와 음성을 준비 중입니다...")
    await send_daily_prompt(chat_id, context.application)

# 명령어 핸들러: /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        f"🤖 **양방향 영어 회화 봇 사용법**\n\n"
        f"1. **매일 자동 배달**: 매일 저녁 설정된 시간에 새로운 회화 문장과 원어민 음성이 발송됩니다.\n"
        f"2. **음성 대화 기능**: 텔레그램 음성 메시지(🎤)로 영어로 말해서 답장하면, 봇이 음성을 인식하고 **음성으로 다시 답장**합니다!"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def broadcast_daily_job(app: Application):
    """모든 구독자에게 매일 예약 전송 실행"""
    subscribers = load_subscribers()
    logger.info(f"매일 알림 전송 시작 (대상: {len(subscribers)}명)")
    for chat_id in subscribers:
        await send_daily_prompt(chat_id, app)

def main():
    global app
    if not TOKEN or TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("❌ [오류] .env 파일에 올바른 TELEGRAM_BOT_TOKEN을 입력해주세요!")
        return

    # Telegram Application 생성
    app = Application.builder().token(TOKEN).build()

    # 핸들러 등록
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(CommandHandler("help", help_command))
    
    # 🎤 사용자 음성 메시지 처리 핸들러 (양방향 음성 대화)
    app.add_handler(MessageHandler(filters.VOICE, handle_user_voice))

    # 스케줄러 설정
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        broadcast_daily_job,
        trigger=CronTrigger(hour=NOTIFY_HOUR, minute=NOTIFY_MINUTE),
        args=[app]
    )
    scheduler.start()
    logger.info(f"⏰ 매일 {NOTIFY_HOUR:02d}:{NOTIFY_MINUTE:02d}분 알림 스케줄러가 활성화되었습니다.")

    print("🚀 양방향 음성 텔레그램 영어 회화 튜터 봇이 작동을 시작합니다!")
    app.run_polling()

if __name__ == "__main__":
    main()
