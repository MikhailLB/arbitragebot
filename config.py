import os
from dotenv import load_dotenv

load_dotenv()


MAIN_BOT_TOKEN = os.getenv('MAIN_BOT_TOKEN')
SUB_BOT_TOKEN = os.getenv('SUB_BOT_TOKEN')
CHANNEL_GETTER_BOT_LINK = 'Channel_getterbot'

DATABASE_NAME = 'arbitrage.db'

ADMIN_USERNAMES = os.getenv('ADMIN_USERNAMES', '').split(',')

    