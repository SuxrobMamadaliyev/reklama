import os
import json
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes, ConversationHandler
)
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.errors.rpcerrorlist import SessionPasswordNeededError, FloodWaitError
from telethon.tl.functions.channels import JoinChannelRequest

# Load environment variables
load_dotenv()

# Konfiguratsiya
API_ID = int(os.getenv('API_ID', '28208741'))
API_HASH = os.getenv('API_HASH', '476620711a3188552ef8d377b2f103d6')
BOT_TOKEN = os.getenv('BOT_TOKEN', '8270205971:AAG2IvCMoqRwbyrsEC94759fBT_tvpokYQU')
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'suxacyber')

# Majburiy obuna
REQUIRED_CHANNEL = os.getenv('REQUIRED_CHANNEL', '@suxa_cyber')
CHANNEL_ID = int(os.getenv('CHANNEL_ID', '-1002220576401'))

# Fayllar va papkalar
SESSION_DIR = "sessions12"
DATA_DIR = "data"
COMPANIES_FILE = os.path.join(DATA_DIR, "companies.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
WELCOME_FILE = os.path.join(DATA_DIR, "welcome.txt")

# Bosqichlar
PHONE = 1
CODE = 2
PASSWORD = 3
COMPANY_NAME = 4
COMPANY_GROUP = 5
COMPANY_MSG = 6
COMPANY_INTERVAL = 7
COMPANY_CONFIRM = 8
ADMIN_BROADCAST = 9
ADMIN_WELCOME = 10

# Papkalarni yaratish
for directory in [SESSION_DIR, DATA_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

# Ma'lumotlar saqlash
session_data = {}
company_data = {}
user_companies = {}
active_companies = {}
all_users = set()

# --- Ma'lumotlarni yuklash va saqlash ---
def load_data():
    global user_companies, all_users
    try:
        if os.path.exists(COMPANIES_FILE):
            with open(COMPANIES_FILE, 'r', encoding='utf-8') as f:
                user_companies = json.load(f)
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                all_users = set(json.load(f))
    except Exception as e:
        print(f"Ma'lumotlarni yuklashda xatolik: {e}")

def save_data():
    try:
        # Kompaniyalarni saqlash (faqat ma'lumotlar, tasklar emas)
        companies_to_save = {}
        for user_id, companies in user_companies.items():
            companies_to_save[user_id] = {}
            for comp_name, comp_data in companies.items():
                companies_to_save[user_id][comp_name] = {
                    "name": comp_data.get("name", comp_name),
                    "group": comp_data.get("group", ""),
                    "message_text": comp_data.get("message_text", ""),
                    "message_photo": comp_data.get("message_photo", ""),
                    "interval": comp_data.get("interval", 5),
                    "created_at": comp_data.get("created_at", datetime.now().isoformat()),
                    "status": comp_data.get("status", "stopped")
                }
        
        with open(COMPANIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(companies_to_save, f, ensure_ascii=False, indent=2)
        
        # Foydalanuvchilarni saqlash
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(all_users), f)
    except Exception as e:
        print(f"Ma'lumotlarni saqlashda xatolik: {e}")

# --- Majburiy obuna tekshirish ---
async def check_subscription(user_id, context):
    """Foydalanuvchi obuna bo'lganligini tekshiradi"""
    try:
        member = await context.bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Obuna tekshirishda xatolik: {e}")
        return False

def get_subscription_keyboard():
    """Obuna tugmalari"""
    keyboard = [
        [InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=f"https://t.me/{REQUIRED_CHANNEL[1:]}")],
        [InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_subscription")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_subscription_message():
    """Obuna xabari"""
    subscription_text = f"""🔒 Botdan foydalanish uchun kanalimizga obuna bo'ling!

📢 Kanal: {REQUIRED_CHANNEL}

🎯 Kanalimizda:
• Yangi funksiyalar haqida xabar
• Foydali maslahatlar
• Bot yangilanishlari
• Texnik yordam

👇 Avval obuna bo'ling, keyin "✅ Obunani tekshirish" tugmasini bosing"""
    return subscription_text

# --- Admin tekshirish ---
def is_admin(user):
    return user.username == ADMIN_USERNAME

# --- Ban/unban funksiyalari ---
BAN_FILE = os.path.join(DATA_DIR, "banned_users.json")

def load_banned_users():
    if os.path.exists(BAN_FILE):
        with open(BAN_FILE, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    return set()

def save_banned_users(banned_users):
    with open(BAN_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(banned_users), f)

def ban_user(user_id):
    banned_users = load_banned_users()
    banned_users.add(str(user_id))
    save_banned_users(banned_users)
    # Remove from active users if exists
    if str(user_id) in all_users:
        all_users.remove(str(user_id))
        save_data()

def unban_user(user_id):
    banned_users = load_banned_users()
    if str(user_id) in banned_users:
        banned_users.remove(str(user_id))
        save_banned_users(banned_users)
        # Add back to active users if not already there
        if str(user_id) not in all_users:
            all_users.add(str(user_id))
            save_data()

# Yuklab olish
banned_users = load_banned_users()

# --- Yordamchi funksiyalar ---
def get_welcome_message(name):
    welcome_text = f"""Salom <b>{name}</b>! 👋

👇 Quyidagilardan birini tanlang:
"""
    return welcome_text

def get_main_menu(is_admin_user=False):
    keyboard = [
        [InlineKeyboardButton("📱 Hissobraqam qo'shish", callback_data="create_session")],
        [InlineKeyboardButton("🏢 Avtoxabarchi yaratish", callback_data="create_company")],
        [InlineKeyboardButton("📂 Mening xabarchlarim", callback_data="my_companies")],
        [InlineKeyboardButton("📂 Mening hissobraqamlarim", callback_data="my_sessions")]
    ]
    
    if is_admin_user:
        keyboard.append([InlineKeyboardButton("🔧 Admin Panel", callback_data="admin_panel")])
    
    return InlineKeyboardMarkup(keyboard)

def get_admin_menu():
    keyboard = [
        [InlineKeyboardButton("👥 Foydalanuvchilar soni", callback_data="admin_users")],
        [InlineKeyboardButton("📊 Sessiyalar soni", callback_data="admin_sessions")],
        [InlineKeyboardButton("🏢 Hammaga xabar yuborish", callback_data="admin_broadcast")],
        [InlineKeyboardButton("📝 Welcome message tahrirlash", callback_data="admin_welcome")],
        [InlineKeyboardButton("🚫 Foydalanuvchini ban qilish", callback_data="admin_ban")],
        [InlineKeyboardButton("✅ Foydalanuvchini unban qilish", callback_data="admin_unban")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_company_control_menu(company_name, status):
    keyboard = []
    if status == "running":
        keyboard.append([InlineKeyboardButton("⏸️ To'xtatish", callback_data=f"pause_{company_name}")])
    else:
        keyboard.append([InlineKeyboardButton("▶️ Ishga tushirish", callback_data=f"start_{company_name}")])
    
    keyboard.extend([
        [InlineKeyboardButton("🗑️ O'chirish", callback_data=f"delete_{company_name}")],
        [InlineKeyboardButton("📊 Statistika", callback_data=f"stats_{company_name}")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="my_companies")]
    ])
    return InlineKeyboardMarkup(keyboard)

def clean_code(code_str):
    return code_str.replace(".", "").strip()

# --- Ma'lumotlarni yuklash ---
load_data()

# --- Bot boshlanishi ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    
    # Foydalanuvchilarga qo'shish
    if user_id not in all_users:
        all_users.add(user_id)
        save_data()
    
    # Admin tekshirish
    admin_status = is_admin(user)
    
    # Obunani tekshirish
    if not admin_status:
        is_subscribed = await check_subscription(user.id, context)
        if not is_subscribed:
            await update.message.reply_html(
                get_subscription_message(),
                reply_markup=get_subscription_keyboard()
            )
            return
    
    await update.message.reply_html(
        get_welcome_message(user.full_name),
        reply_markup=get_main_menu(admin_status)
    )

# --- Inline tugmalarni boshqarish ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    user_id = str(user.id)

    # Obunani tekshirish tugmasi
    if query.data == "check_subscription":
        if not is_admin(user):
            is_subscribed = await check_subscription(int(user_id), context)
            if not is_subscribed:
                error_message = "❌ Siz hali kanalga obuna bo'lmagan ekan!\n\n" + get_subscription_message()
                await query.message.edit_text(
                    error_message,
                    reply_markup=get_subscription_keyboard()
                )
                return ConversationHandler.END
        
        # Obuna tasdiqlandi
        admin_status = is_admin(user)
        success_message = f"✅ Obuna tasdiqlandi!\n\n{get_welcome_message(user.full_name)}"
        await query.message.edit_text(
            success_message,
            reply_markup=get_main_menu(admin_status)
        )
        return ConversationHandler.END

    # Admin bo'lmagan foydalanuvchilar uchun obuna tekshirish
    if not is_admin(user):
        is_subscribed = await check_subscription(int(user_id), context)
        if not is_subscribed:
            await query.message.edit_text(
                get_subscription_message(),
                reply_markup=get_subscription_keyboard()
            )
            return ConversationHandler.END

    if query.data == "create_session":
        await query.message.reply_text("📱 Telefon raqamingizni xalqaro formatda yuboring (masalan: +998901234567):")
        return PHONE

    elif query.data == "my_sessions":
        files = [f for f in os.listdir(SESSION_DIR) if f.startswith(user_id)]
        if files:
            msg = "📂 Mavjud sessiyalar:\n" + "\n".join(f"✅ {f}" for f in files)
        else:
            msg = "⛔ Sessiyalar topilmadi."
        await query.message.reply_text(msg)
        return ConversationHandler.END

    elif query.data == "create_company":
        await query.message.reply_text("🏢 Kompaniya nomini kiriting:")
        return COMPANY_NAME

    elif query.data == "my_companies":
        companies = user_companies.get(user_id, {})
        if companies:
            text = "🏢 Sizning kompaniyalaringiz:\n\n"
            keyboard = []
            for comp_name, comp in companies.items():
                status = comp.get("status", "stopped")
                status_emoji = "🟢" if status == "running" else "🔴"
                text += f"{status_emoji} **{comp_name}**\n"
                text += f"   └ Guruh: {comp.get('group', 'N/A')}\n"
                interval_value = comp.get('interval', 'N/A')
                text += f"   └ Interval: {interval_value} daqiqa\n\n"
                
                keyboard.append([InlineKeyboardButton(
                    f"{status_emoji} {comp_name}", 
                    callback_data=f"manage_{comp_name}"
                )])
            
            keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")])
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.message.edit_text("⛔ Sizda hali kompaniya yo'q.")
        return ConversationHandler.END

    elif query.data.startswith("manage_"):
        comp_name = query.data[7:]
        companies = user_companies.get(user_id, {})
        comp = companies.get(comp_name)
        if comp:
            status = comp.get("status", "stopped")
            status_text = "🟢 Faol" if status == "running" else "🔴 To'xtatilgan"
            text = f"🏢 **{comp_name}** boshqaruvi\n\n"
            text += f"📊 Status: {status_text}\n"
            text += f"🔗 Guruh: {comp.get('group', 'N/A')}\n"
            interval_value = comp.get('interval', 'N/A')
            text += f"⏱️ Interval: {interval_value} daqiqa\n"
            created_date = comp.get('created_at', 'N/A')[:10]
            text += f"📅 Yaratilgan: {created_date}\n"
            
            await query.message.edit_text(
                text, 
                reply_markup=get_company_control_menu(comp_name, status)
            )

    elif query.data.startswith("start_"):
        comp_name = query.data[6:]
        await start_company_by_name(user_id, comp_name, query.message)

    elif query.data.startswith("pause_"):
        comp_name = query.data[6:]
        await pause_company_by_name(user_id, comp_name, query.message)

    elif query.data.startswith("delete_"):
        comp_name = query.data[7:]
        await delete_company_by_name(user_id, comp_name, query.message)

    elif query.data.startswith("stats_"):
        comp_name = query.data[6:]
        await show_company_stats(user_id, comp_name, query.message)

    # Admin paneli
    elif query.data == "admin_panel" and is_admin(user):
        await query.message.edit_text("🔧 **Admin Panel**", reply_markup=get_admin_menu())

    elif query.data == "admin_users" and is_admin(user):
        users_count = len(all_users)
        admin_users_text = f"👥 Jami foydalanuvchilar: **{users_count}**"
        await query.message.edit_text(admin_users_text, reply_markup=get_admin_menu())

    elif query.data == "admin_sessions" and is_admin(user):
        session_files = [f for f in os.listdir(SESSION_DIR) if f.endswith('.txt')]
        sessions_count = len(session_files)
        admin_sessions_text = f"📊 Jami sessiyalar: **{sessions_count}**"
        await query.message.edit_text(admin_sessions_text, reply_markup=get_admin_menu())

    elif query.data == "admin_broadcast" and is_admin(user):
        try:
            # Clear any existing conversation state
            if 'broadcast' in context.user_data:
                del context.user_data['broadcast']
                
            # Send a new message to avoid editing issues
            sent_msg = await query.message.reply_text(
                "📢 Hammaga yubormoqchi bo'lgan xabaringizni yuboring:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_broadcast")],
                ])
            )
            
            # Store the status message ID for later updates
            context.user_data['broadcast'] = {
                'status_message_id': sent_msg.message_id,
                'chat_id': sent_msg.chat_id
            }
            
            return ADMIN_BROADCAST
            
        except Exception as e:
            print(f"Error in admin_broadcast setup: {e}")
            await query.message.reply_text("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")
            return ConversationHandler.END

    elif query.data == "confirm_broadcast" and is_admin(user):
        if 'broadcast_text' in context.user_data:
            broadcast_text = context.user_data['broadcast_text']
            
            # Show sending status
            status_message = await query.message.edit_text("📤 Xabar yuborilmoqda...")
            
            try:
                # Send the broadcast
                success, failed = await send_broadcast(context, broadcast_text, status_message)
                
                # Show results
                await query.message.reply_text(
                    f"✅ Xabar yuborish yakunlandi!\n\n"
                    f"✅ Muvaffaqiyatli: {success}\n"
                    f"❌ Xatoliklar: {failed}\n"
                    f"📊 Jami: {success + failed}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]
                    ])
                )
            except Exception as e:
                print(f"Xabar yuborishda xatolik: {e}")
                await query.message.reply_text(
                    f"❌ Xabar yuborishda xatolik yuz berdi: {str(e)}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]
                    ])
                )
            finally:
                # Clean up
                if 'broadcast_text' in context.user_data:
                    del context.user_data['broadcast_text']
        
        return ConversationHandler.END
        
    elif query.data == "cancel_broadcast" and is_admin(user):
        if 'broadcast_text' in context.user_data:
            del context.user_data['broadcast_text']
            
        await query.message.edit_text(
            "❌ Xabar yuborish bekor qilindi.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]
            ])
        )
        return ConversationHandler.END
        
    elif query.data == "admin_welcome" and is_admin(query.from_user):
        current_welcome = ""
        if os.path.exists(WELCOME_FILE):
            with open(WELCOME_FILE, 'r', encoding='utf-8') as f:
                current_welcome = f.read()
                
        await query.message.edit_text(
            f"✏️ Yangi xush kelish xabarini yuboring. Hozirgi xabar:\n\n{current_welcome}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]
            ])
        )
        return ADMIN_WELCOME
        
    elif query.data == "admin_ban" and is_admin(user):
        context.user_data['awaiting_ban'] = True
        await query.message.edit_text(
            "🚫 Ban qilmoqchi bo'lgan foydalanuvchi ID sini yuboring:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]
            ])
        )
        return "AWAITING_BAN_USER_ID"
        
    elif query.data == "admin_unban" and is_admin(user):
        context.user_data['awaiting_unban'] = True
        banned = load_banned_users()
        if not banned:
            await query.message.edit_text(
                "ℹ️ Banlangan foydalanuvchilar topilmadi.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]
                ])
            )
            return ConversationHandler.END
            
        banned_list = "\n".join(f"• `{user_id}`" for user_id in banned)
        await query.message.edit_text(
            f"🔍 Ban olib tashlash uchun foydalanuvchi ID sini yuboring:\n\nBanned users:\n{banned_list}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]
            ]),
            parse_mode='Markdown'
        )
        return "AWAITING_UNBAN_USER_ID"
        
    elif query.data == "back_to_admin":
        await query.message.edit_text(
            "🔧 Admin Panel",
            reply_markup=get_admin_menu()
        )
        return ConversationHandler.END
        
    elif query.data == "back_to_main":
        # Clean up any broadcast state
        if 'broadcast' in context.user_data:
            del context.user_data['broadcast']
            
        admin_status = is_admin(user)
        await query.message.edit_text(
            get_welcome_message(user.full_name),
            reply_markup=get_main_menu(admin_status)
        )

    return ConversationHandler.END

