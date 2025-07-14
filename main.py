import psycopg2
import telebot
import re
from datetime import datetime
from telebot import types

# Инициализация бота
bot = telebot.TeleBot('')  # Замените на ваш токен бота
admin_id =   # Замените на ID администратора

# Глобальные словари для хранения данных пользователей и состояний регистрации
user_data = {}
registration_state = {}

# Функция для получения соединения с базой данных
def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname="Rodionov",
            user="alex",
            password="1234",
            host="localhost",
            port="5432",
            client_encoding='UTF8'  # Установите кодировку клиента на UTF8
        )
        return conn
    except psycopg2.Error as e:
        print(f"Ошибка подключения к базе данных: {e}")
        return None

# Функция для проверки существования пользователя
def check_user_existence(chat_id):
    conn = get_db_connection()
    if conn is None:
        return False, "Не удалось подключиться к базе данных."

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT chat_id FROM users WHERE chat_id = %s", (chat_id,))
            result = cur.fetchone()
            if result:
                return True, None
            else:
                return False, None
    except psycopg2.Error as e:
        print(f"Ошибка при проверке пользователя: {e}")
        return False, "Произошла ошибка при проверке пользователя."
    finally:
        if conn is not None:
            conn.close()

# Функция для удаления пользователя из базы данных
def delete_user(chat_id):
    conn = get_db_connection()
    if conn is None:
        return "Не удалось подключиться к базе данных."

    try:
        with conn.cursor() as cur:
            # Удаляем данные из всех таблиц, связанных с пользователем
            cur.execute("DELETE FROM responses WHERE chat_id = %s", (chat_id,))
            cur.execute("DELETE FROM users WHERE chat_id = %s", (chat_id,))
            conn.commit()
        
        return "Ваш аккаунт был успешно удален."
    
    except psycopg2.Error as e:
        print(f"Ошибка при удалении пользователя: {e}")
        return "Произошла ошибка при удалении вашего аккаунта."
    finally:
        if conn is not None:
            conn.close()

# Функция для сброса состояния регистрации и удаления временных данных
def cancel_registration(chat_id):
    if chat_id in registration_state:
        del registration_state[chat_id]
    if chat_id in user_data:
        del user_data[chat_id]
    return "Регистрация отменена. Все введенные данные удалены."

# Функция для отправки главного меню с кнопками
def send_main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    if chat_id == admin_id:
        # Кнопки, которые видит только администратор
        markup.row(types.KeyboardButton('Отправить запрос 📢'))
        markup.row(types.KeyboardButton('Посмотреть всех пользователей 📋'))
        markup.row(types.KeyboardButton('Управление черным списком 🚫'))
    else:
        # Кнопки для обычных пользователей
        exists, _ = check_user_existence(chat_id)
        if exists:
            # Пользователь зарегистрирован
            markup.row(types.KeyboardButton('Прайс 💵'), types.KeyboardButton('Удалить аккаунт ❌'))
        else:
            # Пользователь не зарегистрирован
            markup.row(types.KeyboardButton('Прайс 💵'), types.KeyboardButton('Регистрация ⏰'))
    
    bot.send_message(chat_id, "Выберите действие:", reply_markup=markup)

# Функция для проверки, находится ли пользователь в черном списке
def is_user_blacklisted(chat_id):
    conn = get_db_connection()
    if conn is None:
        return False

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT chat_id FROM blacklist WHERE chat_id = %s", (chat_id,))
            result = cur.fetchone()
            return result is not None
    except psycopg2.Error as e:
        print(f"Ошибка при проверке черного списка: {e}")
        return False
    finally:
        if conn is not None:
            conn.close()

# Обработка команды /start
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    if is_user_blacklisted(chat_id):
        bot.send_message(chat_id, "Ваш аккаунт заблокирован💀. Вы не можете использовать этого бота❗️")
        return
    send_main_menu(chat_id)

# Обработка кнопки "Удалить аккаунт ❌"
@bot.message_handler(func=lambda message: message.text == 'Удалить аккаунт ❌')
def delete_account(message):
    chat_id = message.chat.id
    response_message = delete_user(chat_id)
    bot.send_message(chat_id, response_message)
    send_main_menu(chat_id)  # Обновляем меню после удаления аккаунта

