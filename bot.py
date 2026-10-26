import asyncio
import logging
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile
from config import Config
from database import db
from paypal_client import create_payment
from address_processor import AddressProcessor
from datamatrix_processor import DataMatrixProcessor
from dpd_processor import DPDProcessor
from pylibdmtx.pylibdmtx import decode as dmtx_decode
from PIL import Image

logging.basicConfig(level=logging.INFO)

storage = MemoryStorage()
bot = Bot(token=Config.BOT_TOKEN)
dp = Dispatcher(storage=storage)

# ============ /START ============
@dp.message(Command("start"))
async def start_command(message: types.Message):
    welcome = """
🚀 *Welcome to ZapLabels!*

Select your country to continue:
    """
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🇬🇧 United Kingdom", callback_data="country_United Kingdom")]
    ])
    await message.answer(welcome, reply_markup=keyboard, parse_mode="Markdown")

# ============ COUNTRY SELECTED ============
@dp.callback_query(lambda c: c.data.startswith("country_"))
async def country_selected(callback: types.CallbackQuery):
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=f"📦 {carrier}", callback_data=f"carrier_{carrier}")]
        for carrier in Config.UK_CARRIERS
    ])
    await callback.message.edit_text(
        f"🇬🇧 *United Kingdom Selected*\n\nSelect your carrier:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# ============ CARRIER SELECTED ============
@dp.callback_query(lambda c: c.data.startswith("carrier_"))
async def carrier_selected(callback: types.CallbackQuery, state: FSMContext):
    carrier = callback.data.replace("carrier_", "")
    await state.update_data(carrier=carrier)
    
    if carrier == "UPS":
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=f"FTID (£15)", callback_data=f"service_FTID_{carrier}")],
            [types.InlineKeyboardButton(text=f"LIT (£20)", callback_data=f"service_LIT_{carrier}")]
        ])
    else:
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