# --- Kompaniya boshqaruvi ---
async def start_company_by_name(user_id, company_name, message):
    companies = user_companies.get(user_id, {})
    comp = companies.get(company_name)
    
    if not comp:
        await message.edit_text("❌ Kompaniya topilmadi.")
        return

    # Sessiya faylini tekshirish
    session_file = os.path.join(SESSION_DIR, f"{user_id}_session.txt")
    if not os.path.exists(session_file):
        await message.edit_text("❌ Sessiya topilmadi, avval sessiya yarating.")
        return

    try:
        with open(session_file, "r") as f:
            string_session = f.read()

        client = TelegramClient(StringSession(string_session), API_ID, API_HASH)
        await client.start()

        # Xabar yuborish vazifasini yaratish
        async def send_messages():
            while True:
                try:
                    message_photo = comp.get("message_photo")
                    message_text = comp.get("message_text", "")
                    
                    if message_photo:
                        await client.send_file(
                            comp["group"], 
                            message_photo, 
                            caption=message_text
                        )
                    else:
                        await client.send_message(comp["group"], message_text)
                    
                    interval_minutes = comp.get("interval", 5)
                    await asyncio.sleep(interval_minutes * 60)
                except FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    print(f"Kompaniya {company_name}da xatolik: {e}")
                    interval_minutes = comp.get("interval", 5)
                    await asyncio.sleep(interval_minutes * 60)

        task = asyncio.create_task(send_messages())
        
        # Faol kompaniyalar ro'yxatiga qo'shish
        active_companies[f"{user_id}_{company_name}"] = {
            "task": task,
            "client": client,
            "user_id": user_id,
            "company_name": company_name
        }

        # Statusni yangilash
        comp["status"] = "running"
        save_data()

        interval_value = comp.get('interval', 5)
        success_text = f"✅ {company_name} ishga tushirildi!\n\nHar {interval_value} daqiqada xabar yuboriladi."
        await message.edit_text(
            success_text,
            reply_markup=get_company_control_menu(company_name, "running")
        )

    except Exception as e:
        error_text = f"❌ Xatolik: {e}"
        await message.edit_text(error_text)

