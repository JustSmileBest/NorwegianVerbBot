import pandas as pd
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, JobQueue
from telegram.ext.filters import Text, Command
import asyncio
from datetime import datetime
import os  # Добавляем импорт os для работы с переменными окружения

# Получение токена из переменной окружения
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("Токен бота не задан. Установите переменную окружения TOKEN.")

# Путь к файлам с данными
VERBS_FILE_PATH = '1_norwegian_verbs.csv'
SUGGESTIONS_FILE_PATH = 'Suggestions.csv'
CONTACTS_FILE_PATH = '1_Kontakt.csv'

# Чтение данных из CSV с обработкой ошибок
print("Чтение CSV файла с глаголами...")
try:
    df_verbs = pd.read_csv(VERBS_FILE_PATH)
except FileNotFoundError:
    print("Файл с глаголами не найден, создаём новый...")
    df_verbs = pd.DataFrame(columns=[
        'Infinitiv (инфинитив)',
        'Presens (настоящее время)',
        'Preteritum (прошедшее время)',
        'Presens perfektum (причастие прошедшего времени)',
        'Перевод'
    ])
    df_verbs.to_csv(VERBS_FILE_PATH, index=False, encoding='utf-8')

print("Чтение CSV файла с предложениями...")
try:
    df_suggestions = pd.read_csv(SUGGESTIONS_FILE_PATH)
except FileNotFoundError:
    print("Файл с предложениями не найден, создаём новый...")
    df_suggestions = pd.DataFrame(columns=[
        'Infinitiv (инфинитив)',
        'Presens (настоящее время)',
        'Preteritum (прошедшее время)',
        'Presens perfektum (причастие прошедшего времени)',
        'Перевод',
        'User_ID',
        'Username',
        'Contact'
    ])
    df_suggestions.to_csv(SUGGESTIONS_FILE_PATH, index=False, encoding='utf-8')

print("Чтение CSV файла с контактами...")
try:
    df_contacts = pd.read_csv(CONTACTS_FILE_PATH)
except FileNotFoundError:
    print("Файл с контактами не найден, создаём новый...")
    df_contacts = pd.DataFrame(columns=[
        'User_ID',
        'Username',
        'Contact',
        'Last_Active'
    ])
    df_contacts.to_csv(CONTACTS_FILE_PATH, index=False, encoding='utf-8')


# Определение клавиатуры
def get_keyboard(infinitiv, df_verbs, update):
    user_id = update.effective_user.id
    if user_id == 509114893:  # Клавиатура для администратора
        return ReplyKeyboardMarkup([
            ['Старт', 'Добавить'],
            ['Anbefalinger', 'Kontaktperson']
        ], resize_keyboard=True)
    else:  # Клавиатура для обычных пользователей
        return ReplyKeyboardMarkup([
            ['Старт', 'Legg til ord']
        ], resize_keyboard=True)


# Клавиатура для Anbefalinger
def get_anbefalinger_keyboard():
    return ReplyKeyboardMarkup([
        ['Добавить номер', 'Добавить всё'],
        ['Удалить номер', 'Удалить всё'],
        ['Редактировать номер'],
        ['Назад']
    ], resize_keyboard=True)


# Клавиатура для отмены ввода
def get_cancel_keyboard():
    return ReplyKeyboardMarkup([['Отмена']], resize_keyboard=True)


# Клавиатура для возврата из Kontaktperson, Anbefalinger или Legg til ord
def get_back_keyboard():
    return ReplyKeyboardMarkup([['Назад']], resize_keyboard=True)


