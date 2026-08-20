from aiogram import Router, types
from aiogram.filters import Command

router = Router()

COUNTRIES = {
    "United Kingdom": "🇬🇧",
    "USA": "🇺🇸",
    "Spain": "🇪🇸",
    "Germany": "🇩🇪",
    "Italy": "🇮🇹",
    "France": "🇫🇷"
}

@router.message(Command("start"))
async def start_command(message: types.Message):
    welcome = """
🚀 *Welcome to ZapLabels!*

We support almost every country worldwide. Our services help you move faster and make more money.

*Select your country to continue:*
    """
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=f"{flag} {country}", callback_data=f"country_{country}")]
        for country, flag in COUNTRIES.items()
    ])
    
    await message.answer(welcome, reply_markup=keyboard, parse_mode="Markdown")