async def pause_company_by_name(user_id, company_name, message):
    key = f"{user_id}_{company_name}"
    active_comp = active_companies.get(key)
    
    if active_comp:
        # Taskni to'xtatish
        active_comp["task"].cancel()
        
        # Clientni yopish
        try:
            await active_comp["client"].disconnect()
        except:
            pass
        
        # Faol ro'yxatdan o'chirish
        del active_companies[key]
        
        # Statusni yangilash
        companies = user_companies.get(user_id, {})
        if company_name in companies:
            companies[company_name]["status"] = "stopped"
            save_data()

        pause_text = f"⏸️ **{company_name}** to'xtatildi."
        await message.edit_text(
            pause_text,
            reply_markup=get_company_control_menu(company_name, "stopped")
        )
    else:
        await message.edit_text("❌ Kompaniya faol emas.")

async def delete_company_by_name(user_id, company_name, message):
    # Avval to'xtatish
    await pause_company_by_name(user_id, company_name, message)
    
    # Ma'lumotlar bazasidan o'chirish
    companies = user_companies.get(user_id, {})
    if company_name in companies:
        del companies[company_name]
        save_data()
        
        delete_text = f"🗑️ **{company_name}** o'chirildi."
        await message.edit_text(delete_text)
    else:
        await message.edit_text("❌ Kompaniya topilmadi.")

