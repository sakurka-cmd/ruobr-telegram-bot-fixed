"""
Обработчики аутентификации и базовых команд.
"""
import logging
from typing import Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from ..config import config
from ..database import get_user, create_or_update_user, UserConfig
from ..states import LoginStates
from ..services import get_children_async, AuthenticationError

logger = logging.getLogger(__name__)

router = Router()


# ===== Клавиатуры =====

def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Расписание сегодня"), KeyboardButton(text="📅 Расписание завтра")],
            [KeyboardButton(text="📘 ДЗ на завтра"), KeyboardButton(text="⭐ Оценки сегодня")],
            [KeyboardButton(text="💰 Баланс питания"), KeyboardButton(text="🍽 Питание сегодня")],
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="❓ Помощь")],
        ],
        resize_keyboard=True,
        persistent=True
    )


def get_settings_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔑 Изменить логин/пароль"), KeyboardButton(text="💰 Порог баланса")],
            [KeyboardButton(text="🔔 Уведомления"), KeyboardButton(text="👤 Мой профиль")],
            [KeyboardButton(text="◀️ Назад")],
        ],
        resize_keyboard=True
    )


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )


# ===== Команды =====

@router.message(Command("start"))
async def cmd_start(message: Message, user_config: Optional[UserConfig] = None):
    if user_config is None:
        user_config = await create_or_update_user(message.chat.id)
    
    is_auth = user_config.login and user_config.password
    
    welcome_text = (
        "👋 <b>Добро пожаловать в школьный бот!</b>\n\n"
        "Я помогаю родителям следить за:\n"
        "• 💰 Балансом школьного питания\n"
        "• 📅 Расписанием уроков\n"
        "• 📘 Домашними заданиями\n"
        "• ⭐ Оценками\n\n"
    )
    
    if not is_auth:
        welcome_text += "⚠️ <b>Требуется настройка!</b>\nИспользуйте /set_login для ввода учётных данных.\n\n"
    else:
        welcome_text += "✅ Учётные данные настроены.\n\n"
    
    welcome_text += (
        "📖 <b>Команды:</b>\n"
        "/set_login — настроить логин/пароль\n"
        "/balance — баланс питания\n"
        "/ttoday — расписание сегодня\n"
        "/ttomorrow — расписание завтра"
    )
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard())


@router.message(Command("set_login"))
async def cmd_set_login(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🔐 <b>Настройка учётных данных</b>\n\n"
        "Введите логин от cabinet.ruobr.ru:\n\n"
        "❌ Отмена — для выхода",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(LoginStates.waiting_for_login)


@router.message(LoginStates.waiting_for_login)
async def process_login(message: Message, state: FSMContext):
    text = message.text.strip()
    
    # Проверка отмены
    if text == "❌ Отмена" or text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=get_main_keyboard())
        return
    
    if not text:
        await message.answer("❌ Логин не может быть пустым. Попробуйте ещё раз:")
        return
    
    if len(text) > 100:
        await message.answer("❌ Логин слишком длинный. Попробуйте ещё раз:")
        return
    
    await state.update_data(login=text)
    await message.answer(
        "✅ Логин сохранён.\n\n"
        "Теперь введите пароль от cabinet.ruobr.ru:\n\n"
        "❌ Отмена — для выхода"
    )
    await state.set_state(LoginStates.waiting_for_password)


@router.message(LoginStates.waiting_for_password)
async def process_password(message: Message, state: FSMContext):
    password = message.text.strip()
    
    # Проверка отмены
    if password == "❌ Отмена" or password == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=get_main_keyboard())
        return
    
    if not password:
        await message.answer("❌ Пароль не может быть пустым. Попробуйте ещё раз:")
        return
    
    data = await state.get_data()
    login = data.get("login", "")
    
    # Удаляем сообщение с паролем
    try:
        await message.delete()
    except Exception:
        pass
    
    status_message = await message.answer("🔄 Проверка учётных данных...")
    
    try:
        children = await get_children_async(login, password)
        
        if not children:
            await status_message.edit_text(
                "⚠️ Учётные данные верны, но дети не найдены.\n"
                "Данные сохранены. Проверьте аккаунт на cabinet.ruobr.ru"
            )
        else:
            children_list = "\n".join([f"  • {c.full_name} ({c.group})" for c in children])
            await status_message.edit_text(
                f"✅ <b>Успешная авторизация!</b>\n\n"
                f"Найдены дети:\n{children_list}\n\n"
                f"Теперь доступны все функции бота."
            )
        
        # Сохраняем учётные данные
        await create_or_update_user(message.chat.id, login=login, password=password)
        
        # Отправляем клавиатуру отдельным сообщением
        await message.answer("🏠 Главное меню", reply_markup=get_main_keyboard())
        
    except AuthenticationError:
        await status_message.edit_text(
            "❌ <b>Ошибка авторизации!</b>\n\n"
            "Неверный логин или пароль. Попробуйте снова: /set_login"
        )
    except Exception as e:
        logger.error(f"Error during login for user {message.chat.id}: {e}")
        await status_message.edit_text(
            "❌ <b>Ошибка соединения!</b>\n\n"
            "Не удалось проверить учётные данные. Попробуйте позже."
        )
    
    await state.clear()


@router.message(Command("cancel"))
@router.message(F.text == "❌ Отмена")
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нет активной операции.", reply_markup=get_main_keyboard())
        return
    
    await state.clear()
    await message.answer("❌ Операция отменена.", reply_markup=get_main_keyboard())


