# 🎧 텔레그램 매일 영어 회화 음성 알림 봇 (Telegram Daily Voice Trainer)

매일 지정된 시각에 **텔레그램 알림**과 **고품질 원어민 음성(Edge Neural TTS)**을 자동으로 보내주는 영어 회화 봇입니다.

---

## 🛠️ 주요 기능
1. **원어민 음성(TTS) 전송**: Microsoft Edge의 최신 신경망 TTS(`en-US-AvaNeural`)를 활용하여 매우 자연스러운 억양의 영어 음성을 생성하고 텔레그램 **음성 메시지(Voice Note)** 형태로 보냅니다.
2. **매일 자동 예약 알림**: `APScheduler`를 이용해 매일 설정한 시간(기본 저녁 21:00)에 등록된 모든 사용자에게 회화 문장과 음성을 발송합니다.
3. **즉시 실행 명령어 (`/today`)**: 정해진 알림 시간 외에도 원할 때 즉시 회화 문장과 발음 음성을 수신할 수 있습니다.

---

## 📋 1. 텔레그램 봇 토큰 발급 방법 (@BotFather)

1. 텔레그램 앱 실행 후 검색창에 **`@BotFather`**를 검색합니다. (파란색 체크표시 확인)
2. `@BotFather` 대화방에서 **`/newbot`** 명령어를 입력합니다.
3. 봇의 이름(Name)과 아이디(Username, 끝에 `bot`으로 끝나야 함, 예: `my_english_speaker_bot`)를 입력합니다.
4. 생성이 완료되면 제공되는 **HTTP API Token** (예: `7123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`)을 복사합니다.

---

## ⚙️ 2. 설정 파일 (.env) 작성

`/Users/devorah/Documents/speakEnglish/.env` 파일을 열고 `@BotFather`에게 받은 토큰을 입력합니다:

```env
TELEGRAM_BOT_TOKEN=7123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
NOTIFY_HOUR=21
NOTIFY_MINUTE=00
VOICE_NAME=en-US-AvaNeural
```

---

## 🚀 3. 봇 실행 방법

터미널에서 아래 명령어로 봇을 실행합니다:

```bash
cd /Users/devorah/Documents/speakEnglish
python3 bot.py
```

### 📱 텔레그램 대화 시작
1. 생성한 텔레그램 봇 대화방에 들어간 뒤 **`/start`**를 누르면 구독자로 등록됩니다.
2. **`/today`**를 입력하면 즉시 텍스트 알림과 원어민 음성 메시지가 전달되는 것을 확인할 수 있습니다!