async def show_company_stats(user_id, company_name, message):
    companies = user_companies.get(user_id, {})
    comp = companies.get(company_name)
    
    if comp:
        text = f"📊 **{company_name}** statistikasi\n\n"
        created_date = comp.get('created_at', 'N/A')[:19]
        text += f"📅 Yaratilgan: {created_date}\n"
        status_text = "🟢 Faol" if comp.get('status') == 'running' else "🔴 To'xtatilgan"
        text += f"📊 Status: {status_text}\n"
        text += f"🔗 Guruh: {comp.get('group', 'N/A')}\n"
        interval_value = comp.get('interval', 'N/A')
        text += f"⏱️ Interval: {interval_value} daqiqa\n"
        message_length = len(comp.get('message_text', ''))
        text += f"📝 Xabar uzunligi: {message_length} belgi\n"
        has_photo = "Bor" if comp.get('message_photo') else "Yo'q"
        text += f"🖼️ Rasm: {has_photo}\n"
        
        await message.edit_text(
            text,
            reply_markup=get_company_control_menu(company_name, comp.get("status", "stopped"))
        )

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        print(f"Admin broadcast started by user: {user.id} ({user.username or 'no username'})")
        
        if not is_admin(user):
            print("Access denied: User is not admin")
            return ConversationHandler.END
        
        if not update.message or not update.message.text:
            print("Error: No message text found")
            await update.message.reply_text("❌ Xabar matni topilmadi!")
            return ConversationHandler.END
        
        message_text = update.message.text
        sent_count = 0
        failed_count = 0
        failed_users = []
        
        # Get status message info from context
        broadcast_data = context.user_data.get('broadcast', {})
        status_message_id = broadcast_data.get('status_message_id')
        chat_id = broadcast_data.get('chat_id')
        
        if not status_message_id or not chat_id:
            # Fallback if context data is missing
            status_message = await update.message.reply_text("📤 Xabar yuborilmoqda...")
            status_message_id = status_message.message_id
            chat_id = status_message.chat_id
        
        total_users = len(all_users)
        print(f"Starting broadcast to {total_users} users")
        
        # Update status message
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_message_id,
            text=f"📤 Xabar yuborilmoqda...\n0/{total_users} (0%)"
        )
        
        # Convert all_users to a list to avoid potential set modification during iteration
        users_list = list(all_users)
        print(f"DEBUG: Users to send to: {users_list}")
        
        # Send to each user
        for i, user_id in enumerate(users_list, 1):
            try:
                user_id_int = int(user_id)  # Ensure user_id is an integer
                print(f"DEBUG: Attempting to send to user_id: {user_id_int} (type: {type(user_id_int)})")
                
                broadcast_text = f"📢 **Admin xabari:**\n\n{message_text}"
                print(f"DEBUG: Sending message to {user_id_int}")
                
                # Try sending with a timeout
                try:
                    await asyncio.wait_for(
                        context.bot.send_message(chat_id=user_id_int, text=broadcast_text),
                        timeout=10.0
                    )
                    sent_count += 1
                    print(f"DEBUG: Successfully sent to {user_id_int}")
                except asyncio.TimeoutError:
                    error_msg = "Timeout while sending message"
                    print(f"DEBUG: {error_msg} to {user_id_int}")
                    failed_count += 1
                    failed_users.append(f"{user_id_int}: {error_msg}")
                    continue
                except Exception as send_error:
                    error_msg = str(send_error)
                    print(f"DEBUG: Error sending to {user_id_int}: {error_msg}")
                    failed_count += 1
                    failed_users.append(f"{user_id_int}: {error_msg}")
                    continue
                    
            except Exception as e:
                error_msg = str(e)
                print(f"DEBUG: Unexpected error with user_id {user_id}: {error_msg}")
                print(f"DEBUG: User ID type: {type(user_id)}, value: {user_id}")
                failed_count += 1
                failed_users.append(f"{user_id}: {error_msg}")
            
            # Update progress every 5 messages or if it's the last message
            if i % 5 == 0 or i == total_users:
                progress = int((i / total_users) * 100)
                progress_text = (
                    f"📤 Xabar yuborilmoqda...\n"
                    f"{i}/{total_users} ({progress}%)"
                    f"\n✓ Yuborildi: {sent_count}"
                    f"\n✗ Xato: {failed_count}"
                )
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_message_id,
                    text=progress_text
                )
        
        # Prepare final status
        final_text = (
            f"✅ Xabar yuborish tugadi!\n\n"
            f"📊 Jami yuborish urinishlari: {total_users}"
            f"\n✓ Yuborildi: {sent_count}"
            f"\n✗ Xato: {failed_count}"
        )
        
        # Add details about failed sends if any
        if failed_users:
            failed_details = "\n\nQuyidagi foydalanuvchilarga yuborib bo'lmadi:"
            for i, fail in enumerate(failed_users[:5], 1):
                failed_details += f"\n{i}. {fail}"
            if len(failed_users) > 5:
                failed_details += f"\n...va yana {len(failed_users) - 5} ta xato"
            final_text += failed_details
        
        # Send final status
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_message_id,
            text=final_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]
            ])
        )
        
        # Clean up
        if 'broadcast' in context.user_data:
            del context.user_data['broadcast']
            
        print("Broadcast completed successfully")
        return ConversationHandler.END
        
    except Exception as e:
        print(f"Error in admin_broadcast: {e}")
        try:
            await update.message.reply_text(
                "❌ Xabar yuborishda xatolik yuz berdi. Qaytadan urinib ko'ring.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Qayta urinish", callback_data="admin_broadcast")],
                    [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]
                ])
            )
        except:
            pass
        return ConversationHandler.END

