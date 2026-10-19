import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Optional

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from shazamio import Shazam
import yt_dlp

# ==================== SOZLAMALAR ====================
BOT_TOKEN = "8913140977:AAEP2EAnL0qT4Lh36Vcq0alN4v1hJhZJx74"  # Tokeningiz

# Majburiy obuna kanallari (Username yoki ID ko'rinishida)
CHANNEL_IDS = [
    "@anizone_2",  # <-- Kanal username'ingiz
]

ADMIN_IDS = [8318241400]  # Admin ID lari

# Vaqtinchalik fayllar uchun papka
TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== BOT VA DISPATCHER ====================
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
router = Router()
dp.include_router(router)

shazam = Shazam()


# ==================== YORDAMCHI FUNKSIYALAR ====================
async def check_subscription(user_id: int) -> bool:
    """Foydalanuvchi barcha kanallarga obuna bo‘lganligini tekshiradi"""
    for channel in CHANNEL_IDS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            # Agar foydalanuvchi chiqib ketgan yoki bloklagan bo'lsa
            if member.status in ("left", "kicked"):
                return False
        except Exception as e:
            # Agar bot kanalga admin bo'lmasa yoki kanal topilmasa xatolikni logga yozadi
            logger.error(f"Obuna tekshirishda xato ({channel}): {e}")
            return False
    return True


def subscription_keyboard() -> InlineKeyboardMarkup:
    """Majburiy obuna tugmalari"""
    builder = InlineKeyboardBuilder()
    for i, channel in enumerate(CHANNEL_IDS, 1):
        if isinstance(channel, str) and channel.startswith("@"):
            url = f"https://t.me/{channel[1:]}"
        else:
            url = f"https://t.me/c/{str(channel)[4:]}" if str(channel).startswith("-100") else f"https://t.me/{channel}"
        
        builder.button(
            text=f"📢 Kanalga a'zo bo'lish #{i}",
            url=url
        )
    builder.button(text="✅ Tekshirish", callback_data="check_sub")
    builder.adjust(1)
    return builder.as_markup()


def search_results_keyboard(results: list, query: str) -> InlineKeyboardMarkup:
    """YouTube qidiruv natijalari uchun tugmalar"""
    builder = InlineKeyboardBuilder()
    for idx, item in enumerate(results[:5], 1):
        title = item.get("title", "Noma'lum")[:40]
        builder.button(
            text=f"▶️ {idx}. {title}",
            callback_data=f"yt_dl|{item['id']}|{idx}"
        )
    builder.button(text="❌ Boshqasini qidirish", callback_data="cancel_search")
    builder.adjust(1)
    return builder.as_markup()


def clean_filename(name: str) -> str:
    """Fayl nomini tozalash (maxsus belgilarni olib tashlash)"""
    return re.sub(r'[\\/*?:"<>|]', "", name)[:80]


async def download_youtube_audio(video_id: str, title: str) -> Optional[Path]:
    """yt-dlp yordamida YouTube dan audio yuklab olish"""
    output_path = TEMP_DIR / f"{video_id}.%(ext)s"
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(output_path),
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
            for file in TEMP_DIR.glob(f"{video_id}.*"):
                if file.suffix == ".mp3":
                    return file
            for file in TEMP_DIR.glob("*.mp3"):
                if video_id in str(file) or clean_filename(title) in str(file):
                    return file
    except Exception as e:
        logger.error(f"YouTube yuklash xatosi: {e}")
    return None


async def search_youtube(query: str, limit: int = 5) -> list:
    """YouTube dan qidirish"""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "default_search": "ytsearch",
        "skip_download": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
            entries = result.get("entries", [])
            return [
                {
                    "id": e.get("id"),
                    "title": e.get("title", "Noma'lum"),
                    "uploader": e.get("uploader", "Noma'lum"),
                    "duration": e.get("duration"),
                }
                for e in entries if e
            ]
    except Exception as e:
        logger.error(f"YouTube qidiruv xatosi: {e}")
        return []