# Функция для отображения всех пользователей
@bot.message_handler(func=lambda message: message.text == 'Посмотреть всех пользователей 📋' and message.chat.id == admin_id)
def view_all_users(message):
    conn = get_db_connection()
    if conn is None:
        bot.send_message(admin_id, "Не удалось подключиться к базе данных.")
        return

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT chat_id, full_name FROM users")
            users = cur.fetchall()
            if users:
                user_list = "\n".join([f"ФИО:{user[1]}\n ID: {user[0]}\n" for user in users])
                bot.send_message(admin_id, f"Список всех пользователей:\n\n{user_list}")
            else:
                bot.send_message(admin_id, "Нет зарегистрированных пользователей.")
    except psycopg2.Error as e:
        bot.send_message(admin_id, "Произошла ошибка при получении списка пользователей.")
        print(f"Ошибка: {e}")
    finally:
        if conn is not None:
            conn.close()

# Функция для управления черным списком
@bot.message_handler(func=lambda message: message.text == 'Управление черным списком 🚫' and message.chat.id == admin_id)
def manage_blacklist(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton('Добавить в черный список ➕'))
    markup.row(types.KeyboardButton('Удалить из черного списка ➖'))
    markup.row(types.KeyboardButton('Посмотреть черный список 💀'))  # Новая кнопка для черного списка
    markup.row(types.KeyboardButton('Назад ↩️'))
    
    bot.send_message(admin_id, "Выберите действие для управления черным списком:", reply_markup=markup)

