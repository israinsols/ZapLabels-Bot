import asyncio
import logging
import os
from datetime import datetime
from PIL import Image
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile
from config import Config
from database import db
from paypal_client import create_payment
from datamatrix_processor import DataMatrixProcessor
from address_processor import AddressProcessor
from label_editor import LabelEditor
from dpd_processor import DPDProcessor
from pylibdmtx.pylibdmtx import decode as dmtx_decode

logging.basicConfig(level=logging.INFO)

storage = MemoryStorage()
bot = Bot(token=Config.BOT_TOKEN)
dp = Dispatcher(storage=storage)

# ============ COUNTRIES ============
COUNTRIES = {
    "United Kingdom": "🇬🇧",
    "USA": "🇺🇸",
    "Spain": "🇪🇸",
    "Germany": "🇩🇪",
    "Italy": "🇮🇹",
    "France": "🇫🇷"
}

# ============ /START ============
@dp.message(Command("start"))
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

# ============ COUNTRY SELECTED ============
@dp.callback_query(lambda c: c.data.startswith("country_"))
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
        text += "\n📎 Please send your label file."
        
        await callback.message.edit_text(text, parse_mode="Markdown")

# ============ CARRIER SELECTED ============
@dp.callback_query(lambda c: c.data.startswith("carrier_"))
async def carrier_selected(callback: types.CallbackQuery, state: FSMContext):
    carrier = callback.data.replace("carrier_", "")
    
    # Store carrier in state
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
    
    # Get price - Fix: Map service name to pricing key
    pricing = Config.PRICING.get("UK", {})
    
    # Service name mapping
    service_map = {
        "FTID": "FTID",
        "LIT": "LIT",
        "RM RTS": "RM_RTS",
        "Receipt": "Receipt"
    }
    
    # Get correct price
    service_key = service_map.get(service, service)
    price = pricing.get(service_key, 0)
    
    print(f"🔍 Service: {service}, Price: {price}")  # Debug
    
    # Store in state with 'amount' field
    await state.update_data(order={
        'carrier': carrier,
        'service': service,
        'price': price,
        'amount': price,
        'country': 'United Kingdom',
        'user_id': callback.from_user.id
    })
    
    if service == 'LIT':
        text = f"""
✅ *Service Selected: {service}*
📦 *Carrier: {carrier}*
💰 *Price: £{price}*

📝 *Please enter your Tracking Number*
"""
    else:
        text = f"""
✅ *Service Selected: {service}*
📦 *Carrier: {carrier}*
💰 *Price: £{price}*

📎 *Please send your label file (PDF or Image)*
"""
    
    await callback.message.edit_text(text, parse_mode="Markdown")

# ============ TEXT/LIT HANDLER ============
@dp.message(lambda message: message.text and not message.text.startswith('/'))
async def handle_text(message: types.Message, state: FSMContext):
    order_data = await state.get_data()
    order = order_data.get('order')
    
    if not order:
        await message.answer("⚠️ Please select a service first. Use /start")
        return
        
    if order.get('service') == 'LIT':
        print("🔄 LIT Mode: Processing...")
        tracking_number = message.text.strip()
        carrier = order.get('carrier')
        
        from lit_processor import LITProcessor
        os.makedirs("downloads", exist_ok=True)
        output_path = f"downloads/lit_{carrier}_{tracking_number}.png"
        
        result = LITProcessor.process_lit(tracking_number, carrier, output_path)
        
        if result:
            decode_msg = f"""
✅ *LIT Label Generated!*

📋 *Details:*
• Carrier: `{carrier}`
• Tracking: `{tracking_number}`

✅ *Address & Barcode Ready!*
📁 Label: `{output_path}`
"""
            await message.answer(decode_msg, parse_mode="Markdown")
            
            # Save order to database
            try:
                db_result = await db.save_order(order)
            except Exception as e:
                print(f"❌ Error saving order: {e}")
            
            # ===== CREATE PAYPAL PAYMENT =====
            amount = float(order['price'])
            payment, approval_url = create_payment(amount, "GBP", f"{order['service']} for {order['carrier']}")
            
            if payment and approval_url:
                await state.update_data(payment_id=payment.id)
                payment_text = f"""
💳 *Payment Required*

📦 *Order Details:*
• Service: {order['service']}
• Carrier: {order['carrier']}
• Amount: £{order['price']}

🔗 *Click below to pay via PayPal:*
[Pay Now]({approval_url})

⏳ After payment, click "I've Paid" to confirm.
"""
                keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="💳 Pay with PayPal", url=approval_url)],
                    [types.InlineKeyboardButton(text="✅ I've Paid", callback_data=f"paid_{order['carrier']}_{order['service']}")]
                ])
                await message.answer(payment_text, reply_markup=keyboard, parse_mode="Markdown")
            else:
                await message.answer("❌ Payment creation failed. Please try again.")
        else:
            await message.answer("⚠️ *LIT processing failed. Template might be missing.*", parse_mode="Markdown")
    else:
        await message.answer("⚠️ Please send a label file (PDF or Image), not text.")

