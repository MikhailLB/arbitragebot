from datetime import datetime, timedelta

import aiosqlite
from config import DATABASE_NAME
import logging

logger = logging.getLogger(__name__)

async def init_db():
    async with aiosqlite.connect(DATABASE_NAME) as db:

        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                role TEXT DEFAULT 'arb',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                ru_link TEXT NOT NULL,
                en_link TEXT NOT NULL,
                channel_id INTEGER NOT NULL,
                paid BOOLEAN DEFAULT FALSE,
                description TEXT DEFAULT '',
                price_subscription INTEGER DEFAULT 0,
                arb_procent INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                channel_id INTEGER,
                language TEXT,
                link TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                description TEXT DEFAULT '',
                short_description TEXT DEFAULT '',
                enter_counter INTEGER DEFAULT 0,
                paid_users INTEGER DEFAULT 0,
                free_users INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (channel_id) REFERENCES channels (id)
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS subscribers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                channel_id INTEGER,
                arbitrage_user_id INTEGER,
                link_id INTEGER,
                subscribed BOOLEAN DEFAULT FALSE,
                subscribed_at TIMESTAMP,
                paid BOOLEAN DEFAULT FALSE,
                paid_subscribed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (channel_id) REFERENCES channels (id),
                FOREIGN KEY (arbitrage_user_id) REFERENCES users (user_id),
                FOREIGN KEY (link_id) REFERENCES links (id)
            )
        ''')

        await db.commit()

async def get_conversion_data(link_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row

        # Получаем общее число пользователей, пришедших через эту ссылку
        await db.execute("PRAGMA foreign_keys = ON;")
        # Считаем всех подписчиков (бесплатных и платных)
        cursor = await db.execute('''
            SELECT COUNT(*) AS total FROM subscribers
            WHERE link_id = ?
        ''', (link_id,))
        total_from_bot = (await cursor.fetchone())['total']

        # Считаем сколько из них подписались на бесплатный канал
        cursor = await db.execute('''
            SELECT COUNT(*) AS free_subs FROM subscribers
            WHERE link_id = ? AND subscribed = TRUE
        ''', (link_id,))
        free_channel_subs = (await cursor.fetchone())['free_subs']

        cursor = await db.execute('''
            SELECT COUNT(*) AS paid_subs FROM subscribers
            WHERE link_id = ? AND paid = TRUE
        ''', (link_id,))
        paid_channel_subs = (await cursor.fetchone())['paid_subs']


        cursor = await db.execute('''
            SELECT c.*, COUNT(s.id) as paid_count
            FROM subscribers s
            JOIN channels c ON s.channel_id = c.id
            WHERE s.link_id = ? AND s.paid = TRUE AND c.paid = TRUE
            GROUP BY c.id
        ''', (link_id,))
        paid_channels = await cursor.fetchall()
        result = []
        for channel in paid_channels:
            # Конверсии
            conv1 = (free_channel_subs / total_from_bot * 100) if total_from_bot else 0
            conv2 = (channel['paid_count'] / free_channel_subs * 100) if free_channel_subs else 0
            conv_total = (channel['paid_count'] / total_from_bot * 100) if total_from_bot else 0

            price = float(channel['price_subscription'])
            procent = float(channel['arb_procent'])
            print(price, procent)
            owner_income = price * procent / 100

            text = (
                f"<b>{channel['name']}</b>\n"
                f"📈 <b>Конверсия:</b>\n"
                f"• Бот → Бесплатный канал: <b>{conv1:.2f}%</b>\n"
                f"• Бесплатный → Платный канал: <b>{conv2:.2f}%</b>\n"
                f"• Бот → Платный (итоговая): <b>{conv_total:.2f}%</b>\n\n"
                f"💰 <b>Цена подписки:</b> {price} руб\n"
                f"🎯 <b>Ваш процент от продаж:</b> {procent}%\n"
                f"💵 <b>Ваш доход с одной подписки:</b> {owner_income:.2f} руб\n"
            )

            result.append(text)

        return result


async def register_user(user_id: int, username: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('''
            INSERT OR IGNORE INTO users (user_id, username, role)
            VALUES (?, ?, 'arb')
        ''', (user_id, username))
        await db.commit()

async def get_channels(include_paid: bool = False):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        if include_paid:
            async with db.execute('SELECT * FROM channels') as cursor:
                return await cursor.fetchall()
        else:
            async with db.execute('SELECT * FROM channels WHERE paid = 0') as cursor:
                return await cursor.fetchall()

async def create_link(user_id: int, channel_id: int, language: str, link: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('''
            INSERT INTO links (user_id, channel_id, language, link)
            VALUES (?, ?, ?, ?)
        ''', (user_id, channel_id, language, link))
        await db.commit()
        return cursor.lastrowid
async def update_link(link_id: int, new_link: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('''
            UPDATE links
            SET link = ?
            WHERE id = ?
        ''', (new_link, link_id))
        await db.commit()


async def get_user_stats(user_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute('''
            SELECT l.link, c.name, 
                   COUNT(DISTINCT s.id) as total_subscribers,
                   COUNT(DISTINCT CASE WHEN s.paid = 1 THEN s.id END) as paid_subscribers
            FROM links l
            JOIN channels c ON l.channel_id = c.id
            LEFT JOIN subscribers s ON l.id = s.link_id
            WHERE l.user_id = ?
            GROUP BY l.id
        ''', (user_id,)) as cursor:
            return await cursor.fetchall()

async def get_link_stats(link_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute('''
            SELECT l.enter_counter, l.paid_users, l.free_users
            FROM links l
            WHERE l.id = ?
        ''', (link_id,)) as cursor:
            return await cursor.fetchall()

async def register_subscriber(user_id: int, channel_id: int, arbitrage_user_id: str, link_id: int) -> None:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute('''
            SELECT id FROM subscribers 
            WHERE user_id = ? AND channel_id = ?
        ''', (user_id, channel_id)) as cursor:
            existing = await cursor.fetchone()
            
        if existing:
            logger.info(f"Subscription already exists for user {user_id} in channel {channel_id}")
            return

        await db.execute('''
            INSERT INTO subscribers (user_id, channel_id, arbitrage_user_id, link_id, subscribed)
            VALUES (?, ?, ?, ?, 0)
        ''', (user_id, channel_id, arbitrage_user_id, link_id))
        await db.commit()
        logger.info(f"New subscription registered for user {user_id} in channel {channel_id}")

async def update_subscriber_status(user_id: int, channel_id: int, subscribed: bool):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('''
            UPDATE subscribers 
            SET subscribed = ?, subscribed_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND channel_id = ? AND subscribed = 0
        ''', (subscribed, user_id, channel_id))
        await db.commit()

async def update_subscriber_paid_status(user_id: int, channel_id: int, is_paid: bool) -> None:
    """
    Обновляет статус платной подписки пользователя
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        if is_paid:
            await db.execute('''
                UPDATE subscribers 
                SET paid = 1, paid_subscribed_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND channel_id = ?
            ''', (user_id, channel_id))
        else:
            await db.execute('''
                UPDATE subscribers 
                SET paid = 0, paid_subscribed_at = NULL
                WHERE user_id = ? AND channel_id = ?
            ''', (user_id, channel_id))
        await db.commit()

async def add_channel(name: str, ru_link: str, en_link: str, channel_id: int, description: str, price_subscription: int, arb_procent: int, paid: bool = False):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('''
            INSERT INTO channels (name, ru_link, en_link, channel_id, description, price_subscription, arb_procent, paid)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, ru_link, en_link, channel_id, description, price_subscription, arb_procent, paid))
        await db.commit()


async def delete_channel(channel_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('DELETE FROM links WHERE channel_id = ?', (channel_id,))
        await db.execute('DELETE FROM subscribers WHERE channel_id = ?', (channel_id,))
        await db.execute('DELETE FROM channels WHERE id = ?', (channel_id,))
        await db.commit()

async def update_channel_adm(channel_id, name, ru_link, en_link, tg_channel_id, paid, description, price_subscription, arb_procent):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "UPDATE channels SET name = ?, ru_link = ?, en_link = ?, channel_id = ?, paid = ?, description = ?, price_subscription = ?, arb_procent = ? WHERE id = ?",
            (name, ru_link, en_link, tg_channel_id, paid, description, price_subscription, arb_procent, channel_id)
        )
        await db.commit()

async def update_channel(channel_id: int, name: str, ru_link: str, en_link: str, paid: bool = None):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        if paid is not None:
            await db.execute('''
                UPDATE channels 
                SET name = ?, ru_link = ?, en_link = ?, paid = ?
                WHERE id = ?
            ''', (name, ru_link, en_link, paid, channel_id))
        else:
            await db.execute('''
                UPDATE channels 
                SET name = ?, ru_link = ?, en_link = ?
                WHERE id = ?
            ''', (name, ru_link, en_link, channel_id))
        await db.commit()

