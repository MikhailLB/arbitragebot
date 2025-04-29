import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import MAIN_BOT_TOKEN, ADMIN_USERNAMES, CHANNEL_GETTER_BOT_LINK
import database as db
from keyboards import *


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


bot = Bot(token=MAIN_BOT_TOKEN)
dp = Dispatcher()
class ChangeLinkShortDesc(StatesGroup):
    waiting_for_description = State()

class ChangeLinkDesc(StatesGroup):
    waiting_for_description = State()

class AdminStats(StatesGroup):
    waiting_for_username = State()

class AdminLinkStats(StatesGroup):
    waiting_for_username_l = State()
class AdminStates(StatesGroup):
    add_channel_name = State()
    add_channel_ru_link = State()
    add_channel_en_link = State()
    add_channel_id = State()
    add_channel_paid = State()
    add_sub_cost = State()
    add_percent_for_arb = State()
    add_description = State()
class EditChannelState(StatesGroup):
    waiting_for_data = State()
@dp.message(Command("start"))
async def start(message: types.Message):
    user = message.from_user
    await db.register_user(user.id, user.username)
    
    keyboard = [
        [InlineKeyboardButton(text="Сгенерировать ссылку", callback_data="select_channel")],
        [InlineKeyboardButton(text="Мои ссылки", callback_data="my_links")],
        [InlineKeyboardButton(text="Моя статистика", callback_data="my_stats")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await message.answer(
        f"Привет, {user.first_name}! Я бот для арбитража. Выберите действие:",
        reply_markup=reply_markup
    )


@dp.callback_query(F.data == "my_links")
async def select_link(callback: types.CallbackQuery):
    links = await db.get_links(user_id=callback.from_user.id)
    if not links:
        await callback.message.edit_text("У вас нет достуных ссылок!", reply_markup=back_kb)
        await callback.answer()
        return

    keyboard = []
    for link in links:
        arbitrage_username, channel_id, link_id = link[4].split('-')
        channel = await db.get_channel(channel_id)
        keyboard.append([InlineKeyboardButton(
            text=channel[1] + " " + link[3] + " " + link[7],
            callback_data=f"link_{link[0]}"
        )])
    keyboard.append([InlineKeyboardButton(
        text="👈🏽 Назад",
        callback_data=f"back"
    )])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(
        "Выберите ссылку:",
        reply_markup=reply_markup
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("link_"))
async def link_selected(callback: types.CallbackQuery):
    try:
        link_id = int(callback.data.split("_")[1])
        link = await db.get_link(link_id=link_id)
        stats = await db.get_link_stats(link_id)
        if not stats:
            keyboard = [[InlineKeyboardButton(text="Выбрать канал", callback_data="select_channel")]]
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            await callback.message.edit_text(
                text="У вас пока нет активных ссылок. Выберите канал, чтобы создать первую ссылку.",
                reply_markup=reply_markup
            )
            await callback.answer()
            return
        channel = await db.get_channel(link[2])
        keyboard = []
        clicks = stats[0][0]
        paid = stats[0][1]
        free = stats[0][2]
        conv_total = (paid / clicks * 100) if clicks else 0
        conv1 = (free / clicks * 100) if clicks else 0
        conv2 = (paid / free * 100) if free else 0
        price = channel[7] if channel[7] != "" else 0
        percent = channel[8] if channel[8] != "" else 0
        owner_income = (price * percent) / 100
        text = (
            "📊 <b>Ваша статистика по ссылке</b>\n\n"
            f"📝 <b>Краткое описание:</b> {link[7]}\n\n"
            f"🔗 <b>Ссылка:</b> {link[4]}\n"
            f"📝 <b>Описание:</b> {link[6]}\n\n"

            f"👥 <b>Всего переходов:</b> {clicks}\n"
            f"🆓 <b>Подписчиков на бесплатный канал:</b> {free}\n"
            f"💳 <b>Платных подписчиков:</b> {paid}\n\n"
        
            f"📈 <b>Конверсия:</b>\n"
            f"• Бот → Бесплатный канал: <b>{conv1:.2f}%</b>\n"
            f"• Бесплатный → Платный канал: <b>{conv2:.2f}%</b>\n\n"
            f"• Бот → Платный (итоговая): <b>{conv_total:.2f}%</b>\n\n"
            f"💰 <b>Цена подписки:</b> {channel[7]} руб\n"
            f"🎯 <b>Ваш процент от продаж:</b> {channel[8]}%\n"
            f"💵 <b>Ваш доход с одной подписки:</b> {owner_income:.2f} руб\n"
            f"💵 <b>Ваш приблизительный доход с ссылки</b> {owner_income*paid:.2f} руб\n"
        )

        keyboard.append([InlineKeyboardButton(
            text=f"❌ Удалить ссылку",
            callback_data=f"delete_link_{link_id}"
        )])
        keyboard.append([InlineKeyboardButton(
            text=f"✅ Изменить описание",
            callback_data=f"changedesc_{link_id}"
        )])
        keyboard.append([InlineKeyboardButton(
            text=f"🖌 Изменить краткое описание",
            callback_data=f"changeshortdesc_{link_id}"
        )])
        keyboard.append([InlineKeyboardButton(text="🔄Обновить статистику", callback_data=f"link_{link_id}")])
        keyboard.append([InlineKeyboardButton(text="👈🏽Назад", callback_data=f"back")])
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        await callback.message.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        await callback.answer("")
    except:
        await callback.answer("Статистика обновлена")

@dp.callback_query(F.data == "select_channel")
async def select_channel(callback: types.CallbackQuery):
    channels = await db.get_channels(include_paid=False)
    if not channels:
        await callback.message.edit_text("Нет доступных каналов.")
        await callback.answer()
        return
    
    keyboard = []
    for channel in channels:
        keyboard.append([InlineKeyboardButton(
            text=channel[1],
            callback_data=f"channel_{channel[0]}"
        )])
    keyboard.append([InlineKeyboardButton(
        text="👈🏽 Назад",
        callback_data=f"back"
    )])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(
        "Выберите канал:",
        reply_markup=reply_markup
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("channel_"))
async def channel_selected(callback: types.CallbackQuery):
    channel_id = int(callback.data.split("_")[1])
    keyboard = [
        [InlineKeyboardButton(text="Русский", callback_data=f"lang_ru_{channel_id}")],
        [InlineKeyboardButton(text="English", callback_data=f"lang_en_{channel_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        text="Выберите язык канала:",
        reply_markup=reply_markup
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("back"))
async def channel_selected(callback: types.CallbackQuery, state: FSMContext):
    keyboard = [
        [InlineKeyboardButton(text="Сгенерировать ссылку", callback_data="select_channel")],
        [InlineKeyboardButton(text="Мои ссылки", callback_data="my_links")],
        [InlineKeyboardButton(text="Моя статистика", callback_data="my_stats")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await callback.message.edit_text(
        f"Выберите действие:",
        reply_markup=reply_markup
    )
@dp.callback_query(F.data.startswith("changeshortdesc_"))
async def channel_selected(callback: types.CallbackQuery, state: FSMContext):
    link_id = int(callback.data.split("_")[1])
    await state.update_data(link_id=link_id)
    await callback.message.answer("Введите новое короткое описание: \n\nОно будет поставляться к названию ссылки, чтобы облегчить распознавание нужной")
    await state.set_state(ChangeLinkShortDesc.waiting_for_description)
    await callback.answer()

@dp.message(ChangeLinkShortDesc.waiting_for_description)
async def process_description_input(message: types.Message, state: FSMContext):
    data = await state.get_data()
    link_id = data["link_id"]
    new_description = message.text

    await db.change_short_desc_link(link_id, new_description)

    await message.answer("Описание успешно обновлено ✅", reply_markup=back_kb)
    await state.clear()

@dp.callback_query(F.data.startswith("changedesc_"))
async def channel_selected(callback: types.CallbackQuery, state: FSMContext):
    link_id = int(callback.data.split("_")[1])
    await state.update_data(link_id=link_id)
    await callback.message.answer("Введите новое описание ссылки:")
    await state.set_state(ChangeLinkDesc.waiting_for_description)
    await callback.answer()

@dp.message(ChangeLinkDesc.waiting_for_description)
async def process_description_input(message: types.Message, state: FSMContext):
    data = await state.get_data()
    link_id = data["link_id"]
    new_description = message.text

    await db.change_link(link_id, new_description)

    await message.answer("Описание успешно обновлено ✅", reply_markup=back_kb)
    await state.clear()

@dp.callback_query(F.data.startswith("lang_"))
async def language_selected(callback: types.CallbackQuery):
    _, lang, channel_id = callback.data.split("_")
    channel_id = int(channel_id)
    channel = await db.get_channel(channel_id)

    temp_link = ""
    id = await db.create_link(callback.from_user.id, channel_id, lang, temp_link)

    link = f"https://t.me/{CHANNEL_GETTER_BOT_LINK}?start={callback.from_user.username}-{channel_id}-{id}"
    await db.update_link(id, link)
    keyboard = [[InlineKeyboardButton(text="Выбрать канал", callback_data="select_channel")]]
    keyboard.append([InlineKeyboardButton(
        text="👈🏽 Назад",
        callback_data=f"back"
    )])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        text=f"Ваша ссылка для канала {channel[1]}:\n{link}\n\n"
             f"Вы можете создать новую ссылку, выбрав другой канал.",
        reply_markup=reply_markup
    )
    await callback.answer()

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    user = message.from_user
    if user.username not in ADMIN_USERNAMES:
        await message.answer("У вас нет доступа к админ-панели.")
        return
    
    keyboard = [
        [InlineKeyboardButton(text="Добавить бесплатный канал", callback_data="admin_add_free_channel")],
        [InlineKeyboardButton(text="Добавить платный канал", callback_data="admin_add_paid_channel")],
        [InlineKeyboardButton(text="Удалить канал", callback_data="admin_delete_channel")],
        [InlineKeyboardButton(text="Список каналов", callback_data="admin_list_channels")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📊 Статистика пользователей", callback_data="user_stats")],
        [InlineKeyboardButton(text="📊 Статистика ссылок пользователей", callback_data="users_link_stats")],
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await message.answer(
        "Админ-панель. Выберите действие:",
        reply_markup=reply_markup
    )

@dp.callback_query(F.data.startswith("admin_add_"))
async def admin_add_channel_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.username not in ADMIN_USERNAMES:
        await callback.message.edit_text("У вас нет доступа к этой функции.")
        await callback.answer()
        return
    
    is_paid = callback.data == "admin_add_paid_channel"
    await state.update_data(is_paid=is_paid)
    await callback.message.edit_text("Введите название канала:")
    await state.set_state(AdminStates.add_channel_name)
    await callback.answer()

@dp.message(AdminStates.add_channel_name)
async def add_channel_name(message: types.Message, state: FSMContext):
    await state.update_data(channel_name=message.text)
    await message.answer("Введите ссылку на русскую версию канала:")
    await state.set_state(AdminStates.add_channel_ru_link)

@dp.message(AdminStates.add_channel_ru_link)
async def add_channel_ru_link(message: types.Message, state: FSMContext):
    await state.update_data(channel_ru_link=message.text)
    await message.answer("Введите ссылку на английскую версию канала:")
    await state.set_state(AdminStates.add_channel_en_link)

@dp.message(AdminStates.add_channel_en_link)
async def add_channel_ru_link(message: types.Message, state: FSMContext):
    await state.update_data(channel_en_link=message.text)
    await message.answer("Введите цену подписки на канал в рублях:")
    await state.set_state(AdminStates.add_sub_cost)

@dp.message(AdminStates.add_sub_cost)
async def add_channel_ru_link(message: types.Message, state: FSMContext):
    await state.update_data(add_sub_cost=message.text)
    await message.answer("Введите процент арбитражника:")
    await state.set_state(AdminStates.add_percent_for_arb)

@dp.message(AdminStates.add_percent_for_arb)
async def add_channel_ru_link(message: types.Message, state: FSMContext):
    await state.update_data(add_percent_for_arb=message.text)
    await message.answer("Введите описание канала\nЕсли не хотите оставлять описание введите: '-' (прочерк) ")
    await state.set_state(AdminStates.add_description)

@dp.message(AdminStates.add_description)
async def add_channel_ru_link(message: types.Message, state: FSMContext):
    if message.text == "-":
        await state.update_data(add_description="")
    else:
        await state.update_data(add_description=message.text)
    await message.answer("Введите channel id\n(перешлите любое сообщение из канала\nв этого бота: @LeadConverterToolkitBot:\n\nПример id: -1002560474274")
    await state.set_state(AdminStates.add_channel_id)

@dp.message(AdminStates.add_channel_id)
async def add_channel_id(message: types.Message, state: FSMContext):
    try:
        channel_id = int(message.text)
        data = await state.get_data()
        is_paid = data.get('is_paid', False)
        
        await db.add_channel(
            data['channel_name'],
            data['channel_ru_link'],
            data['channel_en_link'],
            channel_id,
            data['add_description'],
            data['add_sub_cost'],
            data['add_percent_for_arb'],
            paid=is_paid
        )
        
        keyboard = [[InlineKeyboardButton(text="Назад в админ-панель", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await message.answer(
            f"Канал '{data['channel_name']}' успешно добавлен!",
            reply_markup=reply_markup
        )
        await state.clear()
    except ValueError:
        await message.answer("Пожалуйста, введите корректный ID канала (число)")

@dp.callback_query(F.data == "admin_delete_channel")
async def admin_delete_channel(callback: types.CallbackQuery):
    if callback.from_user.username not in ADMIN_USERNAMES:
        await callback.message.edit_text("У вас нет доступа к этой функции.")
        await callback.answer()
        return
    
    channels = await db.get_channels(include_paid=True)
    if not channels:
        await callback.message.edit_text("Нет доступных каналов для удаления.")
        await callback.answer()
        return
    
    keyboard = []
    for channel in channels:
        keyboard.append([InlineKeyboardButton(
            text="💵 Платный " + channel[1] if channel[5] else "📜 Бесплатный " + channel[1],
            callback_data=f"delete_channel_{channel[0]}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="Назад", callback_data="admin_back")])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        "Выберите канал для удаления:",
        reply_markup=reply_markup
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("delete_channel_"))
async def delete_channel_confirm(callback: types.CallbackQuery):
    if callback.from_user.username not in ADMIN_USERNAMES:
        await callback.message.edit_text("У вас нет доступа к этой функции.")
        await callback.answer()
        return
    
    channel_id = int(callback.data.split("_")[2])
    channel = await db.get_channel(channel_id)
    if not channel:
        await callback.message.edit_text("Канал не найден.")
        await callback.answer()
        return
    
    keyboard = [
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_channel_{channel_id}"),
            InlineKeyboardButton(text="❌ Нет, отмена", callback_data="admin_back")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        f"Вы действительно хотите удалить канал '{channel[1]}'?",
        reply_markup=reply_markup
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_delete_channel_"))
async def delete_channel(callback: types.CallbackQuery):
    if callback.from_user.username not in ADMIN_USERNAMES:
        await callback.message.edit_text("У вас нет доступа к этой функции.")
        await callback.answer()
        return
    
    channel_id = int(callback.data.split("_")[3])
    try:
        await db.delete_channel(channel_id)
        await callback.answer("Канал успешно удален!")

        await admin_list_channels(callback)
    except Exception as e:
        logger.error(f"Error deleting channel: {e}")
        await callback.answer("Произошла ошибка при удалении канала")

@dp.callback_query(F.data == "admin_list_channels")
async def admin_list_channels(callback: types.CallbackQuery):
    if callback.from_user.username not in ADMIN_USERNAMES:
        await callback.message.edit_text("У вас нет доступа к этой функции.")
        await callback.answer()
        return
    
    channels = await db.get_channels(include_paid=True)
    text = "Список каналов:\n\n"

    keyboard = []
    for channel in channels:
        keyboard.append([InlineKeyboardButton(
            text="💵 Платный " + channel[1] if channel[5] else "📜 Бесплатный " + channel[1],
            callback_data=f"channeladm_{channel[0]}"
        )])

    keyboard.append([InlineKeyboardButton(text="Назад", callback_data="admin_back")])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(text=text, reply_markup=reply_markup)
    await callback.answer()


@dp.callback_query(F.data.startswith("channeladm_"))
async def view_channel_info(callback: types.CallbackQuery):
    try:
        channel_id = int(callback.data.split("_")[1])
        channel = await db.get_channel(channel_id)
        paid_sub_counter = await db.paid_sub_counter(channel_id)
        free_sub_counter = await db.free_sub_counter(channel_id)
        arb_counter = await db.arb_counter(channel_id)

        text = (
            "📢 <b>Информация о канале</b>\n\n"
            f"📛 <b>Название:</b> {channel[1]}\n"
            f"🇷🇺 <b>RU ссылка:</b> {channel[2]}\n"
            f"🇬🇧 <b>EN ссылка:</b> {channel[3]}\n"
            f"🛰️ <b>Channel ID:</b> {channel[4]}\n"
            f"💰 <b>Платный канал:</b> {'Да' if channel[5] == 1 else 'Нет'}\n"
            f"📝 <b>Описание:</b> {channel[6] or '—'}\n"
            f"💸 <b>Цена подписки:</b> {channel[7]} руб\n"
            f"🎯 <b>Процент арбитража:</b> {channel[8]}%\n"
            f"🕰️ <b>Дата создания:</b> {channel[9]}\n\n"

            "📊 <b>Статистика</b>\n"
            f"👥 <b>Платных подписчиков:</b> {paid_sub_counter}\n"
            f"🙌 <b>Бесплатных подписчиков:</b> {free_sub_counter}\n"
            f"⚖️ <b>Количество арбитражников:</b> {arb_counter}"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить данные", callback_data=f"editchannel_{channel[0]}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
        ])

        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        print(e)
        await callback.answer("Ошибка при загрузке данных")

@dp.callback_query(F.data.startswith("editchannel_"))
async def start_edit_channel(callback: types.CallbackQuery, state: FSMContext):
    channel_id = int(callback.data.split("_")[1])
    await state.set_state(EditChannelState.waiting_for_data)
    await state.update_data(channel_id=channel_id)

    await callback.message.edit_text(
        "✏️ Введите новые данные канала через '|':\n\n"
        "<code>Название | RU ссылка | EN ссылка | Channel ID | Платный (0/1) | Описание | Цена | Процент</code>\n\n"
        "Пример:\n"
        "<code>MyChannel | https://t.me/ru | https://t.me/en | -100123456789 | 1 | Мой канал | 999 | 30</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(EditChannelState.waiting_for_data)
async def save_channel_data(message: types.Message, state: FSMContext):
    data = await state.get_data()
    channel_id = data["channel_id"]

    try:
        parts = [p.strip() for p in message.text.split("|")]
        if len(parts) != 8:
            await message.answer("❌ Убедитесь, что вы указали 8 параметров, разделённых '|'.")
            return

        name, ru_link, en_link, tg_channel_id, paid, description, price, procent = parts

        await db.update_channel_adm(
            channel_id=channel_id,
            name=name,
            ru_link=ru_link,
            en_link=en_link,
            tg_channel_id=int(tg_channel_id),
            paid=int(paid),
            description=description,
            price_subscription=int(price),
            arb_procent=int(procent)
        )

        await message.answer("✅ Данные канала успешно обновлены!")
        await state.clear()

    except Exception as e:
        print(e)
        await message.answer("❌ Ошибка при обновлении. Проверьте формат данных.")


@dp.callback_query(F.data == "admin_cancel")
async def admin_cancel(callback: types.CallbackQuery):
    if callback.from_user.username not in ADMIN_USERNAMES:
        await callback.message.edit_text("У вас нет доступа к этой функции.")
        await callback.answer()
        return
    
    keyboard = [
        [InlineKeyboardButton(text="Добавить бесплатный канал", callback_data="admin_add_free_channel")],
        [InlineKeyboardButton(text="Добавить платный канал", callback_data="admin_add_paid_channel")],
        [InlineKeyboardButton(text="Удалить канал", callback_data="admin_delete_channel")],
        [InlineKeyboardButton(text="Список каналов", callback_data="admin_list_channels")],
        [InlineKeyboardButton(text="📊 Статистика пользователей", callback_data="user_stats")],
        [InlineKeyboardButton(text="📊 Статистика ссылок пользователей", callback_data="users_link_stats")],

    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        text="Админ-панель. Выберите действие:",
        reply_markup=reply_markup
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: types.CallbackQuery):
    if callback.from_user.username not in ADMIN_USERNAMES:
        await callback.message.edit_text("У вас нет доступа к этой функции.")
        await callback.answer()
        return
    
    keyboard = [
        [InlineKeyboardButton(text="Добавить бесплатный канал", callback_data="admin_add_free_channel")],
        [InlineKeyboardButton(text="Добавить платный канал", callback_data="admin_add_paid_channel")],
        [InlineKeyboardButton(text="Удалить канал", callback_data="admin_delete_channel")],
        [InlineKeyboardButton(text="Список каналов", callback_data="admin_list_channels")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📊 Статистика пользователей", callback_data="user_stats")],
        [InlineKeyboardButton(text="📊 Статистика ссылок пользователей", callback_data="users_link_stats")],
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        text="Админ-панель. Выберите действие:",
        reply_markup=reply_markup
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("delete_link_"))
async def delete_link_confirm(callback: types.CallbackQuery):
    link = callback.data.replace("delete_link_", "")
    keyboard = [
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{link}"),
            InlineKeyboardButton(text="❌ Нет, отмена", callback_data="back")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        f"Вы действительно хотите удалить ссылку {link}?",
        reply_markup=reply_markup
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_delete_"))
async def delete_link(callback: types.CallbackQuery):
    link = callback.data.replace("confirm_delete_", "")
    print(link)
    try:
        await db.delete_link(link)
        await callback.message.edit_text("Ссылка успешно удалена!", reply_markup=back_kb)

    except Exception as e:
        logger.error(f"Error deleting link: {e}")
        await callback.answer("Произошла ошибка при удалении ссылки")

@dp.callback_query(F.data == "admin_stats")
async def show_stats(callback: types.CallbackQuery):
    if callback.from_user.username not in ADMIN_USERNAMES:
        await callback.message.edit_text("У вас нет прав для просмотра статистики.")
        await callback.answer()
        return

    try:
        paid_count, top_arbitrage = await db.get_admin_statistics()


        stats_text = "📊 Статистика:\n\n"
        stats_text += f"💰 Платных подписчиков за последний месяц: {paid_count}\n\n"
        stats_text += "🏆 Топ 5 арбитражников:\n"
        
        for i, (username, count) in enumerate(top_arbitrage, 1):
            stats_text += f"{i}. @{username}: {count} подписчиков\n"

        keyboard = [[InlineKeyboardButton(text="Назад", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await callback.message.edit_text(stats_text, reply_markup=reply_markup)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error showing stats: {e}")
        await callback.message.edit_text("Произошла ошибка при получении статистики.")
        await callback.answer()



@dp.callback_query(F.data == "user_stats")
async def ask_username(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.username not in ADMIN_USERNAMES:
        await callback.message.edit_text("У вас нет прав для просмотра статистики.")
        await callback.answer()
        return

    await callback.message.answer("Введите username арбитражника (без @):")
    await state.set_state(AdminStats.waiting_for_username)
    await callback.answer()


@dp.message(AdminStats.waiting_for_username)
async def process_username(message: types.Message, state: FSMContext):
    username = message.text.strip().lstrip("@")

    try:
        paid, free, profit = await db.get_month_profit_by_username(username)
        text = (
            f"📊 <b>Статистика по @{username} за последний месяц</b>\n\n"
            f"💳 <b>Платных подписок:</b> {paid}\n"
            f"🆓 <b>Бесплатных подписок:</b> {free}\n"
            f"💵 <b>Доход:</b> {profit:.2f} руб"
        )

        keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        await message.answer(text, reply_markup=reply_markup, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Ошибка получения статистики для @{username}: {e}")
        await message.answer("Не удалось получить статистику. Проверьте username.")

    await state.clear()




@dp.callback_query(F.data == "my_stats")
async def my_stats(callback: types.CallbackQuery):
    try:
        paid_all, free_all, links_count = await db.get_user_stats_ever(callback.from_user.id)
        paid_month, free_month, profit_month = await db.get_month_profit(callback.from_user.id)

        text = (
            "📊 <b>Ваша общая статистика</b>\n\n"
            f"🔗 <b>Всего создано ссылок:</b> {links_count}\n"
            f"💳 <b>Всего платных подписчиков:</b> {paid_all}\n"
            f"🆓 <b>Всего бесплатных подписчиков:</b> {free_all}\n\n"

            "📅 <b>Статистика за последний месяц</b>\n\n"
            f"💳 <b>Платных подписчиков:</b> {paid_month}\n"
            f"🆓 <b>Бесплатных подписчиков:</b> {free_month}\n"
            f"💵 <b>Доход за месяц:</b> {profit_month:.2f} руб\n"
        )

        keyboard = [
            [InlineKeyboardButton(text="📎 Мои ссылки", callback_data="my_links")],
            [InlineKeyboardButton(text="👈🏽 Назад", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        await callback.message.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        await callback.answer("")
    except Exception as e:
        print("Ошибка в my_stats:", e)
        await callback.answer("Ошибка при получении статистики.")

@dp.callback_query(F.data == "users_link_stats")
async def ask_username(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.username not in ADMIN_USERNAMES:
        await callback.message.edit_text("У вас нет прав для просмотра статистики.")
        await callback.answer()
        return

    await callback.message.answer("Введите username арбитражника (без @):")
    await state.set_state(AdminLinkStats.waiting_for_username_l)
    await callback.answer()

@dp.message(AdminLinkStats.waiting_for_username_l)
async def admin_links_stats(message: types.Message, state: FSMContext):
    try:
        username = message.text.strip().lstrip("@")
        user = await db.get_user(username)
        user_id = user[0]
        links = await db.get_links(user_id=user_id)
        if not links:
            await message.answer("У вас нет достуных ссылок!", reply_markup=back_kb)
            return

        keyboard = []
        for link in links:
            arbitrage_username, channel_id, link_id = link[4].split('-')
            channel = await db.get_channel(channel_id)
            keyboard.append([InlineKeyboardButton(
                text=channel[1] + " " + link[3] + " " + link[7],
                callback_data=f"link_{link[0]}"
            )])
        keyboard.append([InlineKeyboardButton(
            text="👈🏽 Назад",
            callback_data=f"back"
        )])
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer(
            "Выберите ссылку:",
            reply_markup=reply_markup
        )
    except Exception as e:
        print("Ошибка в my_stats:", e)
        await message.answer("Ошибка при получении статистики.")
    await state.clear()

async def main():
    await db.init_db()

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