# --- Sessiya yaratish uchun telefon ---
async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    
    # Obunani tekshirish
    if not is_admin(user):
        is_subscribed = await check_subscription(int(user_id), context)
        if not is_subscribed:
            await update.message.reply_html(
                get_subscription_message(),
                reply_markup=get_subscription_keyboard()
            )
            return ConversationHandler.END
    
    phone = update.message.text.strip()
    session_data[user_id] = {"phone": phone}

    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    try:
        await client.send_code_request(phone)
        session_data[user_id]["client"] = client
        await update.message.reply_text("✅ Kod yuborildi. Endi kodni kiriting 1.2.3.4.5. formatida kriting :")
        return CODE
    except Exception as e:
        error_text = f"❌ Xatolik: {e}"
        await update.message.reply_text(error_text)
        await client.disconnect()
        return ConversationHandler.END

# --- Kodni olish ---
async def get_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    code_raw = update.message.text.strip()
    code = clean_code(code_raw)
    data = session_data.get(user_id)
    client = data.get("client")

    try:
        await client.sign_in(data["phone"], code)
        string_session = client.session.save()
        file_path = os.path.join(SESSION_DIR, f"{user_id}_session.txt")
        with open(file_path, "w") as f:
            f.write(string_session)

        await update.message.reply_text("✅ Sessiya yaratildi va saqlandi!")
        await client.disconnect()
        return ConversationHandler.END

    except SessionPasswordNeededError:
        await update.message.reply_text("🔐 Iltimos, 2-bosqichli parolni kiriting:")
        return PASSWORD

    except Exception as e:
        await update.message.reply_text("❌ Kod xato, qaytadan urinib ko'ring")
        return CODE

