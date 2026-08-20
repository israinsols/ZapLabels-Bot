from aiogram import Router, types
from config import Config

router = Router()

@router.callback_query(lambda c: c.data.startswith("country_"))
async def country_selected(callback: types.CallbackQuery):
    country = callback.data.replace("country_", "")
    
    if country == "United Kingdom":
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=f"📦 {carrier}", callback_data=f"carrier_{carrier}")]
            for carrier in Config.UK_CARRIERS
        ])
        await callback.message.edit_text(
            f"🇬🇧 *United Kingdom Selected*\n\nSelect your carrier:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    else:
        pricing = Config.PRICING.get(country, {})
        text = f"🌍 *{country} Selected*\n\n*Available Services:*\n"
        for service, price in pricing.items():
            text += f"• {service}: £{price}\n"
        text += "\nPlease send your label file."
        
        await callback.message.edit_text(text, parse_mode="Markdown")

@router.callback_query(lambda c: c.data.startswith("carrier_"))
async def carrier_selected(callback: types.CallbackQuery):
    carrier = callback.data.replace("carrier_", "")
    
    # UPS ke liye sirf FTID aur LIT
    if carrier == "UPS":
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=f"FTID (£15)", callback_data=f"service_FTID_{carrier}")],
            [types.InlineKeyboardButton(text=f"LIT (£20)", callback_data=f"service_LIT_{carrier}")]
        ])
    else:
        # Baqi carriers ke liye sari services
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=f"FTID (£15)", callback_data=f"service_FTID_{carrier}")],
            [types.InlineKeyboardButton(text=f"LIT (£20)", callback_data=f"service_LIT_{carrier}")],
            [types.InlineKeyboardButton(text=f"RM RTS (£20)", callback_data=f"service_RM_RTS_{carrier}")],
            [types.InlineKeyboardButton(text=f"Receipt (£5)", callback_data=f"service_Receipt_{carrier}")]
        ])
    
    await callback.message.edit_text(
        f"📦 *{carrier} Selected*\n\nSelect service:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )