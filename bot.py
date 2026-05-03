from aiogram.utils.keyboard import InlineKeyboardBuilder
import os
import asyncio
import re
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile, BotCommand
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.future import select
from sqlalchemy import delete
from dotenv import load_dotenv

from database import init_db, AsyncSessionLocal, Campaign, Post, Channel, PostMetricsHistory, UTMLink, Setting, User
from keyboards import (
    get_main_menu, get_campaigns_menu, get_posts_menu, get_back_keyboard,
    get_campaign_view_keyboard, get_post_view_keyboard,
    get_channels_menu, get_channel_view_keyboard, get_channel_picker_keyboard,
    get_utm_menu, get_settings_menu, get_users_menu, get_metrica_settings_menu
)
from parser import TelegramParser
from exporter import ExcelExporter
from tracker import start_tracker
from metrica import YandexMetricaClient

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
parser = TelegramParser()
async def is_authorized(user_id: int) -> bool:
    if user_id == ADMIN_ID: return True
    async with AsyncSessionLocal() as session:
        res = await session.get(User, user_id)
        return res is not None

async def is_admin(user_id: int) -> bool:
    if user_id == ADMIN_ID: return True
    async with AsyncSessionLocal() as session:
        res = await session.get(User, user_id)
        return res is not None and res.role == 'admin'


URL_PATTERN = r'(?:https?://)?t.me/([^/]+)/(\d+)'

class CampaignCreate(StatesGroup):
    waiting_for_name = State()

ADMIN_ID = 7078699

class UserAdd(StatesGroup):
    waiting_for_id = State()

class PostAdd(StatesGroup):
    waiting_for_link = State()
    waiting_for_campaign = State()

class ChannelAdd(StatesGroup):
    waiting_for_handle = State()
    waiting_for_topic = State()
    waiting_for_geo = State()
    waiting_for_price_excl = State()
    waiting_for_price_incl = State()

class ChannelEditPrice(StatesGroup):
    waiting_for_price_excl = State()
    waiting_for_price_incl = State()

class ChannelPick(StatesGroup):
    waiting_for_mode = State()
    waiting_for_budget = State()
    waiting_for_reach = State()
    waiting_for_reach_min = State()

class UTMSingle(StatesGroup):
    waiting_for_url = State()
    waiting_for_campaign = State()
    waiting_for_channel = State()

class UTMBulk(StatesGroup):
    waiting_for_url = State()
    waiting_for_campaign = State()
    waiting_for_file = State()

class MetricaSettings(StatesGroup):
    waiting_for_id = State()
    waiting_for_token = State()

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    if not await is_authorized(message.from_user.id):
        await message.answer("🚫 Доступ ограничен. Обратитесь к администратору.")
        return
    await state.clear()
    admin_status = await is_admin(message.from_user.id)
    await message.answer(
        "👋 Привет! Я Telegram Stats Bot v2.0.\n\n"
        "Я помогу тебе планировать рекламные кампании и автоматически отслеживать метрики постов.",
        reply_markup=get_main_menu(is_admin=admin_status)
    )

@dp.message(Command("campaign"))
async def cmd_campaign(message: Message, state: FSMContext):
    if not await is_authorized(message.from_user.id): return
    await state.clear()
    await message.answer(
        "📊 <b>Кампании</b>\nЗдесь ты можешь управлять своими рекламными кампаниями.",
        parse_mode="HTML", reply_markup=get_campaigns_menu()
    )

@dp.message(Command("post"))
async def cmd_post(message: Message, state: FSMContext):
    if not await is_authorized(message.from_user.id): return
    await state.clear()
    await message.answer(
        "📝 <b>Посты</b>\nУправление отслеживаемыми постами.",
        parse_mode="HTML", reply_markup=get_posts_menu()
    )

@dp.message(Command("channels"))
async def cmd_channels(message: Message, state: FSMContext):
    if not await is_authorized(message.from_user.id): return
    await state.clear()
    await message.answer(
        "📚 <b>База каналов</b>\nСправочник рекламных каналов с ценами и охватами.",
        parse_mode="HTML", reply_markup=get_channels_menu()
    )

@dp.callback_query(F.data == "menu_main")
async def cb_menu_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🏠 <b>Главное меню</b>", parse_mode="HTML", reply_markup=get_main_menu(is_admin=await is_admin(callback.from_user.id))
    )

# --- Campaigns ---
@dp.callback_query(F.data == "menu_campaigns")
async def cb_menu_campaigns(callback: CallbackQuery):
    await callback.message.edit_text(
        "📊 <b>Кампании</b>\nЗдесь ты можешь управлять своими рекламными кампаниями.",
        parse_mode="HTML", reply_markup=get_campaigns_menu()
    )

@dp.callback_query(F.data == "campaign_create")
async def cb_campaign_create(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CampaignCreate.waiting_for_name)
    await callback.message.edit_text(
        "✍️ Введи название для новой кампании:",
        reply_markup=get_back_keyboard("menu_campaigns")
    )

@dp.message(CampaignCreate.waiting_for_name)
async def process_campaign_name(message: Message, state: FSMContext):
    name = message.text.strip()
    async with AsyncSessionLocal() as session:
        new_campaign = Campaign(name=name)
        session.add(new_campaign)
        await session.commit()
    
    await state.clear()
    await message.answer(
        f"✅ Кампания <b>{name}</b> успешно создана!",
        parse_mode="HTML", reply_markup=get_campaigns_menu()
    )

@dp.callback_query(F.data == "campaign_list")
async def cb_campaign_list(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Campaign).order_by(Campaign.id.desc()))
        campaigns = result.scalars().all()
        
    if not campaigns:
        await callback.message.edit_text(
            "У вас пока нет ни одной кампании.", reply_markup=get_campaigns_menu()
        )
        return
        
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=c.name, callback_data=f"campaign_view:{c.id}")] for c in campaigns
    ] + [[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_campaigns")]])
    
    await callback.message.edit_text("📋 Выберите кампанию:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("campaign_view:"))
async def cb_campaign_view(callback: CallbackQuery):
    campaign_id = int(callback.data.split(":")[1])
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = result.scalar_one_or_none()
        if not campaign:
            await callback.answer("Кампания не найдена.")
            return
            
        post_result = await session.execute(select(Post).where(Post.campaign_id == campaign.id))
        posts = post_result.scalars().all()
        
    text = f"📊 <b>Кампания:</b> {campaign.name}\n"
    text += f"📅 <b>Создана:</b> {campaign.created_at.strftime('%d.%m.%Y')}\n"
    text += f"📝 <b>Постов:</b> {len(posts)}\n"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_campaign_view_keyboard(campaign.id))

@dp.callback_query(F.data.startswith("campaign_delete:"))
async def cb_campaign_delete(callback: CallbackQuery):
    campaign_id = int(callback.data.split(":")[1])
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Campaign).where(Campaign.id == campaign_id))
        await session.commit()
    await callback.answer("✅ Кампания удалена")
    await cb_campaign_list(callback)

# --- Posts ---
@dp.callback_query(F.data == "menu_posts")
async def cb_menu_posts(callback: CallbackQuery):
    await callback.message.edit_text(
        "📝 <b>Посты</b>\nУправление отслеживаемыми постами.",
        parse_mode="HTML", reply_markup=get_posts_menu()
    )

@dp.callback_query(F.data == "post_add")
async def cb_post_add(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PostAdd.waiting_for_link)
    await callback.message.edit_text(
        "🔗 Отправь мне ссылку на пост (t.me/channel/123):",
        reply_markup=get_back_keyboard("menu_posts")
    )

@dp.callback_query(F.data.startswith("campaign_add_post:"))
async def cb_campaign_add_post(callback: CallbackQuery, state: FSMContext):
    campaign_id = int(callback.data.split(":")[1])
    await state.update_data(campaign_id=campaign_id)
    await state.set_state(PostAdd.waiting_for_link)
    await callback.message.edit_text(
        "🔗 Отправь мне ссылку на пост для добавления в кампанию:",
        reply_markup=get_back_keyboard(f"campaign_view:{campaign_id}")
    )

@dp.message(PostAdd.waiting_for_link)
async def process_post_link(message: Message, state: FSMContext):
    text = message.text.strip()
    matches = list(re.finditer(URL_PATTERN, text))
    
    if not matches:
        await message.answer("⚠️ Неверный формат ссылки. Попробуй ещё раз.")
        return
        
    data = await state.get_data()
    campaign_id = data.get("campaign_id")
    
    added_count = 0
    async with AsyncSessionLocal() as session:
        for match in matches:
            channel = match.group(1)
            post_id = int(match.group(2))
            # Check if channel exists in database
            ch_exists = await session.get(Channel, channel)
            if not ch_exists:
                if "missing_channels" not in data: data["missing_channels"] = []
                if channel not in data["missing_channels"]:
                    data["missing_channels"].append(channel)
                await state.update_data(missing_channels=data["missing_channels"])
            
            # Check for duplicate
            existing_post = await session.execute(
                select(Post).where(
                    Post.campaign_id == campaign_id, 
                    Post.channel_handle == channel, 
                    Post.post_id == post_id
                )
            )
            if existing_post.scalar_one_or_none():
                await message.answer(f"⚠️ Пост @{channel}/{post_id} уже есть в этой кампании, пропускаю.")
                continue
            
            # Fetch stats first to get published_at
            stats = None
            published_at = None
            try:
                stats = await parser.get_post_stats(channel, post_id)
                if stats:
                    published_at = stats.get('date')
            except Exception as e:
                logging.error(f"Error fetching initial stats for {channel}/{post_id}: {e}")
            
            new_post = Post(
                campaign_id=campaign_id,
                channel_handle=channel,
                post_id=post_id,
                name=f"Post {channel}/{post_id}",
                published_at=published_at
            )
            session.add(new_post)
            await session.commit()  # commit to get new_post.id
            await session.refresh(new_post)
            
            added_count += 1
            
            # Save initial metrics
            if stats:
                positive_emojis = ['👍', '❤️', '🔥', '🎉', '😂', '🤩', '👏', '🥳', '❤️\u200d🔥', '💯', '🌟', '🥰']
                negative_emojis = ['👎', '😢', '😡', '🤮', '💔', '😱', '😔', '🤬']
                pos_count = sum(c for e, c in stats.get('top_reactions', []) if e in positive_emojis)
                neg_count = sum(c for e, c in stats.get('top_reactions', []) if e in negative_emojis)
                    
                history = PostMetricsHistory(
                    post_id=new_post.id,
                    views=stats.get('views', 0),
                    forwards=stats.get('forwards', 0),
                    replies=stats.get('replies', 0),
                    positive_reactions=pos_count,
                    negative_reactions=neg_count,
                    subscribers=stats.get('subscribers', 0)
                )
                session.add(history)
                await session.commit()
        
    missing = (await state.get_data()).get('missing_channels', [])
    
    if campaign_id:
        kb = get_campaign_view_keyboard(campaign_id)
    else:
        kb = get_posts_menu()
        
    # If there are missing channels, add buttons to add them
    if missing:
        builder = InlineKeyboardBuilder()
        for ch in missing:
            builder.row(InlineKeyboardButton(text=f"➕ Добавить @{ch} в базу", callback_data=f"channel_add_missing:{ch}"))
        if campaign_id:
            builder.row(InlineKeyboardButton(text="⬅️ К кампании", callback_data=f"campaign_view:{campaign_id}"))
        else:
            builder.row(InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_posts"))
        kb = builder.as_markup()

    text_msg = "✅ Пост добавлен и отслеживается." if added_count == 1 else f"✅ Добавлено постов: {added_count}."
    if missing:
        text_msg += "\n\n⚠️ Некоторые каналы отсутствуют в базе. Рекомендуется добавить их для учета цен и CPV:"

    
    await message.answer(text_msg, reply_markup=kb)
    await state.clear()

@dp.callback_query(F.data == "post_list")
async def cb_post_list(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Post).order_by(Post.id.desc()).limit(20))
        posts = result.scalars().all()
        
    if not posts:
        await callback.message.edit_text("Нет отслеживаемых постов.", reply_markup=get_posts_menu())
        return
        
    text = "📋 <b>Мои посты:</b>\nНажми на пост, чтобы увидеть статистику\n\n"
    buttons = []
    for p in posts:
        status = "🟢" if p.is_tracking_active else "⚪"
        label = f"{status} t.me/{p.channel_handle}/{p.post_id}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"post_view:{p.id}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_posts")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


async def show_post_card(post_db_id: int, message):
    """Renders a post stats card into the given message."""
    async with AsyncSessionLocal() as session:
        p = await session.get(Post, post_db_id)
        if not p:
            await message.edit_text("❌ Пост не найден.", reply_markup=get_back_keyboard("post_list"))
            return
        
        hist_result = await session.execute(
            select(PostMetricsHistory)
            .where(PostMetricsHistory.post_id == post_db_id)
            .order_by(PostMetricsHistory.timestamp.desc())
            .limit(1)
        )
        latest = hist_result.scalar_one_or_none()
    
    post_url = f"https://t.me/{p.channel_handle}/{p.post_id}"
    pub_date = p.published_at.strftime('%Y-%m-%d %H:%M') if p.published_at else "неизвестно"
    status = "🟢 Активно (обновляется каждый час)" if p.is_tracking_active else "⚪ Отслеживание остановлено"
    
    if latest:
        views = latest.views
        forwards = latest.forwards
        replies = latest.replies
        reactions = latest.positive_reactions + latest.negative_reactions
        subs = latest.subscribers
        err = f"{views / subs * 100:.2f}%" if subs > 0 else "—"
        updated = latest.timestamp.strftime('%d.%m.%Y %H:%M')
    else:
        views = forwards = replies = reactions = subs = 0
        err = "—"
        updated = "ещё не обновлялось"
    
    text = (
        f"📊 <b>Статистика поста</b>\n\n"
        f"📌 Канал: <b>@{p.channel_handle}</b>\n"
        f"🔗 Пост: <a href='{post_url}'>t.me/{p.channel_handle}/{p.post_id}</a>\n"
        f"📅 Дата публикации: <b>{pub_date}</b>\n"
        f"👥 Подписчиков: <b>{subs:,}</b>\n\n"
        f"👁 Просмотры: <b>{views:,}</b>\n"
        f"📈 ERR: <b>{err}</b>\n"
        f"🔄 Репосты: <b>{forwards:,}</b>\n"
        f"💬 Комментарии: <b>{replies:,}</b>\n"
        f"❤️ Реакции: <b>{reactions:,}</b>\n\n"
        f"🔁 Статус: {status}\n"
        f"🕐 Последнее обновление: {updated}"
    )
    
    await message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_post_view_keyboard(post_db_id, p.is_tracking_active),
        disable_web_page_preview=False
    )


@dp.callback_query(F.data.startswith("post_view:"))
async def cb_post_view(callback: CallbackQuery):
    post_db_id = int(callback.data.split(":")[1])
    await show_post_card(post_db_id, callback.message)


@dp.callback_query(F.data.startswith("post_stop:"))
async def cb_post_stop(callback: CallbackQuery):
    post_db_id = int(callback.data.split(":")[1])
    async with AsyncSessionLocal() as session:
        p = await session.get(Post, post_db_id)
        if p:
            p.is_tracking_active = False
            await session.commit()
    await callback.answer("🔕 Отслеживание остановлено")
    await show_post_card(post_db_id, callback.message)


@dp.callback_query(F.data.startswith("post_resume:"))
async def cb_post_resume(callback: CallbackQuery):
    post_db_id = int(callback.data.split(":")[1])
    async with AsyncSessionLocal() as session:
        p = await session.get(Post, post_db_id)
        if p:
            p.is_tracking_active = True
            await session.commit()
    await callback.answer("🟢 Отслеживание возобновлено")
    await show_post_card(post_db_id, callback.message)


@dp.callback_query(F.data.startswith("post_delete:"))
async def cb_post_delete(callback: CallbackQuery):
    post_db_id = int(callback.data.split(":")[1])
    async with AsyncSessionLocal() as session:
        p = await session.get(Post, post_db_id)
        if p:
            await session.delete(p)
            await session.commit()
    await callback.answer("🗑 Пост удалён")
    # Refresh post list
    result_mock = type('obj', (object,), {'data': 'post_list', 'message': callback.message, 'answer': callback.answer})()
    await cb_post_list(result_mock)




@dp.callback_query(F.data == "menu_channels")
async def cb_menu_channels(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "📚 <b>База каналов</b>\nСправочник рекламных каналов с ценами и охватами.",
        parse_mode="HTML", reply_markup=get_channels_menu()
    )

@dp.callback_query(F.data.startswith("campaign_excel:"))
async def cb_campaign_excel(callback: CallbackQuery):
    campaign_id = int(callback.data.split(":")[1])
    
    await callback.message.answer("⏳ Генерирую отчёт...")
    
    async with AsyncSessionLocal() as session:
        # Get campaign name
        campaign_result = await session.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = campaign_result.scalar_one_or_none()
        campaign_name = campaign.name if campaign else f"campaign_{campaign_id}"
        
        # Get posts
        post_result = await session.execute(select(Post).where(Post.campaign_id == campaign_id))
        posts = post_result.scalars().all()
        
        if not posts:
            await callback.message.answer("❌ В кампании нет постов.")
            return
            
        stats_list = []
        for p in posts:
            # Get latest metrics
            hist_result = await session.execute(
                select(PostMetricsHistory)
                .where(PostMetricsHistory.post_id == p.id)
                .order_by(PostMetricsHistory.timestamp.desc())
                .limit(1)
            )
            latest_metrics = hist_result.scalar_one_or_none()
            
            # Use published_at from Telegram if available, fallback to added_at
            post_date = p.published_at if p.published_at else p.added_at
            
            if latest_metrics:
                channel_obj = await session.get(Channel, p.channel_handle)
                price_excl = channel_obj.price_excl_vat if channel_obj else 0
                price_incl = channel_obj.price_incl_vat if channel_obj else 0
                
                utm_link = await session.execute(
                    select(UTMLink).where(
                        UTMLink.campaign_id == campaign_id,
                        UTMLink.channel_handle == p.channel_handle
                    ).limit(1)
                )
                utm_record = utm_link.scalar_one_or_none()
                utm_url = utm_record.full_url if utm_record else ""


                # --- Fetch Yandex.Metrica Stats ---
                metrica_stats = None
                cid_res = await session.get(Setting, "metrica_counter_id")
                tok_res = await session.get(Setting, "metrica_token")
                if cid_res and tok_res and cid_res.value and tok_res.value and utm_url:
                    from metrica import YandexMetricaClient
                    client = YandexMetricaClient(tok_res.value, cid_res.value)
                    # Use slugify to get campaign slug
                    def get_slug(text):
                        import unicodedata
                        text = text.lower().replace(" ", "_")
                        return re.sub(r'[^a-z0-9_]', '', text)
                    
                    camp_slug = get_slug(campaign_name)
                    metrica_stats = await client.get_utm_stats(camp_slug, p.channel_handle)

                stats_list.append({
                    'channel': p.channel_handle,
                    'channel_name': channel_obj.name if channel_obj else '',
                    'post_name': p.name,
                    'post_id': p.post_id,
                    'date': post_date,
                    'views': latest_metrics.views,
                    'forwards': latest_metrics.forwards,
                    'replies': latest_metrics.replies,
                    'reactions_pos': latest_metrics.positive_reactions,
                    'reactions_neg': latest_metrics.negative_reactions,
                    'subscribers': latest_metrics.subscribers,
                    'price_excl_vat': price_excl,
                    'price_incl_vat': price_incl,
                    'utm_url': utm_url,
                    'metrica': metrica_stats # Pass metrica stats
                })
            else:
                stats_list.append({
                    'channel': p.channel_handle,
                    'channel_name': channel_obj.name if channel_obj else '',
                    'post_name': p.name,
                    'post_id': p.post_id,
                    'date': post_date,
                    'views': 0, 'forwards': 0, 'replies': 0, 
                    'reactions_pos': 0, 'reactions_neg': 0, 'subscribers': 0,
                    'price_excl_vat': 0, 'price_incl_vat': 0, 'utm_url': ""
                })
                
    try:
        filepath = ExcelExporter.create_campaign_report(stats_list, campaign_name=campaign_name)
        document = FSInputFile(filepath)
        await callback.message.answer_document(
            document=document,
            caption=f"📊 <b>Отчёт по кампании «{campaign_name}»</b>",
            parse_mode="HTML"
        )
        os.remove(filepath)
    except Exception as e:
        logging.error(f"Error generating campaign Excel: {e}", exc_info=True)
        await callback.message.answer("❌ Ошибка при генерации отчёта.")




