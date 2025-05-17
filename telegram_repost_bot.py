import os
import random
import json
from datetime import datetime
from bs4 import BeautifulSoup
from telegram import Bot, InputMediaPhoto
from telegram.error import TelegramError
import logging
from typing import List, Dict, Set, Tuple

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class TelegramPhotoBot:
    def __init__(self, html_files: List[str], photos_folder: str, 
                 bot_token: str, channel_id: str):
        self.html_files = html_files
        self.photos_folder = photos_folder
        self.bot = Bot(token=bot_token)
        self.channel_id = channel_id
        self.caption = "[Краска на теле](https://t.me/body_paint_tattoo)"
        self.sent_messages_file = "sent_messages.json"
        self.sent_messages = self.load_sent_messages()
    
    def load_sent_messages(self) -> Set[str]:
        """Load the set of already sent messages from JSON file."""
        try:
            with open(self.sent_messages_file, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except FileNotFoundError:
            logger.info("Sent messages file not found, starting fresh")
            return set()
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Error loading sent messages: {e}")
            return set()

    def save_sent_messages(self) -> None:
        """Save the set of sent messages to JSON file."""
        try:
            with open(self.sent_messages_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.sent_messages), f)
        except Exception as e:
            logger.error(f"Error saving sent messages: {e}")

    def get_random_file(self) -> str:
        """Get a random HTML file from the available files."""
        return random.choice(self.html_files)

    def parse_html(self, html_file: str) -> Dict[str, List[Tuple[str, str]]]:
        """
        Parse HTML file to extract photo groups.
        
        Returns:
            Dict where keys are timestamps and values are lists of (message_id, photo_path) tuples
        """
        media_groups = {}
        current_group = []
        prev_time = None
        
        try:
            with open(html_file, 'r', encoding='utf-8') as file:
                soup = BeautifulSoup(file, 'html.parser')
        except Exception as e:
            logger.error(f"Error reading HTML file {html_file}: {e}")
            return media_groups
        
        messages = soup.find_all('div', class_='message')
        
        for msg in messages:
            time_div = msg.find('div', class_='pull_right date details')
            if not time_div or not time_div.has_attr('title'):
                continue

            try:
                timestamp_str = time_div['title'].split(' UTC')[0].strip()
                timestamp = datetime.strptime(timestamp_str, '%d.%m.%Y %H:%M:%S')
                time_key = timestamp.strftime('%Y%m%d%H%M%S')
            except ValueError as e:
                logger.warning(f"Invalid timestamp format: {e}")
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

    async def send_media_group(self, message_group: List[Tuple[str, str]]) -> bool:
        """
        Send a group of photos to Telegram channel.
        
        Args:
            message_group: List of (message_id, photo_path) tuples
            
        Returns:
            bool: True if sending was successful
        """
        valid_photos = [
            (msg_id, p) for msg_id, p in message_group
            if os.path.isfile(p) and p.lower().endswith(('.jpg', '.jpeg', '.png'))
        ]

        if not valid_photos:
            return False

        try:
            media_group = []
            message_ids = []
            for i, (msg_id, p) in enumerate(valid_photos[:10]):  # Max 10 photos per group
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
            
            # Mark messages as sent
            self.sent_messages.update(message_ids)
            self.save_sent_messages()
            
            logger.info(f"Successfully sent {len(media_group)} photos")
            return True
        except TelegramError as e:
            logger.error(f"Telegram API error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending photos: {e}")
            return False

    async def run_once(self) -> None:
        """
        Run the bot once (for cron job).
        Attempts to send one media group and exits.
        """
        try:
            html_file = self.get_random_file()
            logger.info(f"Processing file: {html_file}")
            
            media_groups = self.parse_html(html_file)
            
            if media_groups:
                # Select a random group from the file
                time_key, group = random.choice(list(media_groups.items()))
                await self.send_media_group(group)
            else:
                logger.info("No unsent media groups found in the selected file")
        except Exception as e:
            logger.error(f"Error during execution: {e}")


async def main():
    # Configuration - лучше вынести в переменные окружения
    config = {
        'html_files': os.getenv('HTML_FILES', 'messages.html,messages2.html,messages3.html').split(','),
        'photos_folder': os.getenv('PHOTOS_FOLDER', 'photos'),
        'bot_token': os.getenv('TELEGRAM_BOT_TOKEN', '7504132147:AAHfZGVdvEbw2LrBhC_aXbVatV-xG41i3ok'),
        'channel_id': os.getenv('TELEGRAM_CHANNEL_ID', '@body_paint_tattoo')
    }

    # Validate configuration
    if not config['bot_token']:
        logger.error("Telegram bot token is required!")
        return

    bot = TelegramPhotoBot(**config)
    await bot.run_once()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())


    