# ============ FILE UPLOAD HANDLER ============
@dp.message(lambda message: message.document or message.photo)
async def handle_file(message: types.Message, state: FSMContext):
    # Get order data from state
    order_data = await state.get_data()
    order = order_data.get('order')
    
    print(f"📦 Order from state: {order}")  # Debug
    
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
    output_path = f"downloads/ftid_{os.path.basename(file_path)}"

    # ===== AUTO-DETECT LABEL TYPE =====
    # Run in executor with timeout so it never hangs the bot
    def _detect_label_type(fp):
        import cv2 as _cv2
        from pyzbar.pyzbar import decode as _pyzbar
        _img = _cv2.imread(fp)
        if _img is None:
            return None
        _gray = _cv2.cvtColor(_img, _cv2.COLOR_BGR2GRAY)
        # Resize to max 800px to speed up scanning
        _h, _w = _gray.shape
        if max(_h, _w) > 800:
            _scale = 800 / max(_h, _w)
            _gray = _cv2.resize(_gray, (int(_w * _scale), int(_h * _scale)))
        _pil = Image.fromarray(_gray)
        _pyzbar_result = _pyzbar(_pil)
        _dmtx_result   = dmtx_decode(_pil, timeout=3000)  # 3s timeout
        if _dmtx_result and not _pyzbar_result:
            return 'Royal Mail'
        elif _pyzbar_result:
            for b in _pyzbar_result:
                try:
                    data = b.data.decode('utf-8')
                    if '1Z' in data:
                        return 'UPS'
                    import re
                    if re.match(r'^[A-Z0-9]{16}$', data) or re.match(r'^[HP]\d{15}$', data):
                        return 'Evri'
                    if '%' in data or data.startswith('05') or data.startswith('1550'):
                        return 'DPD'
                except:
                    pass
            return None
        return None

    try:
        loop = asyncio.get_event_loop()
        detected = await asyncio.wait_for(
            loop.run_in_executor(None, _detect_label_type, file_path),
            timeout=10  # max 10s
        )
        if detected:
            print(f"🔄 Auto-detect: {detected} label → using {detected} pipeline")
            carrier = detected
        else:
            print(f"🔄 Auto-detect: No barcode found → using selected carrier: {carrier}")
    except asyncio.TimeoutError:
        print(f"⚠️ Auto-detect timed out → using selected carrier: {carrier}")
    except Exception as _e:
        print(f"⚠️ Auto-detect failed: {_e} → using selected carrier: {carrier}")


    # ===== CARRIER-BASED ROUTING =====
    if carrier == 'UPS':
        # ===== UPS PIPELINE =====
        try:
            print("\n" + "=" * 50)
            print("🚚 UPS Automation Start!")
            print("=" * 50)
            
            # Postcode will be extracted in process_ups_label, for warehouse we can try a basic extraction first
            try:
                from ups_processor import UPSProcessor
                raw_postcode = UPSProcessor.extract_postcode_ocr(file_path)
            except Exception:
                raw_postcode = 'E1 6AN'
                
            postcode = raw_postcode or 'E1 6AN'
            warehouse = await AddressProcessor.find_nearest_warehouse(postcode, carrier)
            
            if warehouse:
                result = UPSProcessor.process_ups_label(file_path, warehouse, output_path)
                
                if result:
                    decode_msg = f"""
✅ *UPS Label Processed!*

📋 *Details:*
• Barcode Type: `{result['barcode_type']}`
• Tracking: `{result['tracking'] or 'N/A'}`

🏭 *Redirected to 3PL Warehouse:*
• Name: `{warehouse['name']}`
• Address: `{warehouse['address']}`
• New Postcode: `{warehouse['postcode']}`

✅ *Address & Barcode Updated!*
📁 Label: `{result['output_path']}`
"""
                else:
                    decode_msg = "⚠️ *UPS processing failed. Please check the label.*"
            else:
                decode_msg = "⚠️ *No UPS warehouse found in database.*"
                
            await message.answer(decode_msg, parse_mode="Markdown")
            
            if result and result.get('output_path') and os.path.exists(result['output_path']):
                await message.answer_document(
                    FSInputFile(result['output_path']),
                    caption="📦 Your processed UPS label"
                )
                
        except Exception as e:
            await message.answer(f"⚠️ UPS processing error: {e}")

    elif carrier == 'DPD':
        # ===== DPD PIPELINE =====
        try:
            print("\n" + "=" * 50)
            print("🚚 DPD Automation Start!")
            print("=" * 50)

            # Get postcode from barcode first, fall back to OCR
            try:
                barcodes, _ = DPDProcessor.detect_barcode(file_path)
                raw_postcode = DPDProcessor.extract_postcode_ocr(file_path)
            except Exception:
                barcodes = []
                raw_postcode = 'E1 6AN'

            postcode = raw_postcode or 'E1 6AN'
            warehouse = await AddressProcessor.find_nearest_warehouse(postcode, carrier)

            if warehouse:
                result = DPDProcessor.process_dpd_label(file_path, warehouse, output_path)

                if result:
                    decode_msg = f"""
✅ *DPD Label Processed!*

📋 *Details:*
• Barcode Type: `{result['barcode_type']}`
• Tracking: `{result['tracking'] or 'N/A'}`
• Old Postcode: `{result['delivery_postcode'] or 'N/A'}`

🏭 *Redirected to 3PL Warehouse:*
• Name: `{warehouse['name']}`
• Address: `{warehouse['address']}`
• New Postcode: `{warehouse['postcode']}`

✅ *Address & Barcode Updated!*
📁 Label: `{result['output_path']}`
"""
                else:
                    decode_msg = "⚠️ *DPD processing failed. Please check the label.*"
            else:
                decode_msg = "⚠️ *No DPD warehouse found in database.*"

            await message.answer(decode_msg, parse_mode="Markdown")

            if result and result.get('output_path') and os.path.exists(result['output_path']):
                await message.answer_document(
                    FSInputFile(result['output_path']),
                    caption="📦 Your processed DPD label"
                )

        except Exception as e:
            await message.answer(f"⚠️ DPD processing error: {e}")

    elif carrier == 'Evri':
        # ===== EVRI PIPELINE =====
        try:
            print("\n" + "=" * 50)
            print("🚚 Evri Automation Start!")
            print("=" * 50)

            # Extract postcode
            try:
                from evri_processor import EvriProcessor
                raw_postcode = EvriProcessor.extract_postcode_ocr(file_path)
            except Exception:
                raw_postcode = 'E1 6AN'

            postcode = raw_postcode or 'E1 6AN'
            warehouse = await AddressProcessor.find_nearest_warehouse(postcode, carrier)

            if warehouse:
                result = EvriProcessor.process_evri_label(file_path, warehouse, output_path)

                if result:
                    decode_msg = f"""
✅ *Evri Label Processed!*

📋 *Details:*
• Barcode Type: `{result['barcode_type']}`
• Tracking: `{result['tracking'] or 'N/A'}`
• Old Postcode: `{result['delivery_postcode'] or 'N/A'}`

🏭 *Redirected to 3PL Warehouse:*
• Name: `{warehouse['name']}`
• Address: `{warehouse['address']}`
• New Postcode: `{warehouse['postcode']}`

✅ *Address & Barcode Updated!*
📁 Label: `{result['output_path']}`
"""
                else:
                    decode_msg = "⚠️ *Evri processing failed. Please check the label.*"
            else:
                decode_msg = "⚠️ *No Evri warehouse found in database.*"

            await message.answer(decode_msg, parse_mode="Markdown")

            if result and result.get('output_path') and os.path.exists(result['output_path']):
                await message.answer_document(
                    FSInputFile(result['output_path']),
                    caption="📦 Your processed Evri label"
                )

        except Exception as e:
            await message.answer(f"⚠️ Evri processing error: {e}")

    elif carrier == 'DHL':
        # ===== DHL PIPELINE =====
        try:
            print("\n" + "=" * 50)
            print("🚚 DHL Automation Start!")
            print("=" * 50)

            # Extract postcode
            try:
                from dhl_processor import DHLProcessor
                raw_postcode = DHLProcessor.extract_postcode_ocr(file_path)
            except Exception:
                raw_postcode = 'E1 6AN'

            postcode = raw_postcode or 'E1 6AN'
            warehouse = await AddressProcessor.find_nearest_warehouse(postcode, carrier)

            if warehouse:
                result = DHLProcessor.process_dhl_label(file_path, warehouse, output_path)

                if result:
                    decode_msg = f"""
✅ *DHL Label Processed!*

📋 *Details:*
• Barcode Type: `{result['barcode_type']}`
• Tracking: `{result['tracking'] or 'N/A'}`
• Old Postcode: `{result['delivery_postcode'] or 'N/A'}`

🏭 *Redirected to 3PL Warehouse:*
• Name: `{warehouse['name']}`
• Address: `{warehouse['address']}`
• New Postcode: `{warehouse['postcode']}`

✅ *Address & Barcode Updated!*
📁 Label: `{result['output_path']}`
"""
                else:
                    decode_msg = "⚠️ *DHL processing failed. Please check the label.*"
            else:
                decode_msg = "⚠️ *No DHL warehouse found in database.*"

            await message.answer(decode_msg, parse_mode="Markdown")

            if result and result.get('output_path') and os.path.exists(result['output_path']):
                await message.answer_document(
                    FSInputFile(result['output_path']),
                    caption="📦 Your processed DHL label"
                )

        except Exception as e:
            await message.answer(f"⚠️ DHL processing error: {e}")

    else:
        # ===== ROYAL MAIL / DEFAULT PIPELINE (Data Matrix) =====
        try:
            result = DataMatrixProcessor.process_label(file_path)
            if result:
                fields = result['fields']

                # Find nearest warehouse
                postcode = fields.get('postcode', 'ML3 8BL')
                warehouse = await AddressProcessor.find_nearest_warehouse(postcode, carrier)

                if warehouse:
                    # Create FTID label with address replacement
                    LabelEditor.create_ftid_label(file_path, warehouse, carrier, output_path)

                    # Regenerate Data Matrix with new address
                    final_output = DataMatrixProcessor.regenerate_datamatrix_on_label(
                        file_path,
                        warehouse['postcode'],
                        warehouse['name'],
                        output_path
                    )

                    if final_output:
                        decode_msg = f"""
✅ *FTID Label Created Successfully!*

📋 *Extracted Fields:*
• Service Type: `{fields.get('service_type', 'N/A')}`
• Tracking: `{fields.get('tracking', 'N/A')}`
• Old Postcode: `{fields.get('postcode', 'N/A')}`
• Old Building: `{fields.get('building_name', 'N/A')}`

🏭 *Nearest 3PL Warehouse:*
• Name: `{warehouse['name']}`
• Address: `{warehouse['address']}`
• New Postcode: `{warehouse['postcode']}`

✅ *Data Matrix Regenerated!*
📁 Final FTID Label: `{final_output}`
"""
                    else:
                        decode_msg = f"""
✅ *Data Matrix Decoded!*

📋 *Extracted Fields:*
• Service Type: `{fields.get('service_type', 'N/A')}`
• Tracking: `{fields.get('tracking', 'N/A')}`
• Postcode: `{fields.get('postcode', 'N/A')}`
• Building Name: `{fields.get('building_name', 'N/A')}`

🏭 *Nearest 3PL Warehouse:*
• Name: `{warehouse['name']}`
• Address: `{warehouse['address']}`
• Postcode: `{warehouse['postcode']}`

⚠️ *Data Matrix regeneration failed.*
📁 File saved in downloads folder.
"""
                else:
                    decode_msg = f"""
✅ *Data Matrix Decoded!*

📋 *Extracted Fields:*
• Service Type: `{fields.get('service_type', 'N/A')}`
• Tracking: `{fields.get('tracking', 'N/A')}`
• Postcode: `{fields.get('postcode', 'N/A')}`
• Building Name: `{fields.get('building_name', 'N/A')}`

⚠️ *No warehouse found in database.*

📁 File saved in downloads folder.
"""

                await message.answer(decode_msg, parse_mode="Markdown")
        except Exception as e:
            await message.answer(f"⚠️ Data Matrix decode failed: {e}")
    
    # Save order to database
    try:
        result = await db.save_order(order)
        if result:
            print(f"✅ Order saved: {result}")
        else:
            print(f"❌ Order not saved")
    except Exception as e:
        print(f"❌ Error saving order: {e}")
    
    # ===== CREATE PAYPAL PAYMENT =====
    amount = float(order['price'])
    payment, approval_url = create_payment(amount, "GBP", f"{order['service']} for {order['carrier']}")
    
    if payment and approval_url:
        # Store payment ID in state
        await state.update_data(payment_id=payment.id)
        
        payment_text = f"""
💳 *Payment Required*

📦 *Order Details:*
• Service: {order['service']}
• Carrier: {order['carrier']}
• Amount: £{order['price']}

🔗 *Click below to pay via PayPal:*
[Pay Now]({approval_url})

⏳ After payment, click "I've Paid" to confirm.
"""
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="💳 Pay with PayPal", url=approval_url)],
            [types.InlineKeyboardButton(text="✅ I've Paid", callback_data=f"paid_{order['carrier']}_{order['service']}")]
        ])
        
        await message.answer(payment_text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await message.answer("❌ Payment creation failed. Please try again.")

# ============ PAYMENT CONFIRMATION ============
@dp.callback_query(lambda c: c.data.startswith("paid_"))
async def payment_confirmed(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data.replace("paid_", "")
    parts = data.split("_")
    carrier = parts[0]
    service = "_".join(parts[1:])
    
    # Get order from state
    order_data = await state.get_data()
    order = order_data.get('order')
    
    print(f"📦 Payment confirmed for order: {order}")  # Debug
    
    if order:
        # Generate order_id with timestamp for uniqueness
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        order_id = f"ZAP-{timestamp}-{order['user_id']}"
        
        # Update order status using db.update_order_status
        try:
            result = await db.update_order_status(order_id, 'completed')
            if result:
                print(f"✅ Order status updated: {order_id}")
            else:
                print(f"❌ Failed to update order: {order_id}")
        except Exception as e:
            print(f"❌ Error updating order: {e}")
    
    try:
        await callback.message.edit_text(
            f"""
✅ *Payment Confirmed!*

⏳ Processing your {service} for {carrier}...
📁 File saved in downloads folder.

*Done! Your file is ready.* 🎉
            """,
            parse_mode="Markdown"
        )
    except Exception as e:
        if "message is not modified" in str(e):
            pass  # Already showing correct content, safe to ignore
        else:
            raise


# ============ ADMIN PANEL ============
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != Config.ADMIN_ID:
        await message.answer("⚠️ Unauthorized access.")
        return
    
    # Get all orders from database
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
    
    print("✅ Bot started!")
    print(f"👉 Bot: @{Config.BOT_TOKEN.split(':')[0]}")
    
    retry_delay = 5
    max_delay = 60
    attempt = 0
    
    while True:
        try:
            attempt += 1
            print(f"🔄 Starting polling (attempt #{attempt})...")
            await dp.start_polling(bot)
            break  # Clean exit, stop retrying
        except Exception as e:
            err = str(e)
            if any(x in err for x in ["ClientConnectorError", "TelegramNetworkError", "WinError", "semaphore", "timeout", "ServerDisconnectedError"]):
                print(f"⚠️ Network error: {e}")
                print(f"🔁 Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_delay)  # Exponential backoff, max 60s
            else:
                print(f"❌ Fatal error: {e}")
                raise

if __name__ == "__main__":
    asyncio.run(main())