# Команда /start
async def start(update: Update, context: ContextTypes):
    df_verbs = context.bot_data['df_verbs']
    df_contacts = context.bot_data['df_contacts']
    user_id = update.effective_user.id

    # Исключаем ваш ID из записи в 1_Kontakt
    if user_id != 509114893:
        username = update.effective_user.username or "N/A"
        contact = "N/A"
        last_active = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Обновляем или добавляем пользователя в 1_Kontakt.csv
        if user_id in df_contacts['User_ID'].values:
            df_contacts.loc[df_contacts['User_ID'] == user_id, 'Last_Active'] = last_active
            df_contacts.loc[df_contacts['User_ID'] == user_id, 'Username'] = username
        else:
            new_contact = pd.DataFrame({
                'User_ID': [user_id],
                'Username': [username],
                'Contact': [contact],
                'Last_Active': [last_active]
            })
            df_contacts = pd.concat([df_contacts, new_contact], ignore_index=True)
        df_contacts.to_csv(CONTACTS_FILE_PATH, index=False, encoding='utf-8')
        context.bot_data['df_contacts'] = df_contacts

    await update.message.reply_text(
        "Привет! Введи норвежский глагол или перевод, и я покажу его формы!\n"
        "<b>Поиск работает по частичному совпадению (минимум 3 символа)</b>, например, 'legge' найдет все варианты с 'legge'.\n"
        "<b>Используй 'Legg til ord'</b>, чтобы предложить новое слово.",
        reply_markup=get_keyboard('', df_verbs, update),
        parse_mode='HTML'
    )