@router.message(F.text == "❓ Помощь")
async def btn_help(message: Message):
    await message.answer(
        "📖 <b>Справка по боту</b>\n\n"
        "<b>🔐 Настройка:</b>\n• /set_login — ввести логин/пароль\n\n"
        "<b>💰 Питание:</b>\n• /balance — баланс всех детей\n• /foodtoday — что ели сегодня\n\n"
        "<b>📅 Расписание:</b>\n• /ttoday — расписание сегодня\n• /ttomorrow — расписание завтра\n\n"
        "<b>📘 ДЗ:</b>\n• /hwtomorrow — ДЗ на завтра\n\n"
        "<b>⭐ Оценки:</b>\n• /markstoday — оценки за сегодня"
    )


@router.message(F.text == "⚙️ Настройки")
async def btn_settings(message: Message):
    await message.answer("⚙️ <b>Настройки</b>", reply_markup=get_settings_keyboard())


@router.message(F.text == "🔑 Изменить логин/пароль")
async def btn_change_login(message: Message, state: FSMContext):
    await cmd_set_login(message, state)


@router.message(F.text == "◀️ Назад")
async def btn_back(message: Message):
    await message.answer("🏠 <b>Главное меню</b>", reply_markup=get_main_keyboard())


@router.message(F.text == "👤 Мой профиль")
async def btn_profile(message: Message, user_config: Optional[UserConfig] = None):
    if user_config is None:
        user_config = await get_user(message.chat.id)
    
    if user_config is None:
        await message.answer("Профиль не найден. Используйте /start")
        return
    
    status = "✅ Настроен" if user_config.login and user_config.password else "❌ Не настроен"
    notif_status = "🔔 Включены" if user_config.enabled else "🔕 Выключены"
    marks_status = "🔔 Включены" if user_config.marks_enabled else "🔕 Выключены"
    
    await message.answer(
        f"👤 <b>Ваш профиль</b>\n\n"
        f"<b>Статус:</b> {status}\n"
        f"<b>Логин:</b> {user_config.login or 'не указан'}\n\n"
        f"<b>Уведомления о балансе:</b> {notif_status}\n"
        f"<b>Уведомления об оценках:</b> {marks_status}"
    )


@router.message(Command("enable"))
async def cmd_enable(message: Message):
    await create_or_update_user(message.chat.id, enabled=True, marks_enabled=True)
    await message.answer("🔔 <b>Уведомления включены!</b>")


@router.message(Command("disable"))
async def cmd_disable(message: Message):
    await create_or_update_user(message.chat.id, enabled=False, marks_enabled=False)
    await message.answer("🔕 <b>Уведомления отключены.</b>")


# ===== Inline клавиатуры =====

def get_notification_keyboard(user_config: UserConfig) -> InlineKeyboardMarkup:
    balance_status = "✅" if user_config.enabled else "❌"
    marks_status = "✅" if user_config.marks_enabled else "❌"
    food_status = "✅" if getattr(user_config, 'food_enabled', True) else "❌"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💰 Баланс: {balance_status}", callback_data="toggle_balance")],
        [InlineKeyboardButton(text=f"⭐ Оценки: {marks_status}", callback_data="toggle_marks")],
        [InlineKeyboardButton(text=f"🍽 Питание: {food_status}", callback_data="toggle_food")],
    ])


@router.message(F.text == "🔔 Уведомления")
async def btn_notifications_inline(message: Message, user_config: Optional[UserConfig] = None):
    if user_config is None:
        user_config = await get_user(message.chat.id)
    if user_config is None:
        user_config = await create_or_update_user(message.chat.id)
    
    await message.answer(
        "🔔 <b>Настройки уведомлений</b>\n\n"
        "Нажмите для включения/выключения:",
        reply_markup=get_notification_keyboard(user_config)
    )


@router.callback_query(F.data == "toggle_balance")
async def cb_toggle_balance(callback: CallbackQuery, user_config: Optional[UserConfig] = None):
    if user_config is None:
        user_config = await get_user(callback.message.chat.id)
    if user_config is None:
        await callback.answer("Ошибка!")
        return
    
    new_status = not user_config.enabled
    await create_or_update_user(callback.message.chat.id, enabled=new_status)
    await callback.answer(f"{'Включено' if new_status else 'Выключено'}!")
    
    updated = await get_user(callback.message.chat.id)
    await callback.message.edit_reply_markup(reply_markup=get_notification_keyboard(updated))


@router.callback_query(F.data == "toggle_marks")
async def cb_toggle_marks(callback: CallbackQuery, user_config: Optional[UserConfig] = None):
    if user_config is None:
        user_config = await get_user(callback.message.chat.id)
    if user_config is None:
        await callback.answer("Ошибка!")
        return
    
    new_status = not user_config.marks_enabled
    await create_or_update_user(callback.message.chat.id, marks_enabled=new_status)
    await callback.answer(f"{'Включено' if new_status else 'Выключено'}!")
    
    updated = await get_user(callback.message.chat.id)
    await callback.message.edit_reply_markup(reply_markup=get_notification_keyboard(updated))


@router.callback_query(F.data == "toggle_food")
async def cb_toggle_food(callback: CallbackQuery, user_config: Optional[UserConfig] = None):
    if user_config is None:
        user_config = await get_user(callback.message.chat.id)
    if user_config is None:
        await callback.answer("Ошибка!")
        return
    
    new_status = not getattr(user_config, 'food_enabled', True)
    await create_or_update_user(callback.message.chat.id, food_enabled=new_status)
    await callback.answer(f"{'Включено' if new_status else 'Выключено'}!")
    
    updated = await get_user(callback.message.chat.id)
    await callback.message.edit_reply_markup(reply_markup=get_notification_keyboard(updated))