# ==================== HANDLERLAR ====================

@router.message(CommandStart())
async def cmd_start(message: Message):
    """ /start buyrug‘i """
    user_id = message.from_user.id
    if await check_subscription(user_id):
        await message.answer(
            "🎵 <b>Assalomu alaykum!</b>\n\n"
            "Men musiqa botiman. Quyidagilarni qila olaman:\n\n"
            "🔍 <b>Video yoki dumaloq video</b> yuboring — musiqani aniqlayman (Shazam)\n"
            "✍️ <b>Qo‘shiq nomi</b> yozing — YouTube dan qidirib yuklab beraman\n\n"
            "Masalan: <code>Janob Rasul - Yig'lama</code>\n\n"
            "Boshlash uchun video yuboring yoki qidiruv so‘zini yozing! 🚀"
        )
    else:
        await message.answer(
            "📢 <b>Assalomu alaykum!</b>\n\n"
            "Botdan foydalanish uchun quyidagi kanal(lar)ga <b>obuna bo‘lishingiz</b> shart.\n\n"
            "Obuna bo‘lgach «✅ Tekshirish» tugmasini bosing.",
            reply_markup=subscription_keyboard()
        )


@router.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: CallbackQuery):
    """Obunani tekshirish"""
    user_id = callback.from_user.id
    if await check_subscription(user_id):
        await callback.message.edit_text(
            "✅ <b>Rahmat!</b> Obuna tasdiqlandi.\n\n"
            "Endi botdan to‘liq foydalanishingiz mumkin.\n\n"
            "🔍 Video yuboring yoki qo‘shiq nomini yozing!"
        )
        await callback.answer("Obuna muvaffaqiyatli tasdiqlandi! 🎉")
    else:
        await callback.answer(
            "❌ Hali barcha kanallarga obuna bo‘lmadingiz!",
            show_alert=True
        )


@router.message(F.video | F.video_note | F.audio | F.voice)
async def handle_media(message: Message):
    """Video / dumaloq video / audio kelganda Shazam ishga tushadi"""
    user_id = message.from_user.id
    if not await check_subscription(user_id):
        await message.answer(
            "❌ Avval kanallarga obuna bo‘ling!",
            reply_markup=subscription_keyboard()
        )
        return

    status_msg = await message.answer("🔍 Videodagi musiqa qidirilmoqda... 🎵")

    file_id = None
    file_path = None
    try:
        if message.video:
            file_id = message.video.file_id
        elif message.video_note:
            file_id = message.video_note.file_id
        elif message.audio:
            file_id = message.audio.file_id
        elif message.voice:
            file_id = message.voice.file_id

        if not file_id:
            await status_msg.edit_text("😔 Afsuski, faylni o‘qib bo‘lmadi.")
            return

        file = await bot.get_file(file_id)
        file_path = TEMP_DIR / f"{file_id}.mp4"
        await bot.download_file(file.file_path, destination=file_path)

        result = await shazam.recognize(str(file_path))

        if result and "track" in result:
            track = result["track"]
            title = track.get("title", "Noma'lum")
            artist = track.get("subtitle", "Noma'lum")

            text = (
                f"🎧 <b>Musiqa topildi!</b>\n\n"
                f"🎤 <b>Ijrochi:</b> {artist}\n"
                f"🎼 <b>Qo‘shiq:</b> {title}\n"
            )

            await status_msg.edit_text(text + "\n📥 MP3 yuklanmoqda...")

            search_query = f"{artist} - {title}"
            yt_results = await search_youtube(search_query, limit=1)

            if yt_results:
                video_id = yt_results[0]["id"]
                audio_path = await download_youtube_audio(video_id, title)
                if audio_path and audio_path.exists():
                    await message.answer_audio(
                        audio=FSInputFile(audio_path),
                        title=title,
                        performer=artist,
                        caption=text
                    )
                    await status_msg.delete()
                    try:
                        audio_path.unlink(missing_ok=True)
                    except:
                        pass
                    return

            await status_msg.edit_text(text + "\n😔 MP3 ni avtomatik yuklab bo‘lmadi, lekin musiqa aniqlandi.")
        else:
            await status_msg.edit_text("😔 Afsuski, musiqa topilmadi.")

    except Exception as e:
        logger.exception("Shazam xatosi")
        await status_msg.edit_text("😔 Xatolik yuz berdi. Keyinroq urinib ko‘ring.")
    finally:
        if file_path and file_path.exists():
            try:
                file_path.unlink(missing_ok=True)
            except:
                pass


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_search(message: Message, state: FSMContext):
    """Matn yozilganda YouTube qidiruvi"""
    user_id = message.from_user.id
    if not await check_subscription(user_id):
        await message.answer(
            "❌ Avval kanallarga obuna bo‘ling!",
            reply_markup=subscription_keyboard()
        )
        return

    query = message.text.strip()
    if len(query) < 2:
        await message.answer("🔍 Iltimos, kamida 2 ta harf yozing.")
        return

    status = await message.answer(f"🔎 <b>«{query}»</b> qidirilmoqda...")

    results = await search_youtube(query, limit=5)

    if not results:
        await status.edit_text("😔 Afsuski, hech narsa topilmadi.")
        return

    text = f"🎵 <b>Qidiruv natijalari:</b> <i>{query}</i>\n\n"
    for i, item in enumerate(results, 1):
        duration = ""
        if item.get("duration"):
            mins = item["duration"] // 60
            secs = item["duration"] % 60
            duration = f" ({mins}:{secs:02d})"
        text += f"<b>{i}.</b> {item['title']}{duration}\n👤 {item.get('uploader', 'Noma\'lum')}\n\n"

    await status.edit_text(
        text,
        reply_markup=search_results_keyboard(results, query)
    )
    await state.update_data(last_results=results)