# Обработка запроса глагола
async def handle_message(update: Update, context: ContextTypes):
    df_verbs = context.bot_data['df_verbs']
    df_suggestions = context.bot_data['df_suggestions']
    df_contacts = context.bot_data['df_contacts']
    user_id = update.effective_user.id
    user_input = update.message.text.strip()
    print(f"Получено сообщение: {user_input}")

    # Проверяем отмену ввода для "Добавить"
    if user_input.lower() == "отмена" and 'pending_add' in context.user_data and user_id == 509114893:
        context.user_data.pop('pending_add')
        await update.message.reply_text(
            "Добавление отменено.",
            reply_markup=get_keyboard('', df_verbs, update)
        )
        return

    # Проверяем возврат из "Kontaktperson"
    if user_input.lower() == "назад" and 'pending_kontaktperson' in context.user_data and user_id == 509114893:
        context.user_data.pop('pending_kontaktperson')
        await update.message.reply_text(
            "Возврат в главное меню.",
            reply_markup=get_keyboard('', df_verbs, update)
        )
        return

    # Проверяем возврат из "Anbefalinger" с очисткой всех флагов
    if user_input.lower() == "назад" and 'pending_anbefalinger' in context.user_data and user_id == 509114893:
        context.user_data.pop('pending_anbefalinger', None)
        context.user_data.pop('pending_add_numbers', None)
        context.user_data.pop('pending_delete_numbers', None)
        context.user_data.pop('pending_edit_number', None)
        context.user_data.pop('number_to_edit', None)
        await update.message.reply_text(
            "Возврат в главное меню.",
            reply_markup=get_keyboard('', df_verbs, update)
        )
        return

    # Проверяем возврат из "Legg til ord"
    if user_input.lower() == "назад" and 'pending_suggestion' in context.user_data:
        context.user_data.pop('pending_suggestion')
        await update.message.reply_text(
            "Возврат в главное меню.",
            reply_markup=get_keyboard('', df_verbs, update)
        )
        return

    # Проверяем, ожидается ли предложение нового слова от пользователя
    if 'pending_suggestion' in context.user_data:
        try:
            infinitiv, presens, preteritum, perfektum, translation = user_input.split(',')
            if infinitiv in df_verbs['Infinitiv (инфинитив)'].values:
                await update.message.reply_text(
                    "<b>Dette ordet er allerede i ordboken.</b>",
                    reply_markup=get_keyboard('', df_verbs, update),
                    parse_mode='HTML'
                )
                context.user_data.pop('pending_suggestion')
                return
            if infinitiv in df_suggestions['Infinitiv (инфинитив)'].values:
                await update.message.reply_text(
                    "<b>Dette forslaget er allerede under vurdering.</b>",
                    reply_markup=get_keyboard('', df_verbs, update),
                    parse_mode='HTML'
                )
                context.user_data.pop('pending_suggestion')
                return
            username = update.effective_user.username or "N/A"
            contact = "N/A"
            new_suggestion = pd.DataFrame({
                'Infinitiv (инфинитив)': [infinitiv],
                'Presens (настоящее время)': [presens],
                'Preteritum (прошедшее время)': [preteritum],
                'Presens perfektum (причастие прошедшего времени)': [perfektum],
                'Перевод': [translation],
                'User_ID': [user_id],
                'Username': [username],
                'Contact': [contact]
            })
            df_suggestions = pd.concat([df_suggestions, new_suggestion], ignore_index=True)
            df_suggestions.to_csv(SUGGESTIONS_FILE_PATH, index=False, encoding='utf-8')
            context.bot_data['df_suggestions'] = df_suggestions
            await update.message.reply_text(
                "Спасибо! Слово предложено и отправлено на рассмотрение администратору.",
                reply_markup=get_keyboard('', df_verbs, update)
            )
            context.user_data.pop('pending_suggestion')
            return
        except ValueError:
            await update.message.reply_text(
                "<b>Неверный формат. Используй:</b> å danse,danser,danset,har danset,перевод",
                reply_markup=get_back_keyboard(),
                parse_mode='HTML'
            )
            return

    # Проверяем, ожидается ли добавление пачки слов от админа
    if 'pending_add' in context.user_data and user_id == 509114893:
        lines = user_input.split('\n')
        if len(lines) > 100:
            await update.message.reply_text(
                "<b>Максимум 100 строк за раз.</b> Пожалуйста, сократите список.",
                reply_markup=get_cancel_keyboard(),
                parse_mode='HTML'
            )
            return

        new_verbs = []
        added_verbs = []
        duplicates = []

        for line in lines:
            try:
                infinitiv, presens, preteritum, perfektum, translation = line.strip().split(',')
                if infinitiv in df_verbs['Infinitiv (инфинитив)'].values:
                    duplicates.append(infinitiv)
                else:
                    new_verbs.append([infinitiv, presens, preteritum, perfektum, translation])
                    added_verbs.append(infinitiv)
            except ValueError:
                await update.message.reply_text(
                    f"<b>Ошибка в строке:</b> '{line}'. <b>Используй формат:</b> å danse,danser,danset,har danset,перевод",
                    reply_markup=get_cancel_keyboard(),
                    parse_mode='HTML'
                )
                return

        if new_verbs:
            new_df = pd.DataFrame(new_verbs, columns=[
                'Infinitiv (инфинитив)',
                'Presens (настоящее время)',
                'Preteritum (прошедшее время)',
                'Presens perfektum (причастие прошедшего времени)',
                'Перевод'
            ])
            df_verbs = pd.concat([df_verbs, new_df], ignore_index=True)
            df_verbs.to_csv(VERBS_FILE_PATH, index=False, encoding='utf-8')
            context.bot_data['df_verbs'] = df_verbs

        response = "Результат добавления:\n"
        if added_verbs:
            response += f"Успешно добавлены глаголы: {', '.join(added_verbs)}\n"
        if duplicates:
            response += f"Уже существуют в базе: {', '.join(duplicates)}"

        await update.message.reply_text(
            response.strip(),
            reply_markup=get_keyboard('', df_verbs, update)
        )
        context.user_data.pop('pending_add')
        return

    # Проверяем, ожидается ли добавление по номерам из Anbefalinger
    if 'pending_add_numbers' in context.user_data and user_id == 509114893:
        try:
            numbers = [int(num.strip()) - 1 for num in user_input.split(',')]
            if not all(0 <= num < len(df_suggestions) for num in numbers):
                await update.message.reply_text(
                    f"<b>Некоторые номера вне диапазона.</b> Введите номера от 1 до {len(df_suggestions)}",
                    reply_markup=get_anbefalinger_keyboard(),
                    parse_mode='HTML'
                )
                return
            selected_verbs = df_suggestions.iloc[numbers]
            new_verbs = []
            added_verbs = []
            duplicates = []
            for _, row in selected_verbs.iterrows():
                infinitiv = row['Infinitiv (инфинитив)']
                if infinitiv in df_verbs['Infinitiv (инфинитив)'].values:
                    duplicates.append(infinitiv)
                else:
                    new_verbs.append([row['Infinitiv (инфинитив)'], row['Presens (настоящее время)'],
                                      row['Preteritum (прошедшее время)'],
                                      row['Presens perfektum (причастие прошедшего времени)'],
                                      row['Перевод']])
                    added_verbs.append(infinitiv)
            if new_verbs:
                new_df = pd.DataFrame(new_verbs, columns=[
                    'Infinitiv (инфинитив)',
                    'Presens (настоящее время)',
                    'Preteritum (прошедшее время)',
                    'Presens perfektum (причастие прошедшего времени)',
                    'Перевод'
                ])
                df_verbs = pd.concat([df_verbs, new_df], ignore_index=True)
                df_verbs.to_csv(VERBS_FILE_PATH, index=False, encoding='utf-8')
                context.bot_data['df_verbs'] = df_verbs
                df_suggestions = df_suggestions.drop(selected_verbs.index)
                df_suggestions.to_csv(SUGGESTIONS_FILE_PATH, index=False, encoding='utf-8')
                context.bot_data['df_suggestions'] = df_suggestions

            response = "Результат добавления:\n"
            if added_verbs:
                response += f"Успешно добавлены: {', '.join(added_verbs)}\n"
            if duplicates:
                response += f"Уже существуют: {', '.join(duplicates)}"
            await update.message.reply_text(response.strip(), reply_markup=get_keyboard('', df_verbs, update))
            context.user_data.pop('pending_add_numbers')
            context.user_data.pop('pending_anbefalinger', None)
        except ValueError:
            await update.message.reply_text(
                "<b>Введите номера через запятую</b>, например: 1, 3, 4",
                reply_markup=get_anbefalinger_keyboard(),
                parse_mode='HTML'
            )
        return

    # Проверяем, ожидается ли удаление по номерам из Anbefalinger
    if 'pending_delete_numbers' in context.user_data and user_id == 509114893:
        try:
            numbers = [int(num.strip()) - 1 for num in user_input.split(',')]
            if not all(0 <= num < len(df_suggestions) for num in numbers):
                await update.message.reply_text(
                    f"<b>Некоторые номера вне диапазона.</b> Введите номера от 1 до {len(df_suggestions)}",
                    reply_markup=get_anbefalinger_keyboard(),
                    parse_mode='HTML'
                )
                return
            deleted_verbs = df_suggestions.iloc[numbers]['Infinitiv (инфинитив)'].tolist()
            df_suggestions = df_suggestions.drop(df_suggestions.index[numbers])
            df_suggestions.to_csv(SUGGESTIONS_FILE_PATH, index=False, encoding='utf-8')
            context.bot_data['df_suggestions'] = df_suggestions
            await update.message.reply_text(
                f"Удалены глаголы: {', '.join(deleted_verbs)}",
                reply_markup=get_keyboard('', df_verbs, update)
            )
            context.user_data.pop('pending_delete_numbers')
            context.user_data.pop('pending_anbefalinger', None)
        except ValueError:
            await update.message.reply_text(
                "<b>Введите номера через запятую</b>, например: 1, 3, 4",
                reply_markup=get_anbefalinger_keyboard(),
                parse_mode='HTML'
            )
        return

    # Проверяем, ожидается ли редактирование номера в Anbefalinger
    if 'pending_edit_number' in context.user_data and user_id == 509114893:
        if 'number_to_edit' not in context.user_data:
            try:
                number = int(user_input) - 1
                if 0 <= number < len(df_suggestions):
                    context.user_data['number_to_edit'] = number
                    verb = df_suggestions.iloc[number]['Infinitiv (инфинитив)']
                    await update.message.reply_text(
                        f"Введите новое описание для {verb} в формате:\n"
                        "<b>å legge,legger,la,har lagt,класть</b>",
                        reply_markup=get_anbefalinger_keyboard(),
                        parse_mode='HTML'
                    )
                else:
                    await update.message.reply_text(
                        f"<b>Номер вне диапазона.</b> Введите от 1 до {len(df_suggestions)}",
                        reply_markup=get_anbefalinger_keyboard(),
                        parse_mode='HTML'
                    )
            except ValueError:
                await update.message.reply_text(
                    "<b>Введите номер строки</b>, например: 1",
                    reply_markup=get_anbefalinger_keyboard(),
                    parse_mode='HTML'
                )
        else:
            try:
                infinitiv, presens, preteritum, perfektum, translation = user_input.split(',')
                number = context.user_data['number_to_edit']
                df_suggestions.iloc[number] = [infinitiv, presens, preteritum, perfektum, translation,
                                               df_suggestions.iloc[number]['User_ID'],
                                               df_suggestions.iloc[number]['Username'],
                                               df_suggestions.iloc[number]['Contact']]
                df_suggestions.to_csv(SUGGESTIONS_FILE_PATH, index=False, encoding='utf-8')
                context.bot_data['df_suggestions'] = df_suggestions
                await update.message.reply_text(
                    f"Строка {number + 1} обновлена:\n"
                    f"<b>Infinitiv:</b> {infinitiv}\n<b>Presens:</b> {presens}\n<b>Preteritum:</b> {preteritum}\n"
                    f"<b>Presens perfektum:</b> {perfektum}\n<b>Перевод:</b> {translation}",
                    reply_markup=get_keyboard('', df_verbs, update),
                    parse_mode='HTML'
                )
                context.user_data.pop('number_to_edit')
                context.user_data.pop('pending_edit_number')
                context.user_data.pop('pending_anbefalinger', None)
            except ValueError:
                await update.message.reply_text(
                    "<b>Неверный формат. Используй:</b> å legge,legger,la,har lagt,класть",
                    reply_markup=get_anbefalinger_keyboard(),
                    parse_mode='HTML'
                )
        return

    if user_input.lower() == "старт":
        await start(update, context)
        return
    elif user_input.lower() == "добавить" and user_id == 509114893:
        context.user_data['pending_add'] = True
        await update.message.reply_text(
            "Введите глаголы в формате: <b>å danse,danser,danset,har danset,перевод</b>\n"
            "<b>Можно добавить до 100 строк</b>, разделяя их переносом строки.\n"
            "<b>Нажмите 'Отмена'</b>, если передумали.",
            reply_markup=get_cancel_keyboard(),
            parse_mode='HTML'
        )
        return
    elif user_input.lower() == "anbefalinger" and user_id == 509114893:
        context.user_data['pending_anbefalinger'] = True
        if df_suggestions.empty:
            await update.message.reply_text(
                "Список предложений пуст.\n<b>Нажмите 'Назад'</b>, чтобы вернуться.",
                reply_markup=get_back_keyboard(),
                parse_mode='HTML'
            )
        else:
            suggestions_text = "Список предложенных слов:\n"
            for idx, row in df_suggestions.iterrows():
                suggestions_text += (
                    f"{idx + 1}. {row['Infinitiv (инфинитив)']}, {row['Presens (настоящее время)']}, "
                    f"{row['Preteritum (прошедшее время)']}, {row['Presens perfektum (причастие прошедшего времени)']}, "
                    f"{row['Перевод']}\n"
                )
            await update.message.reply_text(
                suggestions_text + "\n<b>Нажмите 'Назад'</b>, чтобы вернуться.",
                reply_markup=get_anbefalinger_keyboard(),
                parse_mode='HTML'
            )
        return
    elif user_input.lower() == "добавить номер" and user_id == 509114893:
        context.user_data['pending_add_numbers'] = True
        await update.message.reply_text(
            "<b>Введите номера строк для добавления через запятую</b> (например, 1, 3, 4):",
            reply_markup=get_anbefalinger_keyboard(),
            parse_mode='HTML'
        )
        return
    elif user_input.lower() == "добавить всё" and user_id == 509114893:
        new_verbs = []
        added_verbs = []
        duplicates = []
        for _, row in df_suggestions.iterrows():
            infinitiv = row['Infinitiv (инфинитив)']
            if infinitiv in df_verbs['Infinitiv (инфинитив)'].values:
                duplicates.append(infinitiv)
            else:
                new_verbs.append([row['Infinitiv (инфинитив)'], row['Presens (настоящее время)'],
                                  row['Preteritum (прошедшее время)'],
                                  row['Presens perfektum (причастие прошедшего времени)'],
                                  row['Перевод']])
                added_verbs.append(infinitiv)
        if new_verbs:
            new_df = pd.DataFrame(new_verbs, columns=[
                'Infinitiv (инфинитив)',
                'Presens (настоящее время)',
                'Preteritum (прошедшее время)',
                'Presens perfektum (причастие прошедшего времени)',
                'Перевод'
            ])
            df_verbs = pd.concat([df_verbs, new_df], ignore_index=True)
            df_verbs.to_csv(VERBS_FILE_PATH, index=False, encoding='utf-8')
            context.bot_data['df_verbs'] = df_verbs
            df_suggestions = pd.DataFrame(columns=df_suggestions.columns)
            df_suggestions.to_csv(SUGGESTIONS_FILE_PATH, index=False, encoding='utf-8')
            context.bot_data['df_suggestions'] = df_suggestions

        response = "Результат добавления:\n"
        if added_verbs:
            response += f"Успешно добавлены: {', '.join(added_verbs)}\n"
        if duplicates:
            response += f"Уже существуют: {', '.join(duplicates)}"
        await update.message.reply_text(response.strip(), reply_markup=get_keyboard('', df_verbs, update))
        context.user_data.pop('pending_anbefalinger', None)
        return
    elif user_input.lower() == "удалить номер" and user_id == 509114893:
        context.user_data['pending_delete_numbers'] = True
        await update.message.reply_text(
            "<b>Введите номера строк для удаления через запятую</b> (например, 1, 3, 4):",
            reply_markup=get_anbefalinger_keyboard(),
            parse_mode='HTML'
        )
        return
    elif user_input.lower() == "удалить всё" and user_id == 509114893:
        df_suggestions = pd.DataFrame(columns=df_suggestions.columns)
        df_suggestions.to_csv(SUGGESTIONS_FILE_PATH, index=False, encoding='utf-8')
        context.bot_data['df_suggestions'] = df_suggestions
        await update.message.reply_text(
            "Все предложения удалены.",
            reply_markup=get_keyboard('', df_verbs, update)
        )
        context.user_data.pop('pending_anbefalinger', None)
        return
    elif user_input.lower() == "редактировать номер" and user_id == 509114893:
        context.user_data['pending_edit_number'] = True
        await update.message.reply_text(
            "<b>Введите номер строки для редактирования</b> (например, 1):",
            reply_markup=get_anbefalinger_keyboard(),
            parse_mode='HTML'
        )
        return
    elif user_input.lower() == "kontaktperson" and user_id == 509114893:
        context.user_data['pending_kontaktperson'] = True
        if df_contacts.empty:
            await update.message.reply_text(
                "Список контактов пуст.\n<b>Нажмите 'Назад'</b>, чтобы вернуться.",
                reply_markup=get_back_keyboard(),
                parse_mode='HTML'
            )
        else:
            contacts_text = "Список пользователей бота:\n"
            for idx, row in df_contacts.iterrows():
                contacts_text += (
                    f"{idx + 1}. ID: {row['User_ID']}, @{row['Username']}, Contact: {row['Contact']}\n"
                )
            await update.message.reply_text(
                contacts_text + "\n<b>Нажмите 'Назад'</b>, чтобы вернуться.",
                reply_markup=get_back_keyboard(),
                parse_mode='HTML'
            )
        return
    elif user_input.lower() == "legg til ord":
        context.user_data['pending_suggestion'] = True
        await update.message.reply_text(
            "<b>Предложите слово в формате:</b> å danse,danser,danset,har danset,перевод\n"
            "<b>Нажмите 'Назад'</b>, чтобы отменить.",
            reply_markup=get_back_keyboard(),
            parse_mode='HTML'
        )
        return

    # Проверка доступа к командам администратора
    if user_input.lower() in ["добавить", "anbefalinger", "kontaktperson",
                              "добавить номер", "добавить всё", "удалить номер", "удалить всё",
                              "редактировать номер"] and user_id != 509114893:
        await update.message.reply_text(
            "Эта команда доступна только администратору.",
            reply_markup=get_keyboard('', df_verbs, update)
        )
        return

    print(f"Проверка в базе данных для: {user_input.lower()}")
    # Поиск частичного совпадения (минимум 3 символа)
    if len(user_input) >= 3:
        result = df_verbs[
            (df_verbs['Infinitiv (инфинитив)'].str.lower().str.contains(user_input.lower(), na=False)) |
            (df_verbs['Presens (настоящее время)'].str.lower().str.contains(user_input.lower(), na=False)) |
            (df_verbs['Preteritum (прошедшее время)'].str.lower().str.contains(user_input.lower(), na=False)) |
            (df_verbs['Presens perfektum (причастие прошедшего времени)'].str.lower().str.contains(user_input.lower(),
                                                                                                   na=False)) |
            (df_verbs['Перевод'].str.lower().str.contains(user_input.lower(), na=False))
            ]
        if not result.empty:
            response = "<b>Найденные совпадения:</b>\n"
            for idx, row in result.iterrows():
                response += (
                    f"<b>Infinitiv:</b> {row['Infinitiv (инфинитив)']}\n"
                    f"<b>Presens:</b> {row['Presens (настоящее время)']}\n"
                    f"<b>Preteritum:</b> {row['Preteritum (прошедшее время)']}\n"
                    f"<b>Presens perfektum:</b> {row['Presens perfektum (причастие прошедшего времени)']}\n"
                    f"<b>Перевод:</b> {row['Перевод']}\n\n"
                )
            context.user_data['last_searched_verb'] = result.iloc[0]['Infinitiv (инфинитив)']
            await update.message.reply_text(response.strip(), reply_markup=get_keyboard('', df_verbs, update),
                                            parse_mode='HTML')
        else:
            await update.message.reply_text(
                "Слово не найдено в базе. <b>Используй 'Legg til ord'</b>, чтобы предложить его.",
                reply_markup=get_keyboard('', df_verbs, update),
                parse_mode='HTML'
            )
    else:
        await update.message.reply_text(
            "<b>Введите минимум 3 символа</b> для поиска.",
            reply_markup=get_keyboard('', df_verbs, update),
            parse_mode='HTML'
        )