# --- 2-bosqichli parolni olish ---
async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    password = update.message.text.strip()
    data = session_data.get(user_id)
    client = data.get("client")

    try:
        await client.sign_in(password=password)
        string_session = client.session.save()
        file_path = os.path.join(SESSION_DIR, f"{user_id}_session.txt")
        with open(file_path, "w") as f:
            f.write(string_session)

        await update.message.reply_text("✅ Sessiya yaratildi va saqlandi!")
    except Exception as e:
        error_text = f"❌ Parol noto'g'ri 1.1.1.1.1. formatni tekshiring: {e}"
        await update.message.reply_text(error_text)
    finally:
        await client.disconnect()
        return ConversationHandler.END

# --- Kompaniya yaratish ---
async def get_company_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    
    # Obunani tekshirish
    if not is_admin(user):
        is_subscribed = await check_subscription(int(user_id), context)
        if not is_subscribed:
            await update.message.reply_html(
                get_subscription_message(),
                reply_markup=get_subscription_keyboard()
            )
            return ConversationHandler.END

    company_name = update.message.text.strip()
    
    # Kompaniya nomini tekshirish
    if user_id in user_companies and company_name in user_companies[user_id]:
        await update.message.reply_text("❌ Bu nom bilan kompaniya allaqachon mavjud. Boshqa nom tanlang:")
        return COMPANY_NAME
    
    company_data[user_id] = {"name": company_name}
    await update.message.reply_text("📝 Guruh/kanal manzilini kiriting (masalan: @mygroup yoki https://t.me/mygroup):")
    return COMPANY_GROUP

