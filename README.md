# Telegram Stats Bot 📊

Бот для получения детальной статистики постов из публичных Telegram-каналов.

## Функционал
- 👁 Просмотры
- 🔄 Репосты
- 💬 Комментарии
- ❤️ Реакции (включая топ-3 популярных)

## Установка

1. **Клонируйте репозиторий:**
   ```bash
   git clone <your-repo-url>
   cd telegram-stats-bot
   ```

2. **Создайте виртуальное окружение:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # На macOS/Linux
   # venv\Scripts\activate  # На Windows
   ```

3. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Настройте переменные окружения:**
   - Скопируйте `.env.example` в `.env`:
     ```bash
     cp .env.example .env
     ```
   - Откройте `.env` и заполните:
     - `BOT_TOKEN`: Получите у [@BotFather](https://t.me/BotFather).
     - `TELEGRAM_API_ID` и `TELEGRAM_API_HASH`: Получите на [my.telegram.org](https://my.telegram.org).

## Запуск

```bash
python bot.py
```

При первом запуске скрипт попросит ввести номер телефона и код подтверждения для авторизации Telegram-клиента (Telethon). Это нужно для доступа к информации о постах. Сессия сохранится в файл `anon.session` и при следующих запусках вход не потребуется.

## Использование

1. Запустите бота.
2. Отправьте команду `/start`.
3. Пришлите ссылку на пост из публичного канала, например: `https://t.me/durov/1`.
4. Бот пришлет статистику.

## Требования
- Python 3.10+
- Аккаунт Telegram (для получения API ID/Hash)