# ============ SERVICE SELECTED ============
@dp.callback_query(lambda c: c.data.startswith("service_"))
async def service_selected(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data.replace("service_", "")
    parts = data.split("_")
    service = parts[0]
    carrier = "_".join(parts[1:])
    
    pricing = Config.PRICING.get("UK", {})
    service_map = {"FTID": "FTID", "LIT": "LIT", "RM RTS": "RM_RTS", "Receipt": "Receipt"}
    service_key = service_map.get(service, service)
    price = pricing.get(service_key, 0)
    
    await state.update_data(order={
        'carrier': carrier, 'service': service, 'price': price,
        'amount': price, 'country': 'United Kingdom', 'user_id': callback.from_user.id
    })
    
    if service == 'LIT':
        text = f"✅ *Service: {service}*\n📦 *Carrier: {carrier}*\n💰 *Price: £{price}*\n\n📝 *Please enter your Tracking Number*"
    else:
        text = f"✅ *Service: {service}*\n📦 *Carrier: {carrier}*\n💰 *Price: £{price}*\n\n📎 *Please send your label file (PDF or Image)*"
    
    await callback.message.edit_text(text, parse_mode="Markdown")

# ============ TEXT / QR HANDLER ============
@dp.message(lambda message: message.text and not message.text.startswith('/'))
async def handle_text(message: types.Message, state: FSMContext):
    order_data = await state.get_data()
    order = order_data.get('order')
    
    if not order:
        await message.answer("⚠️ Please select a service first. Use /start")
        return
        
    text_input = message.text.strip()
    carrier = order.get('carrier')
    service = order.get('service')
    
    tracking_number = text_input
    postcode = None
    
    import re
    if '1DBarcode=' in text_input and '|' in text_input:
        qr_data = {}
        for part in text_input.split('|'):
            if '=' in part:
                k, v = part.split('=', 1)
                qr_data[k.strip()] = v.strip()
        tracking_number = qr_data.get('1DBarcode', tracking_number)
        ret_details = qr_data.get('RetDetails', '')
        matches = re.findall(r'[A-Z]{1,2}[0-9][A-Z0-9]?\s?[0-9][A-Z]{2}', ret_details.upper())
        if matches:
            postcode = matches[-1]

    if service == 'LIT':
        os.makedirs("downloads", exist_ok=True)
        if carrier == 'Royal Mail':
            from template_processor import RoyalMailTemplateProcessor
            output_path = f"downloads/lit_{carrier}_{tracking_number}.jpg"
            result = RoyalMailTemplateProcessor.generate_label(tracking_number, None, output_path, 'LIT')
        else:
            from lit_processor import LITProcessor
            output_path = f"downloads/lit_{carrier}_{tracking_number}.png"
            result = LITProcessor.process_lit(tracking_number, carrier, output_path)
        
        if result:
            await message.answer(f"✅ *LIT Label Generated!*\n• Tracking: `{tracking_number}`", parse_mode="Markdown")
            await message.answer_document(FSInputFile(output_path), caption="📦 Your LIT label")
        else:
            await message.answer("⚠️ *LIT processing failed. Template might be missing.*", parse_mode="Markdown")
        return
            
    elif service in ['FTID', 'RM RTS']:
        if not postcode:
            await message.answer("⚠️ *QR String missing delivery address/postcode.*", parse_mode="Markdown")
            return
            
        warehouse = await AddressProcessor.find_nearest_warehouse(postcode, carrier)
        if warehouse:
            await message.answer(f"✅ *QR Label Generated!*\n• Tracking: `{tracking_number}`\n• New Postcode: `{warehouse['postcode']}`", parse_mode="Markdown")
            if carrier == 'Royal Mail':
                from template_processor import RoyalMailTemplateProcessor
                output_path = f"downloads/ftid_qr_{tracking_number}.jpg"
                result = RoyalMailTemplateProcessor.generate_label(tracking_number, warehouse, output_path, service)
                if result:
                    await message.answer_document(FSInputFile(output_path), caption="📦 Your label")
        else:
            await message.answer("⚠️ *No 3PL warehouse found in database.*", parse_mode="Markdown")
        return
    else:
        await message.answer("⚠️ Please send a label file (PDF or Image), not text.")
        return

# ============ FILE UPLOAD HANDLER ============
@dp.message(lambda message: message.document or message.photo)
async def handle_file(message: types.Message, state: FSMContext):
    order_data = await state.get_data()
    order = order_data.get('order')
    
    if not order:
        await message.answer("⚠️ Please select a service first. Use /start")
        return
    
    # Download file
    if message.document:
        file = message.document
        file_path = f"downloads/{file.file_name}"
    else:
        file = message.photo[-1]
        file_path = f"downloads/photo_{message.from_user.id}.jpg"
    
    os.makedirs("downloads", exist_ok=True)
    await bot.download(file, file_path)
    
    carrier = order.get('carrier', 'Royal Mail')
    service = order.get('service', 'FTID')
    
    # FIX: Force output to .jpg so Telegram sends it properly
    output_path = f"downloads/out_{os.path.splitext(os.path.basename(file_path))[0]}.jpg"

    # ===== CARRIER-BASED ROUTING =====
    if carrier == 'UPS':
        try:
            from ups_processor import UPSProcessor
            raw_postcode = UPSProcessor.extract_postcode_ocr(file_path) or 'E1 6AN'
            warehouse = await AddressProcessor.find_nearest_warehouse(raw_postcode, carrier)
            if warehouse:
                result = UPSProcessor.process_ups_label(file_path, warehouse, output_path)
                if result and os.path.exists(output_path):
                    await message.answer(f"✅ *UPS Label Processed!*", parse_mode="Markdown")
                    await message.answer_document(FSInputFile(output_path), caption="📦 UPS label")
                else:
                    await message.answer("⚠️ *UPS processing failed or file not created.*")
            else:
                await message.answer("⚠️ *No UPS warehouse found.*")
        except Exception as e:
            await message.answer(f"⚠️ UPS error: {e}")

    elif carrier == 'DPD':
        try:
            from dpd_processor import DPDProcessor
            raw_postcode = DPDProcessor.extract_postcode_ocr(file_path) or 'E1 6AN'
            warehouse = await AddressProcessor.find_nearest_warehouse(raw_postcode, carrier)
            if warehouse:
                result = DPDProcessor.process_dpd_label(file_path, warehouse, output_path)
                if result and os.path.exists(output_path):
                    await message.answer(f"✅ *DPD Label Processed!*", parse_mode="Markdown")
                    await message.answer_document(FSInputFile(output_path), caption="📦 DPD label")
                else:
                    await message.answer("⚠️ *DPD processing failed.*")
            else:
                await message.answer("⚠️ *No DPD warehouse found.*")
        except Exception as e:
            await message.answer(f"⚠️ DPD error: {e}")

    elif carrier == 'Evri':
        try:
            from evri_processor import EvriProcessor
            raw_postcode = EvriProcessor.extract_postcode_ocr(file_path) or 'E1 6AN'
            warehouse = await AddressProcessor.find_nearest_warehouse(raw_postcode, carrier)
            if warehouse:
                result = EvriProcessor.process_evri_label(file_path, warehouse, output_path)
                if result and os.path.exists(output_path):
                    await message.answer(f"✅ *Evri Label Processed!*", parse_mode="Markdown")
                    await message.answer_document(FSInputFile(output_path), caption="📦 Evri label")
                else:
                    await message.answer("⚠️ *Evri processing failed.*")
            else:
                await message.answer("⚠️ *No Evri warehouse found.*")
        except Exception as e:
            await message.answer(f"⚠️ Evri error: {e}")

    elif carrier == 'DHL':
        try:
            from dhl_processor import DHLProcessor
            raw_postcode = DHLProcessor.extract_postcode_ocr(file_path) or 'E1 6AN'
            warehouse = await AddressProcessor.find_nearest_warehouse(raw_postcode, carrier)
            if warehouse:
                result = DHLProcessor.process_dhl_label(file_path, warehouse, output_path)
                if result and os.path.exists(output_path):
                    await message.answer(f"✅ *DHL Label Processed!*", parse_mode="Markdown")
                    await message.answer_document(FSInputFile(output_path), caption="📦 DHL label")
                else:
                    await message.answer("⚠️ *DHL processing failed.*")
            else:
                await message.answer("⚠️ *No DHL warehouse found.*")
        except Exception as e:
            await message.answer(f"⚠️ DHL error: {e}")

    else:
        # ===== ROYAL MAIL PIPELINE =====
        try:
            from royal_mail_processor import RoyalMailProcessor

            raw_postcode, orig_name = None, None
            try:
                raw_postcode, orig_name = RoyalMailProcessor.extract_label_info(file_path)
            except Exception:
                pass

            postcode = raw_postcode if raw_postcode else 'B1 1AA'
            warehouse = await AddressProcessor.find_nearest_warehouse(postcode, 'Royal Mail')

            if warehouse:
                if service == 'RM RTS':
                    result = RoyalMailProcessor.process_rts_label(file_path, warehouse, output_path)
                    msg_text = "✅ *Royal Mail RTS Label Created!*"
                else:
                    result = RoyalMailProcessor.process_royal_mail_label(file_path, warehouse, output_path)
                    msg_text = "✅ *Royal Mail FTID Label Created!*"

                if result and os.path.exists(output_path):
                    await message.answer(msg_text, parse_mode="Markdown")
                    await message.answer_document(FSInputFile(output_path), caption="📬 Your processed Royal Mail label")
                else:
                    await message.answer("⚠️ *Royal Mail processing failed.*")
            else:
                await message.answer("⚠️ *No Royal Mail warehouse found.*")

        except Exception as e:
            import traceback
            traceback.print_exc()
            await message.answer(f"⚠️ Royal Mail error: {e}")

    # Save order to database
    try:
        await db.save_order(order)
    except Exception:
        pass
    
    # ===== CREATE PAYPAL PAYMENT =====
    amount = float(order['price'])
    payment, approval_url = create_payment(amount, "GBP", f"{order['service']} for {order['carrier']}")
    
    if payment and approval_url:
        await state.update_data(payment_id=payment.id)
        payment_text = f"💳 *Payment Required*\n\n• Service: {order['service']}\n• Carrier: {order['carrier']}\n• Amount: £{order['price']}"
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="💳 Pay with PayPal", url=approval_url)],
            [types.InlineKeyboardButton(text="✅ I've Paid", callback_data=f"paid_{order['carrier']}_{order['service']}")]
        ])
        await message.answer(payment_text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await message.answer("❌ Payment creation failed.")

# ============ PAYMENT CONFIRMATION ============
@dp.callback_query(lambda c: c.data.startswith("paid_"))
async def payment_confirmed(callback: types.CallbackQuery, state: FSMContext):
    order_data = await state.get_data()
    order = order_data.get('order')
    
    if order:
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        order_id = f"ZAP-{timestamp}-{order['user_id']}"
        try:
            await db.update_order_status(order_id, 'completed')
        except Exception:
            pass
    
    await callback.message.edit_text(
        f"✅ *Payment Confirmed!*\n\n⏳ Processing your {order['service']} for {order['carrier']}...\n📁 File saved in downloads folder.",
        parse_mode="Markdown"
    )

# ============ ADMIN PANEL ============
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != Config.ADMIN_ID:
        await message.answer("⚠️ Unauthorized access.")
        return
    
    try:
        orders = await db.get_orders(10)
        if not orders:
            await message.answer("📭 No orders found.")
            return
        
        text = "📊 *Recent Orders:*\n\n"
        for order in orders:
            text += f"• {order['order_id']} | {order['country']} | {order['service']} | £{order['amount']} | {order['status']}\n"
        
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"⚠️ Error: {str(e)}")

# ============ MAIN ============
async def main():
    os.makedirs("downloads", exist_ok=True)
    await db.connect()
    print("✅ Database connected!")
    print(f"👉 Bot: @{Config.BOT_TOKEN.split(':')[0]}")
    
    retry_delay = 5
    max_delay = 60
    attempt = 0
    
    while True:
        try:
            attempt += 1
            print(f"🔄 Starting polling (attempt #{attempt})...")
            await dp.start_polling(bot)
            break
        except Exception as e:
            err = str(e)
            if any(x in err for x in ["ClientConnectorError", "TelegramNetworkError", "WinError", "semaphore", "timeout", "ServerDisconnectedError"]):
                print(f"⚠️ Network error: {e}")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_delay)
            else:
                print(f"❌ Fatal error: {e}")
                raise

if __name__ == "__main__":
    asyncio.run(main())