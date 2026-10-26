from aiogram import Router, types

router = Router()

@router.callback_query(lambda c: c.data.startswith("country_"))
async def country_selected(callback: types.CallbackQuery):
    await callback.answer(
        "Label editing is unavailable. Please use the carrier's official service.",
        show_alert=True
    )


@router.callback_query(lambda c: c.data.startswith("carrier_"))
async def carrier_selected(callback: types.CallbackQuery):
    await callback.answer(
        "Label editing is unavailable. Please use the carrier's official service.",
        show_alert=True
    )