async def get_channel(channel_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute('SELECT * FROM channels WHERE id = ?', (channel_id,)) as cursor:
            return await cursor.fetchone()

async def get_link(link_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute('SELECT * FROM links WHERE id = ?', (link_id,)) as cursor:
            return await cursor.fetchone()
async def get_subscriber(id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute('SELECT * FROM subscribers WHERE id = ?', (id,)) as cursor:
            return await cursor.fetchone()

async def delete_link(link: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('DELETE FROM links WHERE id = ?', (link,))
        await db.commit()


async def get_links(user_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute('SELECT * FROM links WHERE user_id = ?', (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return rows

async def get_users():
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute('SELECT user_id FROM users') as cursor:
            rows = await cursor.fetchall()
            return rows

async def get_user(username: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute('SELECT user_id FROM users WHERE username = ?', (username, )) as cursor:
            row = await cursor.fetchone()
            return row

async def paid_sub_counter(channel: int) -> int:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            'SELECT COUNT(id) FROM subscribers WHERE channel_id = ? AND paid = 1',
            (channel,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0
async def free_sub_counter(channel: int) -> int:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            'SELECT COUNT(id) FROM subscribers WHERE channel_id = ? AND subscribed = 1',
            (channel,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def arb_counter(channel: int) -> int:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            'SELECT COUNT(DISTINCT user_id) FROM subscribers WHERE channel_id = ? AND subscribed = 1',
            (channel,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def get_user_stats_ever(user_id: int) -> tuple[int, int, int]:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            '''
            SELECT 
                SUM(paid_users) AS paid_count,
                SUM(free_users) AS free_count,
                COUNT(link) AS links_count
            FROM links
            WHERE user_id = ?
            ''',
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                paid_count = row[0] or 0
                free_count = row[1] or 0
                links_count = row[2] or 0
                return paid_count, free_count, links_count
            return 0, 0, 0

async def get_month_profit(user_id: int) -> tuple[int, int, float]:
    one_month_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()

    async with aiosqlite.connect(DATABASE_NAME) as db:

        async with db.execute(
            "SELECT id FROM links WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            link_rows = await cursor.fetchall()
            link_ids = [row[0] for row in link_rows]

        if not link_ids:
            return 0, 0, 0.0

        placeholders = ','.join(['?'] * len(link_ids))

        query = f"""
        SELECT 
            s.paid,
            s.channel_id,
            c.price_subscription,
            c.arb_procent
        FROM subscribers s
        JOIN channels c ON s.channel_id = c.id
        WHERE s.link_id IN ({placeholders})
        AND s.subscribed = 1
        AND s.created_at >= ?
        """

        async with db.execute(query, (*link_ids, one_month_ago)) as cursor:
            paid_count = 0
            free_count = 0
            total_profit = 0.0

            async for paid, channel_id, price, percent in cursor:
                if paid:
                    paid_count += 1
                    profit = (price * percent) / 100
                    total_profit += profit
                    free_count += 1
                else:
                    free_count += 1

        return paid_count, free_count, total_profit
async def get_month_profit_by_username(username: str) -> tuple[int, int, float]:
    one_month_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()

    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row

        # Получаем user_id по username
        cursor = await db.execute(
            "SELECT user_id FROM users WHERE username = ?",
            (username,)
        )
        user = await cursor.fetchone()
        if not user:
            return 0, 0, 0.0

        user_id = user['user_id']

        # Все ссылки пользователя
        cursor = await db.execute(
            "SELECT id FROM links WHERE user_id = ?",
            (user_id,)
        )
        link_rows = await cursor.fetchall()
        link_ids = [row['id'] for row in link_rows]

        if not link_ids:
            return 0, 0, 0.0

        placeholders = ','.join(['?'] * len(link_ids))
        query = f"""
        SELECT 
            s.paid,
            c.price_subscription,
            c.arb_procent
        FROM subscribers s
        JOIN channels c ON s.channel_id = c.id
        WHERE s.link_id IN ({placeholders})
        AND s.subscribed = 1
        AND s.created_at >= ?
        """

        cursor = await db.execute(query, (*link_ids, one_month_ago))
        paid_count = 0
        free_count = 0
        total_profit = 0.0

        async for row in cursor:
            paid = row[0]
            price = int(row[1])
            percent = int(row[2])
            if paid:
                paid_count += 1
                total_profit += (price * percent) / 100
                free_count += 1
            else:
                free_count += 1

        return paid_count, free_count, total_profit


async def change_link(link_id: int, new_desc: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "UPDATE links SET description = ? WHERE id = ?",
            (new_desc, link_id)
        )
        await db.commit()

async def change_short_desc_link(link_id: int, new_desc: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "UPDATE links SET short_description = ? WHERE id = ?",
            (new_desc, link_id)
        )
        await db.commit()

async def get_admin_statistics():
    async with aiosqlite.connect(DATABASE_NAME) as db:

        month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

        cursor = await db.execute("""
            SELECT COUNT(*) 
            FROM subscribers 
            WHERE paid = 1 
            AND paid_subscribed_at >= ?
        """, (month_ago,))
        paid_count = (await cursor.fetchone())[0]


        cursor = await db.execute("""
            SELECT arbitrage_user_id, COUNT(*) as paid_subs
            FROM subscribers
            WHERE paid = 1 AND paid_subscribed_at >= ?
            GROUP BY arbitrage_user_id
            ORDER BY paid_subs DESC
            LIMIT 5;
        """, (month_ago,))
        top_arbitrage = await cursor.fetchall()

        return paid_count, top_arbitrage