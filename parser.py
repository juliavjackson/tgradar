import os
from telethon import TelegramClient
from telethon.tl.types import Message
from telethon.errors import ChannelPrivateError, ChannelInvalidError
import asyncio

class TelegramParser:
    def __init__(self):
        self.api_id = os.getenv('TELEGRAM_API_ID')
        self.api_hash = os.getenv('TELEGRAM_API_HASH')
        self.phone = os.getenv('TELEGRAM_PHONE')
        self.client = None

    async def start(self):
        if self.client is None:
            self.client = TelegramClient('anon', self.api_id, self.api_hash)
        await self.client.start(phone=self.phone)

    async def get_post_stats(self, channel_username: str, message_id: int):
        try:
            if self.client is None or not self.client.is_connected():
                await self.start()

            # Try to resolve the channel entity
            try:
                entity = await self.client.get_entity(f"@{channel_username}")
            except Exception:
                entity = await self.client.get_entity(channel_username)

            message = await self.client.get_messages(entity, ids=message_id)

            if not message:
                return None

            if not isinstance(message, Message):
                return None

            # Extract reactions
            reactions_count = 0
            top_reactions = []
            
            if message.reactions:
                for reaction_count in message.reactions.results:
                    reactions_count += reaction_count.count
                    # Handle both standard emoji and custom emoji reactions
                    emoji = getattr(reaction_count.reaction, 'emoticon', None)
                    if emoji is None:
                        emoji = '⭐'  # Fallback for custom emoji reactions
                    top_reactions.append((emoji, reaction_count.count))
                
                # Sort by count desc and take top 3
                top_reactions.sort(key=lambda x: x[1], reverse=True)
                top_reactions = top_reactions[:3]

            from telethon.tl.functions.channels import GetFullChannelRequest
            
            # Fetch subscribers
            subscribers = 0
            try:
                full_entity = await self.client(GetFullChannelRequest(channel=entity))
                subscribers = full_entity.full_chat.participants_count
            except Exception as e:
                print(f"Failed to fetch subscribers for {channel_username}: {e}")

            stats = {
                'channel': channel_username,
                'post_id': message_id,
                'date': message.date,
                'views': message.views if message.views else 0,
                'forwards': message.forwards if message.forwards else 0,
                'replies': message.replies.replies if message.replies else 0,
                'reactions_count': reactions_count,
                'top_reactions': top_reactions,
                'subscribers': subscribers
            }
            
            return stats

        except (ChannelPrivateError, ChannelInvalidError):
            raise ValueError("Канал приватный или не найден. Бот работает только с публичными каналами.")
        except Exception as e:
            print(f"Error fetching stats: {e}")
            raise e

    async def get_channel_info(self, channel_username: str) -> dict:
        """Fetch channel metadata + avg reach from last 50 posts via Telethon."""
        try:
            if self.client is None or not self.client.is_connected():
                await self.start()

            try:
                entity = await self.client.get_entity(f"@{channel_username}")
            except Exception:
                entity = await self.client.get_entity(channel_username)

            from telethon.tl.functions.channels import GetFullChannelRequest
            full = await self.client(GetFullChannelRequest(channel=entity))
            subscribers = full.full_chat.participants_count
            name = getattr(entity, 'title', channel_username)

            # Fetch last 50 posts and calculate avg views
            messages = await self.client.get_messages(entity, limit=50)
            views_list = [m.views for m in messages if m.views is not None]
            avg_reach = int(sum(views_list) / len(views_list)) if views_list else 0

            return {
                'handle': channel_username,
                'name': name,
                'subscribers': subscribers,
                'avg_reach': avg_reach,
            }

        except (ChannelPrivateError, ChannelInvalidError):
            raise ValueError("Канал приватный или не найден.")
        except Exception as e:
            print(f"Error fetching channel info: {e}")
            raise e

    async def disconnect(self):
        await self.client.disconnect()