# ────────────────────────────── CHANNELS ──────────────────────────────

@dp.callback_query(F.data.startswith("channel_list"))
async def cb_channel_list(callback: CallbackQuery):
    parts = callback.data.split(":")
    page = int(parts[1]) if len(parts) > 1 else 0
    PAGE_SIZE = 40

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Channel).order_by(Channel.name))
        channels = result.scalars().all()

    if not channels:
        await callback.message.edit_text(
            "📭 База каналов пуста. Добавь каналы вручную или импортируй из Excel.",
            reply_markup=get_channels_menu()
        )
        return

    total_pages = max(1, (len(channels) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, total_pages - 1)
    
    start_idx = page * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_channels = channels[start_idx:end_idx]

    buttons = []
    for ch in page_channels:
        cpv_str = ""
        if ch.price_excl_vat and ch.avg_reach:
            cpv = ch.price_excl_vat / ch.avg_reach
            cpv_str = f" · CPV {cpv:,.0f}"
        label = f"@{ch.handle} · {ch.avg_reach or '?'} охват{cpv_str}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"channel_view:{ch.handle}")])
        
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Пред", callback_data=f"channel_list:{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="След ➡️", callback_data=f"channel_list:{page+1}"))
        
    if nav_row:
        buttons.append(nav_row)
        
    buttons.append([InlineKeyboardButton(text="⬅️ Меню базы", callback_data="menu_channels")])
    await callback.message.edit_text(
        f"📋 <b>Каналы в базе: {len(channels)}</b> (Стр {page+1}/{total_pages})",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@dp.callback_query(F.data.startswith("channel_view:"))
async def cb_channel_view(callback: CallbackQuery):
    handle = callback.data.split(":", 1)[1]
    async with AsyncSessionLocal() as session:
        ch = await session.get(Channel, handle)
    if not ch:
        await callback.answer("Канал не найден.", show_alert=True)
        return

    cpv = "—"
    if ch.price_excl_vat and ch.avg_reach and ch.avg_reach > 0:
        cpv = f"{ch.price_excl_vat / ch.avg_reach:,.1f} UZS"

    text = (
        f"📡 <b>@{ch.handle}</b>\n"
        f"Название: <b>{ch.name}</b>\n"
        f"Подписчики: <b>{ch.subscribers:,}</b>\n"
        f"Средний охват: <b>{ch.avg_reach:,}</b>\n\n"
        f"💰 Цена без НДС: <b>{ch.price_excl_vat:,} UZS</b>\n"
        f"💰 Цена с НДС: <b>{ch.price_incl_vat:,} UZS</b>\n"
        f"📊 CPV: <b>{cpv}</b>\n\n"
        f"🏷 Тема: {ch.topic or '—'}\n"
        f"🌍 Гео: {ch.geo or '—'}"
    ) if ch.subscribers else (
        f"📡 <b>@{ch.handle}</b>\n"
        f"Название: <b>{ch.name}</b>\n"
        f"Средний охват: <b>{ch.avg_reach or '—'}</b>\n\n"
        f"💰 Цена без НДС: <b>{ch.price_excl_vat or '—'}</b>\n"
        f"💰 Цена с НДС: <b>{ch.price_incl_vat or '—'}</b>\n"
        f"🏷 Тема: {ch.topic or '—'}\n"
        f"🌍 Гео: {ch.geo or '—'}"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_channel_view_keyboard(handle))


@dp.callback_query(F.data == "channel_add")
async def cb_channel_add(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ChannelAdd.waiting_for_handle)
    await callback.message.edit_text(
        "📡 Отправь @handle или ссылку канала (например, @digital_uz или t.me/digital_uz).\n\n"
        "⏳ Бот автоматически получит название, подписчиков и средний охват по 50 последним постам.",
        reply_markup=get_back_keyboard("menu_channels")
    )


@dp.message(ChannelAdd.waiting_for_handle)
async def process_channel_handle(message: Message, state: FSMContext):
    raw = message.text.strip().lstrip("@").replace("https://t.me/", "").replace("http://t.me/", "").split("/")[0]
    
    async with AsyncSessionLocal() as session:
        existing = await session.get(Channel, raw)
        if existing:
            await message.answer(f"⚠️ Канал @{raw} уже есть в базе. Для изменения данных перейди в меню 'Все каналы'.")
            await state.clear()
            return

    await message.answer("⏳ Анализирую канал, это займёт ~10 секунд...")
    try:
        info = await parser.get_channel_info(raw)
    except Exception as e:
        await message.answer(f"❌ Не удалось получить данные: {e}\nПроверь handle и попробуй снова.")
        return

    await state.update_data(
        handle=info['handle'],
        name=info['name'],
        subscribers=info['subscribers'],
        avg_reach=info['avg_reach']
    )
    await state.set_state(ChannelAdd.waiting_for_topic)
    await message.answer(
        f"✅ Нашёл канал: <b>{info['name']}</b>\n"
        f"👥 Подписчиков: <b>{info['subscribers']:,}</b>\n"
        f"👁 Средний охват: <b>{info['avg_reach']:,}</b>\n\n"
        f"Введи тематику канала (IT / финтех / новости / бизнес / другое):",
        parse_mode="HTML"
    )


@dp.message(ChannelAdd.waiting_for_topic)
async def process_channel_topic(message: Message, state: FSMContext):
    await state.update_data(topic=message.text.strip())
    await state.set_state(ChannelAdd.waiting_for_geo)
    await message.answer("🌍 Введи географию аудитории (например: Узбекистан, Казахстан, СНГ):")


@dp.message(ChannelAdd.waiting_for_geo)
async def process_channel_geo(message: Message, state: FSMContext):
    await state.update_data(geo=message.text.strip())
    await state.set_state(ChannelAdd.waiting_for_price_excl)
    await message.answer("💰 Введи цену размещения <b>без НДС</b> (в UZS, только цифры):", parse_mode="HTML")


@dp.message(ChannelAdd.waiting_for_price_excl)
async def process_channel_price_excl(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("⚠️ Неверный формат. Введи число, например 500000:")
        return
    await state.update_data(price_excl_vat=price)
    await state.set_state(ChannelAdd.waiting_for_price_incl)
    await message.answer("💰 НДС (12%) будет рассчитан автоматически. (в UZS):", parse_mode="HTML")


@dp.message(ChannelAdd.waiting_for_price_incl)
async def process_channel_price_incl(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("⚠️ Неверный формат. Введи число, например 600000:")
        return
    data = await state.get_data()
    await state.clear()

    async with AsyncSessionLocal() as session:
        ch = Channel(
            handle=data['handle'],
            name=data['name'],
            subscribers=data['subscribers'],
            avg_reach=data['avg_reach'],
            topic=data['topic'],
            geo=data['geo'],
            price_excl_vat=data['price_excl_vat'],
            price_incl_vat=price
        )
        await session.merge(ch)  # merge handles both insert and update
        await session.commit()

    await message.answer(
        f"✅ Канал <b>@{data['handle']}</b> добавлен в базу!",
        parse_mode="HTML",
        reply_markup=get_channels_menu()
    )


@dp.callback_query(F.data.startswith("channel_refresh:"))
async def cb_channel_refresh(callback: CallbackQuery):
    handle = callback.data.split(":", 1)[1]
    await callback.message.answer("⏳ Обновляю данные из Telegram...")
    try:
        info = await parser.get_channel_info(handle)
        async with AsyncSessionLocal() as session:
            ch = await session.get(Channel, handle)
            if ch:
                ch.subscribers = info['subscribers']
                ch.avg_reach = info['avg_reach']
                ch.name = info['name']
                await session.commit()
        await callback.message.answer(
            f"✅ Обновлено: <b>{info['name']}</b>\n👥 {info['subscribers']:,} подписчиков · 👁 {info['avg_reach']:,} охват",
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {e}")

async def background_refresh_channels(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Channel).where((Channel.avg_reach == None) | (Channel.avg_reach == 0)))
        channels = result.scalars().all()
        
    if not channels:
        await message.answer("✅ У всех каналов в базе уже посчитан охват.")
        return
        
    await message.answer(f"⏳ Начинаю фоновое обновление для {len(channels)} каналов...\nЭто займёт примерно {len(channels) * 4 // 60} мин. Я напишу, когда закончу.")
    
    success_count = 0
    fail_count = 0
    
    for ch in channels:
        try:
            info = await parser.get_channel_info(ch.handle)
            async with AsyncSessionLocal() as session:
                db_ch = await session.get(Channel, ch.handle)
                if db_ch:
                    db_ch.subscribers = info['subscribers']
                    db_ch.avg_reach = info['avg_reach']
                    db_ch.name = info['name']
                    await session.commit()
            success_count += 1
        except Exception as e:
            logging.error(f"Failed to auto-refresh channel {ch.handle}: {e}")
            fail_count += 1
            
        await asyncio.sleep(4)  # 4 seconds delay to avoid FloodWait
        
    await message.answer(f"✅ Фоновое обновление завершено!\nУспешно: {success_count}\nОшибок: {fail_count}")

@dp.callback_query(F.data == "channel_refresh_all")
async def cb_channel_refresh_all(callback: CallbackQuery):
    await callback.answer("Запускаю фоновый сборщик...")
    asyncio.create_task(background_refresh_channels(callback.message))


@dp.callback_query(F.data.startswith("channel_delete:"))
async def cb_channel_delete(callback: CallbackQuery):
    handle = callback.data.split(":", 1)[1]
    async with AsyncSessionLocal() as session:
        ch = await session.get(Channel, handle)
        if ch:
            await session.delete(ch)
            await session.commit()
    await callback.answer("🗑 Канал удалён")
    await cb_channel_list(callback)


@dp.callback_query(F.data.startswith("channel_edit_price:"))
async def cb_channel_edit_price(callback: CallbackQuery, state: FSMContext):
    handle = callback.data.split(":", 1)[1]
    await state.update_data(handle=handle)
    await state.set_state(ChannelEditPrice.waiting_for_price_excl)
    await callback.message.edit_text(
        "💰 Введи новую цену <b>без НДС</b> (UZS):", parse_mode="HTML",
        reply_markup=get_back_keyboard(f"channel_view:{handle}")
    )


@dp.message(ChannelEditPrice.waiting_for_price_excl)
async def process_edit_price_excl(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("⚠️ Введи число:")
        return
    await state.update_data(price_excl_vat=price)
    await state.set_state(ChannelEditPrice.waiting_for_price_incl)
    await message.answer("💰 НДС (12%) будет рассчитан автоматически. (UZS):", parse_mode="HTML")


@dp.message(ChannelEditPrice.waiting_for_price_incl)
async def process_edit_price_incl(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("⚠️ Введи число:")
        return
    data = await state.get_data()
    await state.clear()
    async with AsyncSessionLocal() as session:
        ch = await session.get(Channel, data['handle'])
        if ch:
            ch.price_excl_vat = data['price_excl_vat']
            ch.price_incl_vat = price
            await session.commit()
    await message.answer("✅ Цены обновлены.", reply_markup=get_channel_view_keyboard(data['handle']))


# ────────────────────────────── CHANNEL PICKER ──────────────────────────────

@dp.callback_query(F.data == "channel_pick")
async def cb_channel_pick(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🎯 <b>Подборщик каналов</b>\nВыбери режим подбора:",
        parse_mode="HTML", reply_markup=get_channel_picker_keyboard()
    )


@dp.callback_query(F.data == "pick_by_budget")
async def cb_pick_by_budget(callback: CallbackQuery, state: FSMContext):
    await state.update_data(pick_mode="budget")
    await state.set_state(ChannelPick.waiting_for_budget)
    await callback.message.edit_text(
        "💰 Введи максимальный бюджет <b>без НДС</b> в UZS (например: 5000000):",
        parse_mode="HTML", reply_markup=get_back_keyboard("channel_pick")
    )


@dp.callback_query(F.data == "pick_by_reach")
async def cb_pick_by_reach(callback: CallbackQuery, state: FSMContext):
    await state.update_data(pick_mode="reach")
    await state.set_state(ChannelPick.waiting_for_reach)
    await callback.message.edit_text(
        "📡 Введи желаемый минимальный охват (например: 50000):",
        reply_markup=get_back_keyboard("channel_pick")
    )


@dp.callback_query(F.data == "pick_combined")
async def cb_pick_combined(callback: CallbackQuery, state: FSMContext):
    await state.update_data(pick_mode="combined")
    await state.set_state(ChannelPick.waiting_for_budget)
    await callback.message.edit_text(
        "🎯 Введи максимальный бюджет <b>без НДС</b> в UZS:",
        parse_mode="HTML", reply_markup=get_back_keyboard("channel_pick")
    )


async def _run_picker(message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    budget = data.get('budget')
    reach_target = data.get('reach_target')
    mode = data.get('pick_mode', 'budget')

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Channel).where(Channel.price_excl_vat.isnot(None), Channel.avg_reach.isnot(None))
        )
        channels = result.scalars().all()

    if not channels:
        await message.answer("❌ В базе нет каналов с ценами и охватом.")
        return

    # Sort by CPV ascending (best efficiency first)
    channels_sorted = sorted(channels, key=lambda c: (c.price_excl_vat / c.avg_reach) if c.avg_reach else float('inf'))

    selected = []
    total_budget = 0
    total_reach = 0

    for ch in channels_sorted:
        if mode == "budget":
            if total_budget + ch.price_excl_vat <= budget:
                selected.append(ch)
                total_budget += ch.price_excl_vat
                total_reach += ch.avg_reach or 0
        elif mode == "reach":
            selected.append(ch)
            total_budget += ch.price_excl_vat
            total_reach += ch.avg_reach or 0
            if total_reach >= reach_target:
                break
        elif mode == "combined":
            if total_budget + ch.price_excl_vat <= budget:
                selected.append(ch)
                total_budget += ch.price_excl_vat
                total_reach += ch.avg_reach or 0
                if total_reach >= reach_target:
                    break

    if not selected:
        await message.answer("😔 Не удалось подобрать каналы с такими параметрами.")
        return

    await message.answer(f"⏳ Подобрано {len(selected)} каналов. Генерирую Excel...")
    filepath = ExcelExporter.create_channel_selection_report(selected)
    doc = FSInputFile(filepath)
    await message.answer_document(
        document=doc,
        caption=(
            f"🎯 <b>Подборка каналов</b>\n"
            f"Каналов: <b>{len(selected)}</b>\n"
            f"Суммарный охват: <b>{total_reach:,}</b>\n"
            f"Бюджет без НДС: <b>{total_budget:,} UZS</b>"
        ),
        parse_mode="HTML"
    )
    os.remove(filepath)


@dp.message(ChannelPick.waiting_for_budget)
async def process_pick_budget(message: Message, state: FSMContext):
    try:
        budget = float(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("⚠️ Введи число:")
        return
    data = await state.get_data()
    await state.update_data(budget=budget)
    if data.get('pick_mode') == 'combined':
        await state.set_state(ChannelPick.waiting_for_reach_min)
        await message.answer("📡 Теперь введи минимальный желаемый охват:")
    else:
        await _run_picker(message, state)


@dp.message(ChannelPick.waiting_for_reach)
async def process_pick_reach(message: Message, state: FSMContext):
    try:
        reach = int(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("⚠️ Введи число:")
        return
    await state.update_data(reach_target=reach)
    await _run_picker(message, state)


@dp.message(ChannelPick.waiting_for_reach_min)
async def process_pick_reach_min(message: Message, state: FSMContext):
    try:
        reach = int(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("⚠️ Введи число:")
        return
    await state.update_data(reach_target=reach)
    await _run_picker(message, state)


# ────────────────────────────── CHANNEL IMPORT ──────────────────────────────

@dp.callback_query(F.data == "channel_import")
async def cb_channel_import(callback: CallbackQuery):
    filepath = ExcelExporter.create_channel_import_template()
    doc = FSInputFile(filepath)
    await callback.message.answer_document(
        document=doc,
        caption=(
            "📥 <b>Шаблон для импорта каналов</b>\n\n"
            "Заполни таблицу и отправь мне файл .xlsx обратно.\n"
            "Колонки: handle, name, topic, geo, price_excl_vat, price_incl_vat"
        ),
        parse_mode="HTML"
    )
    os.remove(filepath)



@dp.message(F.document, StateFilter(None))
async def handle_document(message: Message):
    """Handle uploaded Excel files for channel import."""
    if not message.document.file_name.endswith('.xlsx'):
        return
    await message.answer("⏳ Обрабатываю файл...")
    file = await message.bot.get_file(message.document.file_id)
    import tempfile
    tmp_path = os.path.join(tempfile.gettempdir(), "channel_import.xlsx")
    await message.bot.download_file(file.file_path, tmp_path)
    try:
        channels_data = ExcelExporter.parse_channel_import(tmp_path)
        count = 0
        async with AsyncSessionLocal() as session:
            for row in channels_data:
                existing = await session.get(Channel, row['handle'])
                if existing:
                    if row.get('name'): existing.name = row['name']
                    if row.get('topic'): existing.topic = row['topic']
                    if row.get('geo'): existing.geo = row['geo']
                    if row.get('price_excl_vat'): existing.price_excl_vat = row['price_excl_vat']
                    if row.get('price_incl_vat'): existing.price_incl_vat = row['price_incl_vat']
                else:
                    ch = Channel(**row)
                    session.add(ch)
                count += 1
            await session.commit()
        await message.answer(
            f"✅ Импортировано каналов: <b>{count}</b>",
            parse_mode="HTML", reply_markup=get_channels_menu()
        )
    except Exception as e:
        logging.error(f"Import error: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка при импорте: {e}")
    finally:
        os.remove(tmp_path)


# ────────────────────────────── UTM GENERATOR ──────────────────────────────

@dp.callback_query(F.data == "menu_utm")
async def cb_menu_utm(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🔗 <b>UTM-генератор</b>\n\nВыбери режим:\n"
        "• <b>Одиночная ссылка</b> — для одного конкретного канала.\n"
        "• <b>Пакетно (Excel)</b> — выгрузит ВСЮ базу каналов в виде таблицы, где для каждого канала будет сгенерирована своя UTM-метка.",
        parse_mode="HTML",
        reply_markup=get_utm_menu()
    )

def slugify(text: str) -> str:
    import unicodedata
    text = text.lower().replace(" ", "_")
    return re.sub(r'[^a-z0-9_]', '', text)

# --- SINGLE UTM ---
@dp.callback_query(F.data == "utm_single")
async def cb_utm_single(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UTMSingle.waiting_for_url)
    await callback.message.edit_text(
        "🔗 Введи базовый URL целевой страницы (например: https://site.uz/promo):",
        reply_markup=get_back_keyboard("menu_utm")
    )

@dp.message(UTMSingle.waiting_for_url)
async def process_utm_single_url(message: Message, state: FSMContext):
    await state.update_data(url=message.text.strip())
    await state.set_state(UTMSingle.waiting_for_campaign)
    await message.answer("✍️ Введи название рекламной кампании (например: Spring Sale 2024):")

@dp.message(UTMSingle.waiting_for_campaign)
async def process_utm_single_campaign(message: Message, state: FSMContext):
    await state.update_data(campaign=message.text.strip())
    await state.set_state(UTMSingle.waiting_for_channel)
    await message.answer("📣 Введи @handle канала (например: @digital_uz):")

@dp.message(UTMSingle.waiting_for_channel)
async def process_utm_single_channel(message: Message, state: FSMContext):
    data = await state.get_data()
    base_url = data['url']
    campaign_name = data['campaign']
    channel = message.text.strip().lstrip('@').replace("https://t.me/", "").split("/")[0]
    
    campaign_slug = slugify(campaign_name)
    sep = "&" if "?" in base_url else "?"
    full_url = f"{base_url}{sep}utm_source=telegram&utm_medium={channel}&utm_campaign={campaign_slug}"
    
    await state.clear()
    await message.answer(
        f"✅ <b>Готово!</b>\n\n<b>Канал:</b> @{channel}\n<b>Кампания:</b> {campaign_name}\n\n"
        f"🔗 Ссылка:\n<code>{full_url}</code>",
        parse_mode="HTML",
        reply_markup=get_back_keyboard("menu_utm")
    )

# --- BULK UTM ---
@dp.callback_query(F.data == "utm_bulk")
async def cb_utm_bulk(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UTMBulk.waiting_for_url)
    await callback.message.edit_text(
        "📦 <b>Пакетная генерация</b>\n\nВведи базовый URL целевой страницы:",
        parse_mode="HTML",
        reply_markup=get_back_keyboard("menu_utm")
    )

@dp.message(UTMBulk.waiting_for_url)
async def process_utm_bulk_url(message: Message, state: FSMContext):
    await state.update_data(url=message.text.strip())
    await state.set_state(UTMBulk.waiting_for_campaign)
    await message.answer("✍️ Введи название рекламной кампании:")

@dp.message(UTMBulk.waiting_for_campaign)
async def process_utm_bulk_campaign(message: Message, state: FSMContext):
    await state.update_data(campaign=message.text.strip())
    await state.set_state(UTMBulk.waiting_for_file)
    await message.answer("📥 Теперь пришли мне Excel-файл со списком каналов (в формате шаблона импорта):")

@dp.message(UTMBulk.waiting_for_file, F.document)
async def process_utm_bulk_file(message: Message, state: FSMContext):
    if not message.document.file_name.endswith('.xlsx'):
        await message.answer("⚠️ Пожалуйста, пришли файл в формате .xlsx")
        return
        
    data = await state.get_data()
    base_url = data['url']
    campaign_name = data['campaign']
    await state.clear()
    
    await message.answer("⏳ Обрабатываю файл и генерирую UTM...")
    
    file = await message.bot.get_file(message.document.file_id)
    import tempfile
    tmp_input = os.path.join(tempfile.gettempdir(), f"utm_input_{message.document.file_id}.xlsx")
    await message.bot.download_file(file.file_path, tmp_input)
    
    try:
        # We reuse the parser from exporter to get channel data from the file
        channels_data = ExcelExporter.parse_channel_import(tmp_input)
        
        if not channels_data:
            await message.answer("❌ В файле не найдено корректных данных о каналах.")
            return

        # Convert dicts to simple objects for create_utm_bulk_report
        class SimpleChannel:
            def __init__(self, **kwargs):
                for k, v in kwargs.items(): setattr(self, k, v)

        channels = [SimpleChannel(**d) for d in channels_data]
        
        filepath = ExcelExporter.create_utm_bulk_report(channels, base_url, campaign_name)
        doc = FSInputFile(filepath)
        await message.answer_document(
            document=doc,
            caption=f"📦 <b>Пакетные UTM сгенерированы!</b>\n\nКампания: {campaign_name}\nКаналов обработано: {len(channels)}",
            parse_mode="HTML",
            reply_markup=get_back_keyboard("menu_utm")
        )
        os.remove(filepath)
    except Exception as e:
        logging.error(f"UTM Bulk Error: {e}")
        await message.answer(f"❌ Произошла ошибка при обработке: {e}")
    finally:
        if os.path.exists(tmp_input):
            os.remove(tmp_input)


# ────────────────────────────── SETTINGS & METRICA ──────────────────────────────

@dp.callback_query(F.data == "menu_settings")
async def cb_menu_settings(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "⚙️ <b>Настройки</b>\n\nЗдесь ты можешь настроить интеграции и параметры бота.",
        parse_mode="HTML",
        reply_markup=get_settings_menu(is_admin=await is_admin(callback.from_user.id))
    )

@dp.callback_query(F.data == "settings_metrica")
async def cb_settings_metrica(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        cid_res = await session.get(Setting, "metrica_counter_id")
        tok_res = await session.get(Setting, "metrica_token")
        cid = cid_res.value if cid_res else "❌ Не указан"
        tok = "✅ Указан" if tok_res and tok_res.value else "❌ Не указан"
        
    await callback.message.edit_text(
        f"📊 <b>Яндекс.Метрика</b>\n\n"
        f"<b>Counter ID:</b> <code>{cid}</code>\n"
        f"<b>OAuth Токен:</b> {tok}\n\n"
        f"Для получения токена перейди в <a href='https://oauth.yandex.ru/authorize?response_type=token&client_id=YOUR_CLIENT_ID'>Яндекс OAuth</a>.",
        parse_mode="HTML",
        reply_markup=get_metrica_settings_menu(),
        disable_web_page_preview=True
    )

@dp.callback_query(F.data == "metrica_set_id")
async def cb_metrica_set_id(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MetricaSettings.waiting_for_id)
    await callback.message.edit_text(
        "🔢 Введи ID счетчика Яндекс.Метрики (только цифры):",
        reply_markup=get_back_keyboard("settings_metrica")
    )

@dp.message(MetricaSettings.waiting_for_id)
async def process_metrica_id(message: Message, state: FSMContext):
    cid = message.text.strip()
    if not cid.isdigit():
        await message.answer("⚠️ ID должен состоять только из цифр. Попробуй еще раз:")
        return
        
    async with AsyncSessionLocal() as session:
        await session.merge(Setting(key="metrica_counter_id", value=cid))
        await session.commit()
    
    await state.clear()
    await message.answer(f"✅ Counter ID <code>{cid}</code> сохранен!", parse_mode="HTML",
                         reply_markup=get_settings_menu(is_admin=await is_admin(callback.from_user.id)))

@dp.callback_query(F.data == "metrica_set_token")
async def cb_metrica_set_token(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MetricaSettings.waiting_for_token)
    await callback.message.edit_text(
        "🔑 Введи твой Яндекс OAuth Токен:",
        reply_markup=get_back_keyboard("settings_metrica")
    )

@dp.message(MetricaSettings.waiting_for_token)
async def process_metrica_token(message: Message, state: FSMContext):
    token = message.text.strip()
    async with AsyncSessionLocal() as session:
        await session.merge(Setting(key="metrica_token", value=token))
        await session.commit()
    
    await state.clear()
    await message.answer("✅ OAuth Токен успешно сохранен!",
                         reply_markup=get_settings_menu(is_admin=await is_admin(callback.from_user.id)))


@dp.callback_query(F.data.startswith("channel_add_missing:"))
async def cb_channel_add_missing(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    handle = callback.data.split(":")[1]
    logging.info(f"User clicked add missing channel: {handle}")
    await state.update_data(handle=handle)
    try:
        ch_info = await parser.get_channel_info(handle)
        name = ch_info.get("name", handle)
        subs = ch_info.get("subscribers", 0)
        reach = ch_info.get("avg_reach", 0)
        await state.update_data(name=name, subscribers=subs, avg_reach=reach)
        await state.set_state(ChannelAdd.waiting_for_topic)
        await callback.message.edit_text(
            f"🆕 <b>Добавление канала @{handle}</b>\n\n"
            f"Название из TG: <b>{name}</b>\n"
            f"Подписчики: <b>{subs:,}</b>\n"
            f"Средний охват: <b>{reach:,}</b>\n\n"
            f"Введи тематику канала (IT / бизнес / новости / другое):",
            parse_mode="HTML",
            reply_markup=get_back_keyboard("menu_channels")
        )
    except Exception as e:
        logging.error(f"Error in cb_channel_add_missing: {e}")
        await state.set_state(ChannelAdd.waiting_for_topic)
        await state.update_data(name=handle, subscribers=0, avg_reach=0)
        await callback.message.edit_text(
            f"🆕 <b>Добавление канала @{handle}</b>\n\n"
            f"⚠️ Не удалось получить данные автоматически.\n\n"
            f"Введи тематику канала:",
            parse_mode="HTML",
            reply_markup=get_back_keyboard("menu_channels")
        )



@dp.callback_query(F.data == "settings_users")
async def cb_settings_users(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    await callback.message.edit_text("👥 <b>Управление доступом</b>\nЗдесь вы можете добавлять коллег.", parse_mode="HTML", reply_markup=get_users_menu())

@dp.callback_query(F.data == "user_add")
async def cb_user_add(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserAdd.waiting_for_id)
    await callback.message.edit_text("👤 Введите Telegram ID пользователя или перешлите мне его сообщение:", reply_markup=get_back_keyboard("settings_users"))

@dp.message(UserAdd.waiting_for_id)
async def process_user_id(message: Message, state: FSMContext):
    target_id = None
    if message.forward_from:
        target_id = message.forward_from.id
    else:
        try: target_id = int(message.text.strip())
        except: pass
    
    if not target_id:
        await message.answer("⚠️ Не удалось определить ID. Введите числом или перешлите сообщение.")
        return
    
    async with AsyncSessionLocal() as session:
        new_user = User(user_id=target_id, role='user', username=message.from_user.username)
        await session.merge(new_user)
        await session.commit()
    
    await state.clear()
    await message.answer(f"✅ Пользователь {target_id} добавлен!", reply_markup=get_users_menu())

@dp.callback_query(F.data == "user_list")
async def cb_user_list(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(User))
        users = res.scalars().all()
    
    text = "👥 <b>Список пользователей:</b>\n\n"
    for u in users:
        text += f"• ID: <code>{u.user_id}</code> ({u.role})\n"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard("settings_users"))



@dp.message(Command("settings"))
async def cmd_settings(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await message.answer("🚫 Доступ к настройкам ограничен.")
        return
    await state.clear()
    await message.answer("⚙️ <b>Настройки</b>", parse_mode="HTML", reply_markup=get_settings_menu(is_admin=True))


async def main():
    print("Initializing Database...")
    await init_db()
    
    print("Starting Telethon Parser...")
    await parser.start()
    
    print("Starting Background Tracker...")
    start_tracker(parser)
    
    print("Setting up Bot Commands...")
    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="campaign", description="Кампании"),
        BotCommand(command="post", description="Добавить пост"),
        BotCommand(command="channels", description="База каналов"),
        BotCommand(command="utm", description="UTM-генератор"),
        BotCommand(command="settings", description="Настройки")
    ])
    print("Starting Bot Polling...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped!")

