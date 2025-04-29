from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

back_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="back")
        ]
    ]
)