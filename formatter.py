from datetime import datetime

class StatsFormatter:
    @staticmethod
    def format_number(num: int) -> str:
        """Formats numbers with comma separation."""
        return f"{num:,}"

    @staticmethod
    def format_stats(data: dict) -> str:
        """
        Formats the post statistics into a readable message.
        
        Expected data structure:
        {
            'channel': str,
            'post_id': int,
            'date': datetime,
            'views': int,
            'forwards': int,
            'replies': int,
            'reactions_count': int,
            'top_reactions': list of (emoji, count) tuples
        }
        """
        # Format date
        date_str = data['date'].strftime('%Y-%m-%d %H:%M') if isinstance(data['date'], datetime) else str(data['date'])
        
        # Format metrics
        views = StatsFormatter.format_number(data.get('views', 0))
        forwards = StatsFormatter.format_number(data.get('forwards', 0))
        replies = StatsFormatter.format_number(data.get('replies', 0))
        reactions = StatsFormatter.format_number(data.get('reactions_count', 0))
        
        # Build reactions string
        top_reactions = data.get('top_reactions', [])
        reactions_details = ""
        if top_reactions:
            details_list = [f"{emoji} {count}" for emoji, count in top_reactions]
            reactions_details = "   " + " | ".join(details_list)

        # Escape special characters for HTML if necessary (basic implementation)
        # In HTML, <, >, & should be escaped. Usernames usually don't have them but we should be safe.
        def escape(s):
            return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        channel_escaped = escape(data['channel'])
        
        message = (
            "📊 <b>Статистика поста</b>\n\n"
            f"📌 Канал: @{channel_escaped}\n"
            f"📝 Пост: <a href=\"https://t.me/{channel_escaped}/{data['post_id']}\">t.me/{channel_escaped}/{data['post_id']}</a>\n"
            f"📅 Дата: {date_str}\n\n"
            f"👁 Просмотры: {views}\n"
            f"🔄 Репосты: {forwards}\n"
            f"💬 Комментарии: {replies}\n"
            f"❤️ Реакции: {reactions}\n"
        )
        
        if reactions_details:
            message += f"{reactions_details}\n"
            
        return message

    @staticmethod
    def _format_delta(new_val: int, old_val: int) -> str:
        """Formats the difference between two values as a delta string."""
        delta = new_val - old_val
        if delta > 0:
            return f" (<b>+{StatsFormatter.format_number(delta)}</b>)"
        elif delta < 0:
            return f" ({StatsFormatter.format_number(delta)})"
        return ""

    @staticmethod
    def format_stats_update(old_stats: dict, new_stats: dict) -> str:
        """
        Formats an hourly stats update with deltas compared to previous values.
        """
        def escape(s):
            return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        channel = escape(new_stats['channel'])
        post_id = new_stats['post_id']

        views = StatsFormatter.format_number(new_stats.get('views', 0))
        forwards = StatsFormatter.format_number(new_stats.get('forwards', 0))
        replies = StatsFormatter.format_number(new_stats.get('replies', 0))
        reactions = StatsFormatter.format_number(new_stats.get('reactions_count', 0))

        views_delta = StatsFormatter._format_delta(new_stats.get('views', 0), old_stats.get('views', 0))
        forwards_delta = StatsFormatter._format_delta(new_stats.get('forwards', 0), old_stats.get('forwards', 0))
        replies_delta = StatsFormatter._format_delta(new_stats.get('replies', 0), old_stats.get('replies', 0))
        reactions_delta = StatsFormatter._format_delta(new_stats.get('reactions_count', 0), old_stats.get('reactions_count', 0))

        # Build reactions string
        top_reactions = new_stats.get('top_reactions', [])
        reactions_details = ""
        if top_reactions:
            details_list = [f"{emoji} {count}" for emoji, count in top_reactions]
            reactions_details = "   " + " | ".join(details_list)

        message = (
            "📡 <b>Обновление статистики</b>\n\n"
            f"📌 Канал: @{channel}\n"
            f"📝 Пост: <a href=\"https://t.me/{channel}/{post_id}\">t.me/{channel}/{post_id}</a>\n\n"
            f"👁 Просмотры: {views}{views_delta}\n"
            f"🔄 Репосты: {forwards}{forwards_delta}\n"
            f"💬 Комментарии: {replies}{replies_delta}\n"
            f"❤️ Реакции: {reactions}{reactions_delta}\n"
        )

        if reactions_details:
            message += f"{reactions_details}\n"

        return message
