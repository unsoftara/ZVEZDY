import asyncio
from telethon import TelegramClient, events
from telethon.tl.types import KeyboardButtonUrl, Channel
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors import FloodWaitError
import re
import sys

# Список ботов
first_bot_username = '@StarsEarnRubot'  # Первый бот
second_bot_username = '@StarsovEarnBot'  # Второй бот
third_bot_username = '@Farm_FreeStars_bot'  # Третий бот

# Глобальные списки для хранения результатов и отслеживания обработанных аккаунтов
account_results = []
processed_accounts = set()
# Словарь замков для каждого api_id
account_locks = {}

# Функция для чтения учетных данных из файла
def read_credentials(file_path="INFA.txt"):
    credentials = []
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            current_cred = {}
            for line in lines:
                line = line.strip()
                if not line:
                    if current_cred:
                        credentials.append(current_cred)
                        current_cred = {}
                    continue
                if line.startswith('@'):
                    continue  # Игнорируем строки с @username
                if '=' in line:
                    key, value = map(str.strip, line.split('=', 1))
                    current_cred[key] = value.strip('"')
            if current_cred:
                credentials.append(current_cred)
        return credentials
    except Exception as e:
        print(f"Ошибка при чтении файла {file_path}: {e}")
        return []

async def process_account(api_id, api_hash, session_string):
    # Инициализация клиента с использованием строки сессии
    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    try:
        await client.start()
        print(f"Клиент успешно запущен для аккаунта с api_id: {api_id}")
    except Exception as e:
        print(f"Ошибка при запуске клиента для аккаунта с api_id: {api_id}: {e}")
        return None, None, None, None

    # Инициализация замка для текущего api_id
    if api_id not in account_locks:
        account_locks[api_id] = asyncio.Lock()

    # Открываем чат с первым ботом
    try:
        first_bot = await client.get_entity(first_bot_username)
        print(f"Чат с первым ботом открыт: {first_bot.username} (ID: {first_bot.id})")
    except Exception as e:
        print(f"Ошибка при открытии чата с первым ботом ({first_bot_username}): {e}")
        await client.disconnect()
        return None, None, None, None

    # Открываем чат со вторым ботом
    try:
        second_bot = await client.get_entity(second_bot_username)
        print(f"Чат с вторым ботом открыт: {second_bot.username} (ID: {second_bot.id})")
    except Exception as e:
        print(f"Ошибка при открытии чата с вторым ботом ({second_bot_username}): {e}")
        await client.disconnect()
        return None, None, None, None

    # Открываем чат с третьим ботом
    try:
        third_bot = await client.get_entity(third_bot_username)
        print(f"Чат с третьим ботом открыт: {third_bot.username} (ID: {third_bot.id})")
    except Exception as e:
        print(f"Ошибка при открытии чата с третьим ботом ({third_bot_username}): {e}")
        await client.disconnect()
        return None, None, None, None

    # Проверяем последние сообщения в чате с первым ботом
    try:
        print("Проверяю последние сообщения в чате с первым ботом...")
        async for message in client.iter_messages(first_bot, limit=5):
            print(f"Историческое сообщение от первого бота: {message.text} (ID: {message.id})")
    except Exception as e:
        print(f"Ошибка при получении сообщений от первого бота: {e}")

    # Отправляем команды для начала заданий
    try:
        await client.send_message(first_bot, "📋 Задания")
        print("Отправлено сообщение '📋 Задания' первому боту")
        await client.send_message(second_bot, "💎 Задания")
        print("Отправлено сообщение '💎 Задания' второму боту")
        await client.send_message(third_bot, "📋 Задания")
        print("Отправлено сообщение '📋 Задания' третьему боту")
    except Exception as e:
        print(f"Ошибка при отправке команд ботам: {e}")
        await client.disconnect()
        return None, None, None, None

    # Обработчик для всех новых сообщений от ботов
    @client.on(events.NewMessage(chats=[first_bot, second_bot, third_bot]))
    async def log_all_messages(event):
        bot_name = "первого бота" if event.chat_id == first_bot.id else "второго бота" if event.chat_id == second_bot.id else "третьего бота"
        print(f"Новое сообщение от {bot_name}: {event.message.text} (ID: {event.message.id})")

    # Обработчик для отредактированных сообщений от ботов
    @client.on(events.MessageEdited(chats=[first_bot, second_bot, third_bot]))
    async def handle_edited_message(event):
        bot_name = "первого бота" if event.chat_id == first_bot.id else "второго бота" if event.chat_id == second_bot.id else "третьего бота"
        print(f"Сообщение от {bot_name} отредактировано: {event.message.text} (ID: {event.message.id})")
        await handle_message_logic(event, client)

    # Обработчик для сообщения о выполнении всех заданий от всех ботов
    @client.on(events.NewMessage(chats=[first_bot, second_bot, third_bot], pattern=r'(?:Вы уже выполнили все доступные задания 👏 Попробуйте позже|😔 К сожалению задания закончились, загляните позже!)'))
    @client.on(events.MessageEdited(chats=[first_bot, second_bot, third_bot], pattern=r'(?:Вы уже выполнили все доступные задания 👏 Попробуйте позже|😔 К сожалению задания закончились, загляните позже!)'))
    async def handle_task_completed(event):
        print(f"Обработчик handle_task_completed вызван для аккаунта с api_id {api_id}")

        # Используем замок для предотвращения параллельной обработки
        async with account_locks[api_id]:
            if api_id in processed_accounts:
                print(f"Аккаунт с api_id {api_id} уже обработан, пропуск")
                return

            bot_name = "первого бота" if event.chat_id == first_bot.id else "второго бота" if event.chat_id == second_bot.id else "третьего бота"
            print(f"Обнаружено сообщение от {bot_name}: {event.message.text}")
            print("Все задания выполнены, проверка баланса...")

            # Проверка баланса первого бота с повторными попытками
            first_bot_balance = "0"
            for attempt in range(3):
                try:
                    await client.send_message(first_bot, "👤 Профиль")
                    await asyncio.sleep(2)  # Ожидание ответа
                    async for message in client.iter_messages(first_bot, limit=1):
                        balance_match = re.search(r'💰 Баланс: (.+)', message.text)
                        if balance_match:
                            balance_str = balance_match.group(1)
                            # Очистка строки от нечисловых символов (например, ⭐️)
                            cleaned_balance = re.sub(r'[^\d.]', '', balance_str)
                            first_bot_balance = cleaned_balance
                            print(f"Баланс первого бота: {first_bot_balance}")
                            break
                    else:
                        print(f"Попытка {attempt + 1}: Баланс первого бота не найден")
                        continue
                    break
                except FloodWaitError as e:
                    wait_time = e.seconds
                    print(f"Ограничение Telegram, ожидание {wait_time} секунд для отправки сообщения первому боту")
                    await asyncio.sleep(wait_time)
            else:
                print("Баланс первого бота не найден после 3 попыток")

            # Проверка баланса второго бота с повторными попытками
            second_bot_stars = "0"
            for attempt in range(3):
                try:
                    await client.send_message(second_bot, "🎁 Вывести Звёзды")
                    await asyncio.sleep(2)  # Ожидание ответа
                    async for message in client.iter_messages(second_bot, limit=1):
                        stars_match = re.search(r'Заработано: (.+)', message.text)
                        if stars_match:
                            stars_str = stars_match.group(1)
                            # Очистка строки от нечисловых символов
                            cleaned_stars = re.sub(r'[^\d.]', '', stars_str)
                            second_bot_stars = cleaned_stars
                            print(f"Заработано второго бота: {second_bot_stars}")
                            break
                    else:
                        print(f"Попытка {attempt + 1}: Заработано второго бота не найдено")
                        continue
                    break
                except FloodWaitError as e:
                    wait_time = e.seconds
                    print(f"Ограничение Telegram, ожидание {wait_time} секунд для отправки сообщения второму боту")
                    await asyncio.sleep(wait_time)
            else:
                print("Заработано второго бота не найдено после 3 попыток")

            # Проверка баланса третьего бота с повторными попытками
            third_bot_balance = "0"
            for attempt in range(3):
                try:
                    await client.send_message(third_bot, "👤 Профиль")
                    await asyncio.sleep(2)  # Ожидание ответа
                    async for message in client.iter_messages(third_bot, limit=1):
                        balance_match = re.search(r'💰 Баланс: (.+)', message.text)
                        if balance_match:
                            balance_str = balance_match.group(1)
                            # Очистка строки от нечисловых символов (например, ⭐️)
                            cleaned_balance = re.sub(r'[^\d.]', '', balance_str)
                            third_bot_balance = cleaned_balance
                            print(f"Баланс третьего бота: {third_bot_balance}")
                            break
                    else:
                        print(f"Попытка {attempt + 1}: Баланс третьего бота не найден")
                        continue
                    break
                except FloodWaitError as e:
                    wait_time = e.seconds
                    print(f"Ограничение Telegram, ожидание {wait_time} секунд для отправки сообщения третьему боту")
                    await asyncio.sleep(wait_time)
            else:
                print("Баланс третьего бота не найден после 3 попыток")

            # Суммирование балансов
            try:
                total_balance = float(first_bot_balance) + float(second_bot_stars) + float(third_bot_balance)
                print(f"Общий баланс для аккаунта с api_id {api_id}: {total_balance}")
            except ValueError:
                print(f"Ошибка при суммировании балансов: {first_bot_balance} + {second_bot_stars} + {third_bot_balance}")
                total_balance = 0.0

            # Сохраняем результат и помечаем аккаунт как обработанный
            account_results.append((api_id, total_balance))
            processed_accounts.add(api_id)
            print(f"Аккаунт с api_id {api_id} обработан, добавлен в processed_accounts")
            await client.disconnect()

    # Основной обработчик для сообщений, начинающихся с "Подпишитесь", "Запустите" или "Добавьте"
    @client.on(events.NewMessage(chats=[first_bot, second_bot, third_bot], pattern=r'(?:^|\n)(Подпишитесь|Запустите|Добавьте).*'))
    async def handle_subscription_message(event):
        await handle_message_logic(event, client)

    # Общая логика обработки сообщений
    async def handle_message_logic(event, client):
        bot_name = "первого бота" if event.chat_id == first_bot.id else "второго бота" if event.chat_id == second_bot.id else "третьего бота"
        print(f"Обработчик сработал для {bot_name}: {event.message.text}")
        message = event.message
        if not message.reply_markup:
            print("В сообщении нет кнопок")
            return

        buttons = message.reply_markup.rows[0].buttons if message.reply_markup.rows else []
        print(f"Найдено кнопок: {len(buttons)}")
        if len(buttons) < 2:
            print("Недостаточно кнопок")
            return

        first_button = buttons[0]
        second_button = buttons[1]

        if not isinstance(first_button, KeyboardButtonUrl):
            print("Первая кнопка не URL")
            return

        link = first_button.url
        print(f"Обработка ссылки: {link}")
        try:
            # Проверяем, содержит ли ссылка параметр ?start= или ?startgroup=
            start_param_match = re.match(r'https?://t\.me/[^?]+\?(start|startgroup)=.+', link)
            if start_param_match:
                param_type = start_param_match.group(1)
                if param_type == 'startgroup':
                    print(f"Пропуск ссылки {link}: добавление бота в группу не поддерживается")
                    return
                # Извлекаем юзернейм из ссылки
                username_match = re.match(r'https?://t\.me/([^?]+)\?start=.+', link)
                if username_match:
                    username = f"@{username_match.group(1)}"
                    entity = await client.get_entity(username)
                    if hasattr(entity, 'bot') and entity.bot:
                        await client.send_message(entity, '/start')
                        print(f"Запуск бота по ссылке с параметром: {link}")
                    else:
                        print(f"Сущность {link} не является ботом")
                else:
                    print(f"Не удалось извлечь юзернейм из ссылки: {link}")
            else:
                # Проверяем, является ли ссылка инвайт-ссылкой (начинается с +)
                invite_match = re.match(r'https?://t\.me/\+(.+)', link)
                if invite_match:
                    invite_hash = invite_match.group(1)
                    try:
                        await client(ImportChatInviteRequest(invite_hash))
                        print(f"Присоединился к приватному каналу/группе по инвайт-ссылке: {link}")
                    except FloodWaitError as e:
                        wait_time = e.seconds
                        print(f"Ограничение Telegram, ожидание {wait_time} секунд для ссылки {link}")
                        await asyncio.sleep(wait_time)
                        try:
                            await client(ImportChatInviteRequest(invite_hash))
                            print(f"Повторное присоединение к приватному каналу/группе по инвайт-ссылке: {link}")
                        except Exception as e2:
                            print(f"Ошибка при повторном присоединении к инвайт-ссылке {link}: {e2}")
                    except Exception as e:
                        print(f"Ошибка при присоединении к инвайт-ссылке {link}: {e}")
                else:
                    # Обычная обработка канала или бота
                    entity = await client.get_entity(link)
                    print(f"Тип сущности: {type(entity).__name__}")
                    if isinstance(entity, Channel):
                        await client(JoinChannelRequest(channel=entity))
                        print(f"Подписка на канал: {link}")
                    elif hasattr(entity, 'bot') and entity.bot:
                        await client.send_message(entity, '/start')
                        print(f"Запуск бота: {link}")
                    else:
                        print(f"Пропуск ссылки: {link} - не канал или бот")
        except ValueError as e:
            print(f"Ошибка при получении сущности {link}: {e}")
            try:
                channel_username = re.match(r'https?://t\.me/(.+)', link)
                if channel_username and not channel_username.group(1).startswith('+'):
                    channel_username = channel_username.group(1)
                    entity = await client.get_entity(channel_username)
                    if isinstance(entity, Channel):
                        await client(JoinChannelRequest(channel=entity))
                        print(f"Подписка на канал по юзернейму: {link}")
                    else:
                        print(f"Сущность {link} не является каналом")
            except Exception as e2:
                print(f"Ошибка при обработке ссылки как юзернейма: {e2}")
        except Exception as e:
            print(f"Неожиданная ошибка с ссылкой {link}: {e}")

        # Эмуляция нажатия на вторую кнопку
        print(f"Эмуляция нажатия второй кнопки: {second_button.text if not isinstance(second_button, KeyboardButtonUrl) else second_button.url}")
        try:
            await message.click(1)  # Нажимаем вторую кнопку (индекс 1)
            print("Вторая кнопка нажата")
            await asyncio.sleep(1)  # Небольшая задержка для предотвращения дублирования
        except Exception as e:
            print(f"Ошибка при нажатии второй кнопки: {e}")
            if isinstance(second_button, KeyboardButtonUrl):
                await client.send_message(event.chat, second_button.url)
            else:
                await client.send_message(event.chat, second_button.text)
            print("Вторая кнопка обработана через отправку текста")

    print(f"Ожидание новых сообщений от {first_bot_username}, {second_bot_username} и {third_bot_username} для аккаунта с api_id {api_id}...")
    return client, first_bot, second_bot, third_bot

