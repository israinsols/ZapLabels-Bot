from aiogram import Router, types
from aiogram.filters import Command

router = Router()

@router.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer(
        "Label editing and redirection are unavailable. For a valid shipping label, "
        "please use the carrier's official website or support channel."
    )
