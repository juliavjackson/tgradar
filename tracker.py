import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy.future import select
from sqlalchemy import update
from database import AsyncSessionLocal, Post, PostMetricsHistory

# Ensure you pass your parser instance to start_tracker
async def tracking_loop(parser):
    """Background task that sends hourly stat updates for tracked posts."""
    logging.info("Tracking loop started.")
    while True:
        try:
            async with AsyncSessionLocal() as session:
                # Find all active posts
                result = await session.execute(select(Post).where(Post.is_tracking_active == True))
                active_posts = result.scalars().all()
                
                now = datetime.utcnow()
                
                for post in active_posts:
                    # Check 48h expiration
                    if now - post.added_at > timedelta(hours=48):
                        post.is_tracking_active = False
                        await session.commit()
                        logging.info(f"Tracking stopped for post {post.id} (48h reached).")
                        continue
                        
                    # Fetch stats
                    try:
                        stats = await parser.get_post_stats(post.channel_handle, post.post_id)
                        if stats:
                            # We can also classify positive/negative reactions here or parser does it
                            reactions = stats.get('reactions', [])
                            pos_count = 0
                            neg_count = 0
                            
                            # Simple classification
                            positive_emojis = ['👍', '❤️', '🔥', '🎉', '😂', '🤩', '👏', '🥳', '❤️‍🔥', '💯', '🌟', '🥰']
                            negative_emojis = ['👎', '😢', '😡', '🤮', '💔', '😱', '😔', '🤬']
                            
                            for emoji, count in stats.get('top_reactions', []):
                                if emoji in positive_emojis:
                                    pos_count += count
                                elif emoji in negative_emojis:
                                    neg_count += count
                                    
                            history = PostMetricsHistory(
                                post_id=post.id,
                                views=stats.get('views', 0),
                                forwards=stats.get('forwards', 0),
                                replies=stats.get('replies', 0),
                                positive_reactions=pos_count,
                                negative_reactions=neg_count,
                                subscribers=stats.get('subscribers', 0)
                            )
                            session.add(history)
                            await session.commit()
                    except Exception as e:
                        logging.error(f"Error fetching stats for post {post.id}: {e}")
                        
            # Sleep for 1 hour
            await asyncio.sleep(3600)
        except Exception as e:
            logging.error(f"Error in tracking loop: {e}", exc_info=True)
            await asyncio.sleep(60)

def start_tracker(parser):
    asyncio.create_task(tracking_loop(parser))
