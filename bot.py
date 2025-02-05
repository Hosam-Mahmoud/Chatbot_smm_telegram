import logging
import telebot
import mysql.connector
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import time

# إعداد التسجيل لتسجيل الأخطاء
logging.basicConfig(level=logging.INFO)

# إعدادات البوت
TOKEN = "7745789981:AAEI5LcwnS0MWYsba_XKded-oEmBLyjSrcQ"  # ضع توكن البوت هنا
ADMIN_ID = 5229631462  # ضع معرف الأدمن هنا
bot = telebot.TeleBot(TOKEN)

# محاولة الاتصال بقاعدة البيانات
while True:
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="smm_bot"
        )
        cursor = conn.cursor()
        logging.info("✅ تم الاتصال بقاعدة البيانات بنجاح.")
        break
    except mysql.connector.Error as e:
        logging.error(f"❌ فشل الاتصال بقاعدة البيانات: {e}, إعادة المحاولة...")
        time.sleep(5)

# إنشاء جدول الطلبات إذا لم يكن موجودًا
cursor.execute('''
CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT,
    service VARCHAR(255),
    quantity INT,
    price FLOAT,
    total_price FLOAT,
    status VARCHAR(50) DEFAULT 'قيد المعالجة',
    proof TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')
conn.commit()

# ** القائمة الرئيسية **
def main_menu_markup(user_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🛒 طلب جديد"))
    markup.add(KeyboardButton("📋 تتبع طلب"))
    if user_id == ADMIN_ID:
        markup.add(KeyboardButton("⚙️ إدارة الطلبات"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(
        message.chat.id,
        "👋 مرحبًا بك في البوت! يرجى اختيار أحد الخيارات:",
        reply_markup=main_menu_markup(message.chat.id)
    )

# ** تقديم طلب جديد **
@bot.message_handler(func=lambda message: message.text == "🛒 طلب جديد")
def new_order(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📈 متابعين", callback_data="service_followers"))
    markup.add(InlineKeyboardButton("👀 مشاهدات", callback_data="service_views"))
    bot.send_message(message.chat.id, "🔽 اختر الخدمة المطلوبة:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("service_"))
def select_quantity(call):
    service = "متابعين" if call.data == "service_followers" else "مشاهدات"
    msg = bot.send_message(call.message.chat.id, f"🔢 أدخل الكمية المطلوبة لـ {service}:")
    bot.register_next_step_handler(msg, lambda m: confirm_order(m, service))

def confirm_order(message, service):
    try:
        quantity = int(message.text.strip())
        price_per_unit = 0.05  # سعر الوحدة
        total_price = quantity * price_per_unit
        cursor.execute("INSERT INTO orders (user_id, service, quantity, price, total_price, status) VALUES (%s, %s, %s, %s, %s, 'قيد المعالجة')", 
                       (message.chat.id, service, quantity, price_per_unit, total_price))
        conn.commit()
        order_id = cursor.lastrowid
        bot.send_message(message.chat.id, f"✅ تم إنشاء الطلب رقم {order_id} بنجاح! السعر الإجمالي: {total_price}$.
🖼 أرسل صورة إثبات الدفع:")
        bot.register_next_step_handler(message, lambda m: upload_proof(m, order_id))
    except ValueError:
        bot.send_message(message.chat.id, "❌ أدخل رقمًا صحيحًا.")

# ** إثبات الدفع **
def upload_proof(message, order_id):
    if message.photo:
        file_id = message.photo[-1].file_id
        cursor.execute("UPDATE orders SET proof=%s WHERE id=%s", (file_id, order_id))
        conn.commit()

        cursor.execute("SELECT service, quantity, price, total_price, created_at FROM orders WHERE id=%s", (order_id,))
        order = cursor.fetchone()
        if order:
            service, quantity, price, total_price, created_at = order
            admin_message = f"📌 طلب جديد رقم {order_id}\n📌 الخدمة: {service}\n🔢 الكمية: {quantity}\n💰 السعر: {price}$\n💵 الإجمالي: {total_price}$\n📅 التاريخ: {created_at}\n🖼 إثبات الدفع:"
            bot.send_message(ADMIN_ID, admin_message)
            bot.send_photo(ADMIN_ID, file_id)
        
        bot.send_message(message.chat.id, "✅ تم إرسال إثبات الدفع، جاري المراجعة.")
    else:
        bot.send_message(message.chat.id, "❌ يرجى إرسال صورة لإثبات الدفع.")

# ** تتبع الطلب **
@bot.message_handler(func=lambda message: message.text == "📋 تتبع طلب")
def track_order(message):
    msg = bot.send_message(message.chat.id, "📌 أدخل رقم الطلب:")
    bot.register_next_step_handler(msg, check_order_status)

def check_order_status(message):
    order_id = message.text.strip()
    cursor.execute("SELECT status FROM orders WHERE id=%s", (order_id,))
    order = cursor.fetchone()
    if order:
        bot.send_message(message.chat.id, f"🔍 حالة الطلب {order_id}: {order[0]}")
    else:
        bot.send_message(message.chat.id, "❌ رقم الطلب غير صحيح.")

# ** إدارة الطلبات (للأدمن فقط) **
@bot.message_handler(func=lambda message: message.text == "⚙️ إدارة الطلبات" and message.chat.id == ADMIN_ID)
def admin_menu(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("✏️ تحديث حالة طلب"), KeyboardButton("🔙 رجوع"))
    bot.send_message(message.chat.id, "⚙️ اختر الإجراء:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "✏️ تحديث حالة طلب" and message.chat.id == ADMIN_ID)
def update_order_status(message):
    msg = bot.send_message(message.chat.id, "📌 أدخل رقم الطلب:")
    bot.register_next_step_handler(msg, ask_new_status)

def ask_new_status(message):
    order_id = message.text.strip()
    cursor.execute("SELECT * FROM orders WHERE id=%s", (order_id,))
    if cursor.fetchone():
        markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add("✅ مكتمل", "⏳ قيد التنفيذ", "❌ مرفوض")
        msg = bot.send_message(message.chat.id, "🔄 اختر الحالة الجديدة:", reply_markup=markup)
        bot.register_next_step_handler(msg, lambda m: save_new_status(m, order_id))
    else:
        bot.send_message(message.chat.id, "❌ رقم الطلب غير صحيح.")

def save_new_status(message, order_id):
    new_status = message.text.strip()
    if new_status in ["✅ مكتمل", "⏳ قيد التنفيذ", "❌ مرفوض"]:
        cursor.execute("UPDATE orders SET status=%s WHERE id=%s", (new_status, order_id))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ تم تحديث حالة الطلب {order_id} إلى: {new_status}")
    else:
        bot.send_message(message.chat.id, "❌ حالة غير صالحة. يرجى اختيار حالة صحيحة.")

# تشغيل البوت
bot.polling(none_stop=True)
