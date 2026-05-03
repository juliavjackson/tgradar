from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu(is_admin=False):
    keyboard = [
        [InlineKeyboardButton(text="📊 Кампании", callback_data="menu_campaigns")],
        [InlineKeyboardButton(text="📝 Посты", callback_data="menu_posts")],
        [InlineKeyboardButton(text="📚 База каналов", callback_data="menu_channels")],
        [InlineKeyboardButton(text="🔗 UTM-генератор", callback_data="menu_utm")]
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu_settings")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_campaigns_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать кампанию", callback_data="campaign_create")],
        [InlineKeyboardButton(text="📋 Мои кампании", callback_data="campaign_list")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
    ])

def get_posts_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить пост", callback_data="post_add")],
        [InlineKeyboardButton(text="📋 Мои посты", callback_data="post_list")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
    ])

def get_back_keyboard(callback_data="menu_main"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=callback_data)]
    ])

def get_post_view_keyboard(post_db_id: int, is_active: bool):
    rows = []
    if is_active:
        rows.append([InlineKeyboardButton(text="🔕 Перестать следить", callback_data=f"post_stop:{post_db_id}")])
    else:
        rows.append([InlineKeyboardButton(text="🟢 Возобновить слежение", callback_data=f"post_resume:{post_db_id}")])
    rows.append([InlineKeyboardButton(text="🗑 Удалить пост", callback_data=f"post_delete:{post_db_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад к постам", callback_data="post_list")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_campaign_view_keyboard(campaign_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить пост в кампанию", callback_data=f"campaign_add_post:{campaign_id}")],
        [InlineKeyboardButton(text="📥 Выгрузить в Excel", callback_data=f"campaign_excel:{campaign_id}")],
        [InlineKeyboardButton(text="🗑 Удалить кампанию", callback_data=f"campaign_delete:{campaign_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="campaign_list")]
    ])

def get_channels_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить канал", callback_data="channel_add")],
        [InlineKeyboardButton(text="📋 Все каналы", callback_data="channel_list")],
        [InlineKeyboardButton(text="🎯 Подобрать каналы", callback_data="channel_pick")],
        [InlineKeyboardButton(text="📥 Импорт из Excel", callback_data="channel_import")],
        [InlineKeyboardButton(text="🔄 Обновить охваты у всех", callback_data="channel_refresh_all")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
    ])

def get_channel_view_keyboard(handle: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Изменить цену", callback_data=f"channel_edit_price:{handle}")],
        [InlineKeyboardButton(text="🗑 Удалить канал", callback_data=f"channel_delete:{handle}")],
        [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="channel_list")]
    ])

def get_channel_picker_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 По бюджету", callback_data="channel_pick_mode:budget")],
        [InlineKeyboardButton(text="👁 По охвату", callback_data="channel_pick_mode:reach")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_channels")]
    ])

def get_utm_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Создать одну ссылку", callback_data="utm_single")],
        [InlineKeyboardButton(text="📦 Пакетная генерация", callback_data="utm_bulk")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
    ])

def get_settings_menu(is_admin=False):
    keyboard = [
        [InlineKeyboardButton(text="📊 Яндекс.Метрика", callback_data="settings_metrica")]
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton(text="👥 Пользователи", callback_data="settings_users")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_metrica_settings_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆔 Установить Counter ID", callback_data="metrica_set_id")],
        [InlineKeyboardButton(text="🔑 Установить OAuth Токен", callback_data="metrica_set_token")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_settings")]
    ])

def get_users_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить пользователя", callback_data="user_add")],
        [InlineKeyboardButton(text="📋 Список пользователей", callback_data="user_list")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_settings")]
    ])