# Обработка команды /add (только для админа через команду)
async def add_verb(update: Update, context: ContextTypes):
    df_verbs = context.bot_data['df_verbs']
    df_suggestions = context.bot_data['df_suggestions']
    user_id = update.effective_user.id

    if user_id != 509114893:
        await update.message.reply_text(
            "Эта команда доступна только администратору.",
            reply_markup=get_keyboard('', df_verbs, update)
        )
        return

    args = update.message.text.split()[1:]
    if len(args) == 5:
        try:
            infinitiv, presens, preteritum, perfektum, translation = args
            if infinitiv in df_verbs['Infinitiv (инфинитив)'].values:
                await update.message.reply_text(
                    "<b>Dette ordet er allerede i ordboken.</b>",
                    reply_markup=get_keyboard('', df_verbs, update),
                    parse_mode='HTML'
                )
                return
            new_row = pd.DataFrame({
                'Infinitiv (инфинитив)': [infinitiv],
                'Presens (настоящее время)': [presens],
                'Preteritum (прошедшее время)': [preteritum],
                'Presens perfektum (причастие прошедшего времени)': [perfektum],
                'Перевод': [translation]
            })
            df_verbs = pd.concat([df_verbs, new_row], ignore_index=True)
            df_verbs.to_csv(VERBS_FILE_PATH, index=False, encoding='utf-8')
            context.bot_data['df_verbs'] = df_verbs

            if infinitiv in df_suggestions['Infinitiv (инфинитив)'].values:
                df_suggestions = df_suggestions[df_suggestions['Infinitiv (инфинитив)'] != infinitiv]
                df_suggestions.to_csv(SUGGESTIONS_FILE_PATH, index=False, encoding='utf-8')
                context.bot_data['df_suggestions'] = df_suggestions
                await update.message.reply_text(
                    f"Слово {infinitiv} удалено из предложений и добавлено в основную базу!"
                )

            await update.message.reply_text(
                f"Глагол {infinitiv} успешно добавлен!",
                reply_markup=get_keyboard(infinitiv, df_verbs, update)
            )
        except ValueError:
            await update.message.reply_text(
                "<b>Неверный формат. Используй:</b> /add å danse,danser,danset,har danset,перевод",
                reply_markup=get_keyboard('', df_verbs, update),
                parse_mode='HTML'
            )
    else:
        await update.message.reply_text(
            "<b>Неверный формат. Используй:</b> /add å danse,danser,danset,har danset,перевод",
            reply_markup=get_keyboard('', df_verbs, update),
            parse_mode='HTML'
        )


# Запуск бота
def main():
    print("Инициализация бота...")
    app = Application.builder().token(TOKEN).job_queue(JobQueue()).build()
    print("Бот запущен и ожидает сообщений...")
    app.bot_data['df_verbs'] = df_verbs
    app.bot_data['df_suggestions'] = df_suggestions
    app.bot_data['df_contacts'] = df_contacts
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_verb))
    app.add_handler(MessageHandler(Text() & ~Command(), handle_message))
    app.run_polling()


if __name__ == '__main__':
    print("Запуск программы...")
    main()
