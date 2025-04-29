import asyncio
import logging
import sys
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import SUB_BOT_TOKEN, DATABASE_NAME
import database

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

bot = Bot(token=SUB_BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: types.Message):
    user = message.from_user
    args = message.text.split()

    if len(args) < 2:
        await message.answer("Пожалуйста, используйте правильную ссылку для перехода.")
        return

    try:

        arbitrage_username, channel_id, link_id = args[1].split('-')

        channel_id = int(channel_id)
        link_id = int(link_id)


        channel = await database.get_channel(channel_id)
        try:
            async with aiosqlite.connect(DATABASE_NAME) as db:
                await db.execute('''
                    UPDATE links
                    SET enter_counter = enter_counter + 1
                    WHERE id = ?
                ''', (link_id,))
                await db.commit()
        except Exception as e:
            print(f"Ошибка при увеличении счётчика: {e}")

        if not channel:
            await message.answer("Канал не найден.")
            return

        users = await database.get_users()
        if user.id == users[0][0]:
            await message.answer("Вы зарегистрированы как арбитражник! Вам не будет приписан этот реферал.")
        else:
            await database.register_subscriber(user.id, channel_id, arbitrage_username, link_id)
        keyboard = [[InlineKeyboardButton(text="Перейти в канал", url=channel[2])]]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer(
            f"Добро пожаловать! Перейдите по ссылке, чтобы присоединиться к каналу {channel[1]}",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")


async def check_subscription_status(bot: Bot, user_id: int, channel_id_or_username: str | int) -> bool:
    """
    Проверяет, подписан ли пользователь на канал
    """
    try:
        logger.info(f"[Step 1] Проверка канала: {channel_id_or_username}")

        chat = await bot.get_chat(channel_id_or_username)
        logger.info(f"[Step 2] Канал найден: {chat.title} (ID: {chat.id})")

        try:
            member = await bot.get_chat_member(chat.id, user_id)
            logger.info(f"[Step 3] Статус пользователя {user_id}: {member.status}")
            return member.status in ['member', 'administrator', 'creator']
        except Exception as e:
            logger.warning(f"[Step 3] Не удалось получить статус пользователя: {e}")
            return False

    except Exception as e:
        logger.error(f"[ERROR] Канал не найден: {e}")
        return False


async def check_subscriptions():
    while True:
        try:

            async with aiosqlite.connect(DATABASE_NAME) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute('''
                    SELECT s.user_id, s.channel_id, s.id
                    FROM subscribers s
                    WHERE s.subscribed = 0
                ''')
                unsubscribed = await cursor.fetchall()
            
            for sub in unsubscribed:
                try:

                    channel = await database.get_channel(sub['channel_id'])
                    if not channel:
                        logger.warning(f"Channel with ID {sub['channel_id']} not found in database")
                        continue

                    chat_member = await bot.get_chat_member(channel[4], sub['user_id'])
                    if chat_member.status in ['member', 'administrator', 'creator']:

                        async with aiosqlite.connect(DATABASE_NAME) as db:
                            await db.execute('''
                                UPDATE subscribers 
                                SET subscribed = 1, subscribed_at = CURRENT_TIMESTAMP
                                WHERE id = ?
                            ''', (sub['id'],))
                            await db.commit()
                        sub = await database.get_subscriber(sub['id'])

                        async with aiosqlite.connect(DATABASE_NAME) as db:
                            await db.execute('''
                                UPDATE links
                                SET free_users = free_users + 1
                                WHERE id = ?
                            ''', (sub[4],))
                            await db.commit()

                except Exception as e:
                    if "chat not found" in str(e):
                        logger.warning(f"Channel {channel[4]} ({channel[1]}) not found or inaccessible. Channel links: RU: {channel[2]}, EN: {channel[3]}")
                        continue
                    logger.error(f"Error checking subscription for user {sub['user_id']}: {e}")
                    continue


            logger.info("Starting paid channels check...")
            async with aiosqlite.connect(DATABASE_NAME) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute('''
                    SELECT id, channel_id
                    FROM channels 
                    WHERE paid = 1
                ''')
                paid_channels = await cursor.fetchall()
                logger.info(f"Found {len(paid_channels)} paid channels to check")
            
            for channel_db in paid_channels:
                try:
                    logger.info(f"Processing paid channel with ID: {channel_db['id']}")

                    channel = await database.get_channel(channel_db['id'])
                    print(channel)
                    if not channel:
                        logger.warning(f"Channel with ID {channel_db['id']} not found in database")
                        continue
                    logger.info(f"Channel info: ID={channel[0]}, Name={channel[1]}, Telegram ID={channel[4]}")

                    bot_member = await bot.get_chat_member(channel[4], bot.id)
                    if bot_member.status not in ['administrator', 'creator']:
                        logger.warning(f"Bot is not admin in paid channel {channel[4]} ({channel[1]})")
                        continue
                    logger.info(f"Bot is admin in channel {channel[4]}")

                    async with aiosqlite.connect(DATABASE_NAME) as db:
                        db.row_factory = aiosqlite.Row
                        cursor = await db.execute('''
                            SELECT DISTINCT s.user_id, s.id, s.channel_id
                            FROM subscribers s 
                            WHERE s.paid = 0 AND s.subscribed = 1
                        ''')
                        free_subscribers = await cursor.fetchall()
                        logger.info(f"Found {len(free_subscribers)} free subscribers to check")
                    for subscriber in free_subscribers:
                        try:
                            logger.info(f"Checking subscriber {subscriber['user_id']} in channel {channel[4]}")
                            chat_member = await bot.get_chat_member(channel[4], subscriber['user_id'])
                            logger.info(f"Subscriber {subscriber['user_id']} status in channel: {chat_member.status}")
                            if chat_member.status in ['member', 'administrator', 'creator']:
                                logger.info(f"Found free subscriber {subscriber['user_id']} in paid channel {channel[4]}. Updating status...")
                                await database.update_subscriber_paid_status(subscriber['user_id'], subscriber['channel_id'], True)

                                sub = await database.get_subscriber(subscriber['id'])
                                async with aiosqlite.connect(DATABASE_NAME) as db:
                                    await db.execute('''
                                        UPDATE links
                                        SET paid_users = paid_users + 1
                                        WHERE id = ?
                                    ''', (sub[4],))
                                    await db.commit()
                                print(channel[0])
                                print(subscriber['id'])
                                async with aiosqlite.connect(DATABASE_NAME) as db:
                                    await db.execute('''
                                        UPDATE subscribers
                                        SET channel_id = ?
                                        WHERE id = ?
                                    ''', (channel[0], subscriber['id']))
                                    await db.commit()
                                logger.info(f"Successfully updated paid status for subscriber {subscriber['user_id']}")
                            else:
                                logger.info(f"Subscriber {subscriber['user_id']} is not a member of channel {channel[4]}")
                        except Exception as e:
                            if "chat not found" in str(e):
                                logger.warning(f"Channel {channel[4]} ({channel[1]}) not found or inaccessible. Channel links: RU: {channel[2]}, EN: {channel[3]}")
                                continue
                            logger.error(f"Error checking paid subscription for user {subscriber['user_id']}: {e}")
                except:
                    logger.error(f"Error checking paid subscription for user")
                    continue
            logger.info(f"Checked {len(unsubscribed)} unsubscribed users and {len(paid_channels)} paid channels")
        except Exception as e:
            logger.error(f"Error in check_subscriptions: {e}")
        
        await asyncio.sleep(10)

async def main():
    logger.info("Starting subscription checker")
    scheduler = asyncio.create_task(check_subscriptions())

    logger.info("Starting bot polling")
    await dp.start_polling(bot)

def run_bot():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error running bot: {e}")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--subprocess':

        asyncio.run(main())
    else:

        run_bot() 