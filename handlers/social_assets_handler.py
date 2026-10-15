"""Telegram UI for the built-in SLH Spark social media asset gallery."""
from __future__ import annotations

from io import BytesIO
from urllib.parse import quote

from core.social_asset_library import get_asset, list_assets, render_social_asset


PUBLIC_BASE_URL = "https://slh-cloud-bot-production.up.railway.app"
MINI_APP_URL = PUBLIC_BASE_URL + "/mini-app-v4"


def _share_url(asset: dict) -> str:
    text = str(asset.get("caption") or "").strip()
    share_page = PUBLIC_BASE_URL + "/share/" + quote(str(asset["id"]), safe="")
    return "https://t.me/share/url?url=" + quote(share_page, safe="") + "&text=" + quote(text, safe="")


def _catalog_markup():
    from telebot import types

    catalog = list_assets(PUBLIC_BASE_URL)
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton(
            text=("✨ " if item["id"] == "brand" else "🎨 ") + str(item["title"])[:50],
            callback_data=f"slhmedia:{item['id']}",
        )
        for item in catalog
    ]
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton("🌐 פתיחת SLH Spark", url=MINI_APP_URL))
    return markup


def _send_catalog(bot, chat_id, *, edit_message=None):
    text = (
        "🖼️ SLH Spark — מאגר עיצובים לשיתוף\n\n"
        "בחר עיצוב. הבוט ייצור את תמונת ה־PNG וישלח אותה כאן יחד עם טקסט מוכן.\n"
        "אפשר להעביר את התמונה לרשת חברתית או להשתמש בממשק השיתוף של המכשיר. "
        "העיצובים אינם מכילים הבטחות רווח או טענות שמסחר פתוח."
    )
    markup = _catalog_markup()
    if edit_message is not None:
        try:
            bot.edit_message_text(
                text,
                chat_id=edit_message.chat.id,
                message_id=edit_message.message_id,
                reply_markup=markup,
                parse_mode=None,
            )
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode=None)


def register(bot):
    @bot.message_handler(commands=["media", "share_assets", "postmaker"])
    def social_assets_cmd(message):
        chat = getattr(message, "chat", None)
        chat_id = getattr(chat, "id", None)
        if chat_id is None:
            return
        if str(getattr(chat, "type", "") or "").lower() != "private":
            bot.reply_to(message, "פתח את מאגר התמונות בשיחה הפרטית עם הבוט.", parse_mode=None)
            return
        _send_catalog(bot, chat_id)

    @bot.callback_query_handler(func=lambda call: str(getattr(call, "data", "") or "").startswith("slhmedia:"))
    def social_assets_callback(call):
        data = str(getattr(call, "data", "") or "")
        message = getattr(call, "message", None)
        chat = getattr(message, "chat", None)
        chat_id = getattr(chat, "id", None)
        if chat_id is None or str(getattr(chat, "type", "") or "").lower() != "private":
            try:
                bot.answer_callback_query(call.id, "פתח את המאגר בשיחה הפרטית עם הבוט.", show_alert=True)
            except Exception:
                pass
            return
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

        asset_id = data.split(":", 1)[1].strip().lower()
        if asset_id == "gallery":
            _send_catalog(bot, chat_id, edit_message=message)
            return
        try:
            asset = get_asset(asset_id)
            payload = render_social_asset(asset_id)
        except KeyError:
            bot.send_message(chat_id, "העיצוב אינו קיים. פתח /media ובחר עיצוב אחר.", parse_mode=None)
            return
        except Exception as exc:
            bot.send_message(chat_id, f"לא ניתן ליצור תמונה כרגע ({type(exc).__name__}).", parse_mode=None)
            return

        from telebot import types

        buttons = types.InlineKeyboardMarkup(row_width=2)
        buttons.row(
            types.InlineKeyboardButton("🔗 שתף טקסט וקישור", url=_share_url(asset)),
            types.InlineKeyboardButton("🌐 פתח את Mini App", url=MINI_APP_URL),
        )
        buttons.add(types.InlineKeyboardButton("🎨 בחר עיצוב אחר", callback_data="slhmedia:gallery"))
        photo = BytesIO(payload)
        photo.name = f"slh-spark-{asset_id}.png"
        bot.send_photo(
            chat_id,
            photo,
            caption=(str(asset["caption"]) + "\n\n" + PUBLIC_BASE_URL + "/share/" + asset_id)[:1024],
            reply_markup=buttons,
            parse_mode=None,
        )

    print("✅ social assets gallery handler registered")