# Функция для добавления пользователя в черный список
# Функция для добавления пользователя в черный список
def add_to_blacklist(user_id):
    conn = get_db_connection()
    if conn is None:
        return False

    try:
        with conn.cursor() as cur:
            # Добавляем пользователя в черный список
            cur.execute("INSERT INTO blacklist (chat_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
            conn.commit()
        return True
    except psycopg2.Error as e:
        print(f"Ошибка при добавлении пользователя в черный список: {e}")
        return False
    finally:
        if conn is not None:
            conn.close()

# Функция для удаления пользователя из черного списка
def remove_from_blacklist(user_id):
    conn = get_db_connection()
    if conn is None:
        return False

    try:
        with conn.cursor() as cur:
            # Удаляем пользователя из черного списка
            cur.execute("DELETE FROM blacklist WHERE chat_id = %s", (user_id,))
            conn.commit()
        return True
    except psycopg2.Error as e:
        print(f"Ошибка при удалении пользователя из черного списка: {e}")
        return False
    finally:
        if conn is not None:
            conn.close()

# Функция для добавления пользователя в черный список
@bot.message_handler(func=lambda message: message.text == 'Добавить в черный список ➕' and message.chat.id == admin_id)
def ask_user_id_to_blacklist(message):
    bot.send_message(admin_id, "Введите ID пользователя, которого хотите добавить в черный список:")
    bot.register_next_step_handler(message, handle_add_to_blacklist)

def handle_add_to_blacklist(message):
    try:
        user_id = int(message.text)
        success = add_to_blacklist(user_id)
        if success:
            bot.send_message(admin_id, f"Пользователь с ID {user_id} добавлен в черный список.")
        else:
            bot.send_message(admin_id, "Не удалось добавить пользователя в черный список.")
    except ValueError:
        bot.send_message(admin_id, "Некорректный ID. Пожалуйста, введите целое число.")

# Функция для удаления пользователя из черного списка
@bot.message_handler(func=lambda message: message.text == 'Удалить из черного списка ➖' and message.chat.id == admin_id)
def ask_user_id_to_remove_from_blacklist(message):
    bot.send_message(admin_id, "Введите ID пользователя, которого хотите удалить из черного списка:")
    bot.register_next_step_handler(message, handle_remove_from_blacklist)

def handle_remove_from_blacklist(message):
    try:
        user_id = int(message.text)
        success = remove_from_blacklist(user_id)
        if success:
            bot.send_message(admin_id, f"Пользователь с ID {user_id} удален из черного списка.")
        else:
            bot.send_message(admin_id, "Не удалось удалить пользователя из черного списка.")
    except ValueError:
        bot.send_message(admin_id, "Некорректный ID. Пожалуйста, введите целое число.")


# Функция для возврата в главное меню
@bot.message_handler(func=lambda message: message.text == 'Назад ↩️' and message.chat.id == admin_id)
def go_back(message):
    send_main_menu(admin_id)

# Функция для отображения всех пользователей в черном списке
@bot.message_handler(func=lambda message: message.text == 'Посмотреть черный список 💀' and message.chat.id == admin_id)
def view_blacklist(message):
    conn = get_db_connection()
    if conn is None:
        bot.send_message(admin_id, "Не удалось подключиться к базе данных.")
        return

    try:
        with conn.cursor() as cur:
            # Получаем пользователей из черного списка и их полные имена
            cur.execute("""
                SELECT b.chat_id, u.full_name
                FROM blacklist b
                LEFT JOIN users u ON b.chat_id = u.chat_id
            """)
            blacklist_users = cur.fetchall()
            if blacklist_users:
                user_list = "\n".join([f"ФИО: {user[1] if user[1] else 'Неизвестно'}\n ID: {user[0]}\n" for user in blacklist_users])
                bot.send_message(admin_id, f"Список пользователей в черном списке:\n\n{user_list}")
            else:
                bot.send_message(admin_id, "В черном списке нет пользователей.")
    except psycopg2.Error as e:
        bot.send_message(admin_id, "Произошла ошибка при получении списка пользователей в черном списке.")
        print(f"Ошибка: {e}")
    finally:
        if conn is not None:
            conn.close()



# Обработка кнопки "Регистрация ⏰"
@bot.message_handler(func=lambda message: message.text == 'Регистрация ⏰')
def ask_fullname(message):
    chat_id = message.chat.id
    exists, response_message = check_user_existence(chat_id)
    if exists:
        bot.send_message(chat_id, "Вы уже зарегистрированы✅")
        send_main_menu(chat_id)
    if is_user_blacklisted(chat_id):
        bot.send_message(chat_id, "Ваш аккаунт заблокирован. Вы не можете использовать этого бота❗️")
    else:
        # Устанавливаем состояние регистрации
        registration_state[chat_id] = 'awaiting_fullname'
        bot.send_message(chat_id, "Введите ваше ФИО:⬇️⬇️⬇️")
        bot.register_next_step_handler(message, activity_fullname)

def activity_fullname(message):
    chat_id = message.chat.id
    if chat_id in registration_state and registration_state[chat_id] == 'awaiting_fullname':
        user_data[chat_id] = {'full_name': message.text}
        registration_state[chat_id] = 'awaiting_phone'
        bot.send_message(chat_id, "ФИО записано✅.\n Введите номер телефона в формате +7XXXXXXXXXX:")
        bot.register_next_step_handler(message, activity_phone)
    else:
        bot.send_message(chat_id, "Регистрация отменена или завершена.")
    
def activity_phone(message):
    chat_id = message.chat.id
    phone = message.text

    # Проверка правильности номера телефона
    if not re.match(r'^\+7\d{10}$', phone):
        bot.send_message(chat_id, "Некорректно набран номер❗️\n Пожалуйста, введите номер в формате +7XXXXXXXXXX:")
        bot.register_next_step_handler(message, activity_phone)  # Повторная регистрация шага
        return
    
    user_data[chat_id]['phone'] = phone
    bot.send_message(chat_id, "Телефон записан✅.\n Введите ваш город проживания🏠:")
    bot.register_next_step_handler(message, activity_residence)


def activity_residence(message):
    chat_id = message.chat.id
    user_data[chat_id]['residence'] = message.text
    bot.send_message(chat_id, "Город записан✅\n Введите дату рождения в формате ДД.ММ.ГГГГ")
    bot.register_next_step_handler(message, activity_birthday)

def activity_birthday(message):
    chat_id = message.chat.id
    birthday_str = message.text

    try:
        birthday = datetime.strptime(birthday_str, "%d.%m.%Y")
        age = (datetime.now() - birthday).days // 365

        if age < 18:
            bot.send_message(chat_id, "Извините, но вам должно быть 🔞 лет и старше😔.")
            return  # Прекращаем процесс регистрации
    except ValueError:
        bot.send_message(chat_id, "Некорректная дата рождения❗️\n Пожалуйста, введите дату в формате ДД.ММ.ГГГГ:")
        bot.register_next_step_handler(message, activity_birthday)  # Повторная регистрация шага
        return
    
    user_data[chat_id]['birthday'] = birthday_str
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Да, применить✅", callback_data="apply_yes"))
    markup.add(types.InlineKeyboardButton("Нет, заполнить заново↩️", callback_data="apply_no"))
    
    bot.send_message(chat_id, "Дата рождения записана✅\n Применить данные?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["apply_yes", "apply_no"])
def handle_apply_query(call):
    chat_id = call.message.chat.id
    
    if call.data == "apply_yes":
        apply_data(call.message)
    elif call.data == "apply_no":
        reset_data(call.message)

def apply_data(message):
    conn = get_db_connection()
    if conn is None:
        bot.send_message(message.chat.id, "Произошла ошибка при подключении к базе данных.")
        return

    chat_id = message.chat.id
    try:
        with conn.cursor() as cur:
            user_info = user_data.get(chat_id)
            cur.execute("SELECT chat_id FROM users WHERE chat_id = %s", (chat_id,))
            if cur.fetchone() is not None:
                bot.send_message(chat_id, "Вы уже зарегистрированы✅")
                return
            
            cur.execute("""
                INSERT INTO users (chat_id, full_name, phone, residence, birthday) 
                VALUES (%s, %s, %s, %s, %s)
            """, (chat_id, user_info['full_name'], user_info['phone'], user_info['residence'], user_info['birthday']))
            
            conn.commit()
        
        bot.send_message(chat_id, "Регистрация выполнена🎉🎉🎉🎉\n Ждите заявки и как можно быстрее на них отликайтесь❕")
        
        # Обновляем данные пользователя
        user_data[chat_id]['registered'] = True
        
        bot.send_message(admin_id,
            f"Новая регистрация:\n"
            f"ID пользователя: {chat_id}\n"
            f"ФИО: {user_info['full_name']}\n"
            f"Телефон: {user_info['phone']}\n"
            f"Город: {user_info['residence']}\n"
            f"Дата рождения: {user_info['birthday']}"
        )
        
        send_main_menu(chat_id)
    except psycopg2.Error as e:
        bot.send_message(chat_id, "Произошла ошибка при сохранении данных.")
        print(f"Ошибка: {e}")
    finally:
        if conn is not None:
            conn.close()

def reset_data(message):
    chat_id = message.chat.id
    cancel_registration(chat_id)
    ask_fullname(message)

# Обработка кнопки "Прайс 💵"
@bot.message_handler(func=lambda message: message.text == 'Прайс 💵')
def send_price(message):
    chat_id = message.chat.id
    if is_user_blacklisted(chat_id):
        bot.send_message(chat_id, "Ваш аккаунт заблокирован💀. Вы не можете использовать этого бота❗️")
        return
    bot.send_message(chat_id, "В час плачу 100руб\n За косяки штраф 150 руб.")

# Обработка кнопки "Отправить запрос 📢"
@bot.message_handler(func=lambda message: message.text == 'Отправить запрос 📢' and message.chat.id == admin_id)
def send_request(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "Введите текст запроса:")
    bot.register_next_step_handler(message, ask_max_responses)

def ask_max_responses(message):
    request_text = message.text
    bot.send_message(message.chat.id, "Введите максимальное количество откликов:")
    bot.register_next_step_handler(message, handle_max_responses, request_text)

def handle_max_responses(message, request_text):
    max_responses = message.text
    
    # Проверка корректности ввода
    if not max_responses.isdigit() or int(max_responses) <= 0:
        bot.send_message(message.chat.id, "Некорректное количество откликов. Пожалуйста, введите положительное число.")
        bot.register_next_step_handler(message, handle_max_responses, request_text)
        return

    max_responses = int(max_responses)
    
    conn = get_db_connection()
    if conn is None:
        bot.send_message(message.chat.id, "Произошла ошибка при подключении к базе данных.")
        return

    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO requests (admin_id, request_text, response_count, max_responses) 
                VALUES (%s, %s, %s, %s) RETURNING request_id
            """, (admin_id, request_text, 0, max_responses))
            request_id = cur.fetchone()[0]
            conn.commit()
        
        bot.send_message(admin_id, f"Ваш запрос был успешно отправлен. ID запроса: {request_id}")
        send_request_to_users(request_id, request_text)
    except psycopg2.Error as e:
        bot.send_message(admin_id, "Произошла ошибка при отправке запроса.")
        print(f"Ошибка: {e}")
    finally:
        if conn is not None:
            conn.close()

def send_request_to_users(request_id, request_text):
    conn = get_db_connection()
    if conn is None:
        bot.send_message(admin_id, "Произошла ошибка при подключении к базе данных.")
        return

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT chat_id FROM users")
            users = cur.fetchall()
            for user in users:
                chat_id = user[0]
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("Откликнуться", callback_data=f"response_{request_id}"))
                
                bot.send_message(chat_id, f"Новый запрос:\n {request_text}", reply_markup=markup)
    except psycopg2.Error as e:
        bot.send_message(admin_id, "Произошла ошибка при отправке запроса пользователям.")
        print(f"Ошибка: {e}")
    finally:
        if conn is not None:
            conn.close()
 # Проверяем, находится ли пользователь в черном списке
@bot.callback_query_handler(func=lambda call: call.data.startswith("response_"))
def handle_response(call):
    request_id = int(call.data.split("_")[1])
    chat_id = call.message.chat.id

    if is_user_blacklisted(chat_id):
        bot.send_message(chat_id, "Вы не можете откликнуться на эту заявку, так как вы находитесь в черном списке.")
        return

    conn = get_db_connection()
    if conn is None:
        bot.send_message(chat_id, "Произошла ошибка при подключении к базе данных.")
        return

    try:
        with conn.cursor() as cur:
            # Проверяем, откликался ли уже пользователь на этот запрос
            cur.execute("SELECT * FROM responses WHERE request_id = %s AND chat_id = %s", (request_id, chat_id))
            if cur.fetchone():
                bot.send_message(chat_id, "Вы уже откликнулись на этот запрос.")
                return

            # Получаем текущее количество откликов и максимальное количество откликов
            cur.execute("SELECT response_count, max_responses FROM requests WHERE request_id = %s", (request_id,))
            result = cur.fetchone()
            if not result:
                bot.send_message(chat_id, "Запрос не найден.")
                return

            response_count, max_responses = result

            # Если количество откликов достигло максимума, отклоняем новые отклики
            if response_count >= max_responses:
                bot.send_message(chat_id, "Извините, на заявку уже откликнулись.😔")
                return

            # Сохраняем отклик в базе данных
            cur.execute("""
                INSERT INTO responses (request_id, chat_id) 
                VALUES (%s, %s)
            """, (request_id, chat_id))
            conn.commit()

            # Обновляем количество откликов в таблице requests
            cur.execute("""
                UPDATE requests 
                SET response_count = response_count + 1 
                WHERE request_id = %s
            """, (request_id,))
            conn.commit()

            # Получаем полную информацию о пользователе, откликнувшемся на заявку
            cur.execute("SELECT full_name, phone, residence, birthday FROM users WHERE chat_id = %s", (chat_id,))
            user_info = cur.fetchone()

            if user_info:
                full_name, phone, residence, birthday = user_info
                
                # Отправляем администратору полные данные пользователя
                bot.send_message(
                    admin_id,
                    f"Пользователь откликнулся на заявку {request_id}:\n\n"
                    f"ФИО: {full_name}\n"
                    f"Телефон: {phone}\n"
                    f"Город: {residence}\n"
                    f"Дата рождения: {birthday}\n"
                    f"ID пользователя: {chat_id}"
                )
            
            bot.send_message(chat_id, "Вы согласились на заявку✅.\n Ожидайте звонка от специалиста.")

            # Обновляем количество откликов
            response_count += 1

            # Если достигнуто максимальное количество откликов, закрываем заявку и уведомляем администратора
            if response_count >= max_responses:
                cur.execute("""
                    UPDATE requests 
                    SET response_count = %s, is_closed = TRUE 
                    WHERE request_id = %s
                """, (response_count, request_id))
                conn.commit()

                bot.send_message(admin_id, f"Заявка: {request_id}\n получила максимальное количество откликов и теперь закрыта.")
        
    except psycopg2.Error as e:
        bot.send_message(chat_id, "Произошла ошибка при сохранении вашего ответа.")
        print(f"Ошибка: {e}")
    finally:
        if conn is not None:
            conn.close()

# Запуск бота
bot.polling(none_stop=True)
