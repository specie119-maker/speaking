import os
import json
import logging
import random
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import edge_tts

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
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
    return [
        {
            "id": 1,
            "english": "Hey there! Today is a great day to practice English. Let me know if you can hear this audio clearly!",
            "korean": "안녕하세요! 오늘은 영어 연습하기 아주 좋은 날입니다. 음성이 잘 들리는지 확인해 보세요!",
            "tip": "하루 5분씩 꾸준히 소리내어 읽어보세요."
        }
    ]

async def generate_voice_file(text: str, filename: str = "voice.mp3") -> str:
    """Edge-TTS를 이용하여 고품질 미국식 원어민 음성 파일 생성"""
    communicate = edge_tts.Communicate(text, VOICE_NAME)
    await communicate.save(filename)
    return filename

async def send_daily_prompt(chat_id: int, app: Application):
    """지정된 사용자에게 텍스트와 음성(TTS) 메시지 전송"""
    expressions = load_expressions()
    item = random.choice(expressions)
    
    text_message = (
        f"🎧 **[오늘의 1분 영어 회화]**\n\n"
        f"🗣 **English:**\n{item['english']}\n\n"
        f"🇰🇷 **한국어:**\n{item['korean']}\n\n"
        f"💡 **학습 팁:** {item.get('tip', '')}\n\n"
        f"👇 아래 음성을 들으며 그대로 3번 따라 읽어보세요!"
    )

    voice_path = f"voice_{chat_id}.mp3"
    try:
        # 음성 파일 생성
        await generate_voice_file(item['english'], voice_path)
        
        # 텍스트 메시지 전송
        await app.bot.send_message(chat_id=chat_id, text=text_message, parse_mode="Markdown")
        
        # 음성 파일 전송 (Telegram Voice 노트 모드)
        with open(voice_path, "rb") as voice_file:
            await app.bot.send_voice(chat_id=chat_id, voice=voice_file, caption="🎙 원어민 발음 듣기")
            
    except Exception as e:
        logger.error(f"메시지/음성 전송 중 오류 (Chat ID: {chat_id}): {e}")
    finally:
        if os.path.exists(voice_path):
            os.remove(voice_path)

# 명령어 핸들러: /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers = load_subscribers()
    
    if chat_id not in subscribers:
        subscribers.add(chat_id)
        save_subscribers(subscribers)
        
    welcome_text = (
        f"🎉 **영어 회화 알림 봇에 오신 것을 환영합니다!**\n\n"
        f"매일 저녁 {NOTIFY_HOUR:02d}:{NOTIFY_MINUTE:02d}분에 오늘의 회화 문장과 **원어민 음성(TTS)**을 보내드립니다.\n\n"
        f"📌 **사용 가능한 명령어:**\n"
        f"• `/today` : 지금 바로 오늘의 회화 문장과 음성 받기\n"
        f"• `/help` : 도움말 보기\n\n"
        f"지금 바로 테스트해보고 싶다면 `/today`를 눌러보세요!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

# 명령어 핸들러: /today (즉시 음성 받기)
async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text("🎙 음성을 생성 중입니다. 잠시만 기다려주세요...")
    await send_daily_prompt(chat_id, context.application)

# 명령어 핸들러: /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        f"🤖 **영어 회화 봇 이용 안내**\n\n"
        f"• 매일 설정된 시간({NOTIFY_HOUR:02d}:{NOTIFY_MINUTE:02d})에 자동으로 알림과 음성 메시지가 전달됩니다.\n"
        f"• `/today` 명령어 입력 시 즉시 새로운 회화 문장과 음성을 받으실 수 있습니다."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def broadcast_daily_job(app: Application):
    """모든 구독자에게 매일 예약 전송 실행"""
    subscribers = load_subscribers()
    logger.info(f"매일 알림 전송 시작 (대상: {len(subscribers)}명)")
    for chat_id in subscribers:
        await send_daily_prompt(chat_id, app)

def main():
    if not TOKEN or TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("❌ [오류] .env 파일에 올바른 TELEGRAM_BOT_TOKEN을 입력해주세요!")
        print("💡 텔레그램 @BotFather에게서 받은 토큰을 .env 파일에 적어주셔야 합니다.")
        return

    # Telegram Application 생성
    app = Application.builder().token(TOKEN).build()

    # 핸들러 등록
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(CommandHandler("help", help_command))

    # 스케줄러 설정 (AsyncIOScheduler)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        broadcast_daily_job,
        trigger=CronTrigger(hour=NOTIFY_HOUR, minute=NOTIFY_MINUTE),
        args=[app]
    )
    scheduler.start()
    logger.info(f"⏰ 매일 {NOTIFY_HOUR:02d}:{NOTIFY_MINUTE:02d}분 알림 스케줄러가 활성화되었습니다.")

    print("🚀 텔레그램 영어 회화 트레이너 봇이 작동을 시작합니다!")
    app.run_polling()

if __name__ == "__main__":
    main()
