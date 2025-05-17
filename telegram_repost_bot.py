import os
import asyncio
import random
import json
from datetime import datetime
from bs4 import BeautifulSoup
from telegram import Bot, InputMediaPhoto
from telegram.error import TelegramError


class TelegramPhotoBot:
    def __init__(self, html_files, photos_folder, bot_token, channel_id):
        self.html_files = html_files
        self.photos_folder = photos_folder
        self.bot = Bot(token=bot_token)
        self.channel_id = channel_id
        self.caption = "[Краска на теле](https://t.me/body_paint_tattoo)"
        self.sent_messages_file = "sent_messages.json"
        self.sent_messages = self.load_sent_messages()
    
    def load_sent_messages(self):
        try:
            with open(self.sent_messages_file, 'r') as f:
                return set(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            return set()

    def save_sent_messages(self):
        with open(self.sent_messages_file, 'w') as f:
            json.dump(list(self.sent_messages), f)

    def get_random_file(self):
        return random.choice(self.html_files)

    def parse_html(self, html_file):
        media_groups = {}
        current_group = []
        prev_time = None
        
        with open(html_file, 'r', encoding='utf-8') as file:
            soup = BeautifulSoup(file, 'html.parser')
        
        messages = soup.find_all('div', class_='message')
        
        for msg in messages:
            time_div = msg.find('div', class_='pull_right date details')
            if not time_div or not time_div.has_attr('title'):
                continue

            try:
                timestamp_str = time_div['title'].split(' UTC')[0].strip()
                timestamp = datetime.strptime(timestamp_str, '%d.%m.%Y %H:%M:%S')
                time_key = timestamp.strftime('%Y%m%d%H%M%S')
            except ValueError:
                continue

            media_link = msg.find('a', class_='photo_wrap')
            if not media_link or not media_link.has_attr('href'):
                continue

            photo_name = os.path.basename(media_link['href'])
            photo_path = os.path.join(self.photos_folder, photo_name)
            message_id = f"{os.path.basename(html_file)}_{photo_name}"

            if message_id in self.sent_messages:
                continue

            if prev_time is None:
                prev_time = time_key
                current_group.append((message_id, photo_path))
            elif time_key == prev_time:
                current_group.append((message_id, photo_path))
            else:
                if current_group:
                    media_groups[prev_time] = current_group.copy()
                current_group = [(message_id, photo_path)]
                prev_time = time_key
        
        if current_group:
            media_groups[prev_time] = current_group
            
        return media_groups

    async def send_media_group(self, message_group):
        valid_photos = [
            (msg_id, p) for msg_id, p in message_group
            if os.path.isfile(p) and p.lower().endswith(('.jpg', '.jpeg', '.png'))
        ]

        if not valid_photos:
            return False

        try:
            media_group = []
            message_ids = []
            for i, (msg_id, p) in enumerate(valid_photos[:10]):
                with open(p, 'rb') as photo_file:
                    media_group.append(InputMediaPhoto(
                        media=photo_file,
                        caption=self.caption if i == 0 else None,
                        parse_mode='MarkdownV2'
                    ))
                    message_ids.append(msg_id)

            await self.bot.send_media_group(
                chat_id=self.channel_id,
                media=media_group
            )
            
            # Помечаем сообщения как отправленные
            self.sent_messages.update(message_ids)
            self.save_sent_messages()
            
            print(f"Отправлено {len(media_group)} фото")
            return True
        except TelegramError as e:
            print(f"Ошибка отправки: {e}")
            return False

    async def run(self):
        while True:
            try:
                html_file = self.get_random_file()
                print(f"Обрабатываю файл: {html_file}")
                
                media_groups = self.parse_html(html_file)
                
                if media_groups:
                    # Выбираем случайную группу из файла
                    time_key, group = random.choice(list(media_groups.items()))
                    await self.send_media_group(group)
                
                # Пауза между сообщениями
                await asyncio.sleep(10)
                
            except Exception as e:
                print(f"Ошибка: {e}")
                await asyncio.sleep(30)

# Настройки
if __name__ == "__main__":
    config = {
        'html_files': [
            'messages.html',
            'messages2.html', 
            'messages3.html'
        ],
        'photos_folder': 'photos',
        'bot_token': '7504132147:AAHfZGVdvEbw2LrBhC_aXbVatV-xG41i3ok',
        'channel_id': '@test_nikita_bots'  # Или числовой ID канала
    }

    bot = TelegramPhotoBot(**config)
    asyncio.run(bot.run())