async def main():
    global account_results, processed_accounts
    # Очищаем результаты и обработанные аккаунты перед каждым запуском
    account_results.clear()
    processed_accounts.clear()

    # Чтение учетных данных из файла
    credentials = read_credentials()
    if not credentials:
        print("Не удалось загрузить учетные данные. Программа завершена.")
        return

    for cred in credentials:
        api_id = cred.get('api_id')
        api_hash = cred.get('api_hash')
        session_string = cred.get('session_string')
        if not all([api_id, api_hash, session_string]):
            print(f"Неполные учетные данные для аккаунта: {cred}. Пропуск.")
            continue

        print(f"\nОбработка аккаунта с api_id: {api_id}")
        client, first_bot, second_bot, third_bot = await process_account(api_id, api_hash, session_string)
        if client and first_bot and second_bot and third_bot:
            # Ждем завершения обработки аккаунта
            await client.run_until_disconnected()
        else:
            print(f"Пропуск аккаунта с api_id: {api_id} из-за ошибок инициализации")

    # Вывод итоговых балансов
    grand_total = 0.0
    print("\nИтоговые балансы по всем аккаунтам:")
    for api_id, balance in account_results:
        print(f"Аккаунт с api_id {api_id}: {balance}")
        grand_total += balance
    print(f"Общий баланс по всем аккаунтам: {grand_total}")
    print(f"Обработка всех аккаунтов завершена.")

async def run_forever():
    while True:
        print("\nЗапуск обработки...")
        await main()
        print("Ожидание 50 секунд перед следующим запуском...")
        await asyncio.sleep(50)

if __name__ == '__main__':
    asyncio.run(run_forever())