@router.callback_query(F.data.startswith("yt_dl|"))
async def download_selected(callback: CallbackQuery, state: FSMContext):
    """Tanlangan musiqani yuklash"""
    try:
        _, video_id, idx = callback.data.split("|")
        idx = int(idx)

        data = await state.get_data()
        results = data.get("last_results", [])
        if not results or idx > len(results):
            await callback.answer("Natijalar eskirgan. Qayta qidiring.", show_alert=True)
            return

        item = results[idx - 1]
        title = item.get("title", "Musiqa")

        await callback.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⏳ Yuklanmoqda...", callback_data="loading")]
            ])
        )
        await callback.answer()

        status = await callback.message.answer(f"📥 <b>{title}</b>\nYuklanmoqda... ⏳")

        audio_path = await download_youtube_audio(video_id, title)

        if audio_path and audio_path.exists():
            await callback.message.answer_audio(
                audio=FSInputFile(audio_path),
                title=title,
                performer=item.get("uploader", "YouTube"),
                caption=f"🎵 <b>{title}</b>\n👤 {item.get('uploader', 'Noma\'lum')}"
            )
            await status.delete()
            try:
                audio_path.unlink(missing_ok=True)
            except:
                pass
        else:
            await status.edit_text("😔 Yuklab olishda xatolik yuz berdi.")

        try:
            await callback.message.delete()
        except:
            pass

    except Exception as e:
        logger.exception("Yuklash xatosi")
        await callback.answer("Xatolik yuz berdi", show_alert=True)


@router.callback_query(F.data == "cancel_search")
async def cancel_search(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Qidiruv bekor qilindi.\n\nYangi so‘rov yozing.")
    await callback.answer()


@router.callback_query(F.data == "loading")
async def loading_dummy(callback: CallbackQuery):
    await callback.answer("Hali yuklanmoqda... ⏳", show_alert=False)


# ==================== ISHGA TUSHIRISH ====================
async def main():
    logger.info("Bot ishga tushmoqda...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