async def get_company_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    group = update.message.text.strip()
    
    company_data[user_id]["group"] = group
    await update.message.reply_text("📝 Yubormoqchi bo'lgan xabaringizni kiriting (matn yoki rasm bilan):")
    return COMPANY_MSG

async def get_company_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    message = update.message
    
    # Matn xabari
    if message.text:
        company_data[user_id]["message_text"] = message.text
        company_data[user_id]["message_photo"] = None
    
    # Rasm bilan xabar
    elif message.photo:
        # Eng yuqori sifatli rasmni olish
        photo = message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        
        # Rasm faylini saqlash
        photo_dir = os.path.join(DATA_DIR, "photos")
        if not os.path.exists(photo_dir):
            os.makedirs(photo_dir)
        
        photo_path = os.path.join(photo_dir, f"{user_id}_{photo.file_id}.jpg")
        await file.download_to_drive(photo_path)
        
        company_data[user_id]["message_photo"] = photo_path
        company_data[user_id]["message_text"] = message.caption or ""
    
    else:
        await update.message.reply_text("❌ Faqat matn yoki rasm yuboring. Qaytadan urinib ko'ring:")
        return COMPANY_MSG
    
    await update.message.reply_text("⏱️ Xabarlar orasidagi interval (daqiqada) kiriting (masalan: 5):")
    return COMPANY_INTERVAL

async def get_company_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    interval_text = update.message.text.strip()
    
    try:
        interval = int(interval_text)
        if interval < 1:
            await update.message.reply_text("❌ Interval kamida 1 daqiqa bo'lishi kerak:")
            return COMPANY_INTERVAL
        
        company_data[user_id]["interval"] = interval
        
        # Tasdiqlash xabari
        comp_data = company_data[user_id]
        confirmation_text = f"""✅ **Kompaniya ma'lumotlari:**

🏢 **Nom:** {comp_data['name']}
🔗 **Guruh:** {comp_data['group']}
📝 **Xabar:** {comp_data.get('message_text', 'Rasm bilan xabar')[:50]}...
⏱️ **Interval:** {interval} daqiqa

Barcha ma'lumotlar to'g'rimi?"""
        
        keyboard = [
            [InlineKeyboardButton("✅ Ha, saqlash", callback_data="save_company")],
            [InlineKeyboardButton("❌ Yo'q, qaytadan", callback_data="cancel_company")]
        ]
        
        await update.message.reply_text(
            confirmation_text, 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return COMPANY_CONFIRM
        
    except ValueError:
        await update.message.reply_text("❌ Faqat raqam kiriting (masalan: 5):")
        return COMPANY_INTERVAL

async def handle_company_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    
    if query.data == "save_company":
        # Kompaniyani saqlash
        comp_data = company_data.get(user_id, {})
        if comp_data:
            if user_id not in user_companies:
                user_companies[user_id] = {}
            
            user_companies[user_id][comp_data["name"]] = {
                "name": comp_data["name"],
                "group": comp_data["group"],
                "message_text": comp_data.get("message_text", ""),
                "message_photo": comp_data.get("message_photo"),
                "interval": comp_data["interval"],
                "created_at": datetime.now().isoformat(),
                "status": "stopped"
            }
            
            save_data()
            
            # Vaqtinchalik ma'lumotlarni tozalash
            if user_id in company_data:
                del company_data[user_id]
            
            success_text = f"✅ {comp_data['name']} kompaniyasi muvaffaqiyatli yaratildi!"
            admin_status = is_admin(query.from_user)
            await query.message.edit_text(
                success_text,
                reply_markup=get_main_menu(admin_status)
            )
        else:
            await query.message.edit_text("❌ Xatolik yuz berdi.")
    
    elif query.data == "cancel_company":
        # Kompaniya yaratishni bekor qilish
        if user_id in company_data:
            del company_data[user_id]
        
        admin_status = is_admin(query.from_user)
        await query.message.edit_text(
            get_welcome_message(query.from_user.full_name),
            reply_markup=get_main_menu(admin_status)
        )
    
    return ConversationHandler.END

# --- Broadcast funksiyasi ---
async def send_broadcast(context: ContextTypes.DEFAULT_TYPE, message_text: str, status_message):
    """Xabarni barcha foydalanuvchilarga yuborish"""
    success = 0
    failed = 0
    total = len(all_users)
    
    # Ma'lumotlarni yuklab olish
    load_data()
    
    for user_id in list(all_users):
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                parse_mode='HTML'
            )
            success += 1
            
            # Har 10 ta xabardan so'ng progress yangilash
            if (success + failed) % 10 == 0:
                try:
                    await status_message.edit_text(
                        f"📤 Xabar yuborilmoqda...\n\n"
                        f"✅ Yuborildi: {success}\n"
                        f"❌ Xatolik: {failed}\n"
                        f"📊 Jami: {total}"
                    )
                except:
                    pass
                    
        except Exception as e:
            print(f"Xabar yuborishda xatolik {user_id}: {e}")
            failed += 1
    
    return success, failed

# --- Admin funksiyalari ---
async def admin_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        return
        
    new_welcome = update.message.text
    
    # Save the new welcome message
    with open(WELCOME_FILE, 'w', encoding='utf-8') as f:
        f.write(new_welcome)
    
    await update.message.reply_text(
        "✅ Xush kelish xabari muvaffaqiyatli yangilandi!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]
        ])
    )
    return ConversationHandler.END

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        return
        
    # Save the message text to user_data
    context.user_data['broadcast_text'] = update.message.text
    
    # Send preview
    preview_text = f"📢 Xabar namoyishi:\n\n{update.message.text}"
    await update.message.reply_text(
        preview_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_broadcast")],
            [InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_broadcast")]
        ])
    )
    return ADMIN_BROADCAST

# --- Xabar handler ---
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
        
    text = update.message.text.strip()
    
    # Check for ban/unban states
    if 'awaiting_ban' in context.user_data:
        try:
            user_id = int(text)
            ban_user(user_id)
            await update.message.reply_text(
                f"✅ Foydalanuvchi {user_id} muvaffaqiyatli bloklandi!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]
                ])
            )
            del context.user_data['awaiting_ban']
        except ValueError:
            await update.message.reply_text(
                "❌ Noto'g'ri ID format. Faqat raqam kiriting.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]
                ])
            )
        return ConversationHandler.END
        
    elif 'awaiting_unban' in context.user_data:
        try:
            user_id = int(text)
            banned_users = load_banned_users()
            if str(user_id) in banned_users:
                unban_user(user_id)
                await update.message.reply_text(
                    f"✅ Foydalanuvchi {user_id} bandan olindi!",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]
                    ])
                )
            else:
                await update.message.reply_text(
                    f"ℹ️ {user_id} ID li foydalanuvchi bandan olingan emas.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]
                    ])
                )
            del context.user_data['awaiting_unban']
        except ValueError:
            await update.message.reply_text(
                "❌ Noto'g'ri ID format. Faqat raqam kiriting.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]
                ])
            )
        return ConversationHandler.END

# --- Botni ishga tushirish ---
def main():
    # Bot yaratish
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(button_handler)
        ],
        states={
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_code)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
            COMPANY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_company_name)],
            COMPANY_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_company_group)],
            COMPANY_MSG: [MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, get_company_message)],
            COMPANY_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_company_interval)],
            COMPANY_CONFIRM: [CallbackQueryHandler(handle_company_confirmation, pattern="^(save_company|cancel_company)$")],
            ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast)],
            ADMIN_WELCOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_welcome)],
            "AWAITING_BAN_USER_ID": [MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler)],
            "AWAITING_UNBAN_USER_ID": [MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler)],
        },
        fallbacks=[
            CommandHandler("start", start),
            CallbackQueryHandler(button_handler)
        ],
        per_message=False
    )
    
    application.add_handler(conv_handler)
    
    # Xabarlarni qayta ishlash
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    # Botni ishga tushirish
    print("🤖 Bot ishga tushdi...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()