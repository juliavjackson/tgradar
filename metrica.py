import aiohttp
import logging
from datetime import datetime, timedelta

class YandexMetricaClient:
    BASE_URL = "https://api-metrika.yandex.net/stat/v1/data"

    def __init__(self, token: str, counter_id: str):
        self.token = token
        self.counter_id = counter_id
        self.headers = {
            "Authorization": f"OAuth {token}"
        }

    async def get_utm_stats(self, campaign_slug: str, channel_handle: str, days: int = 7):
        """Fetches stats for a specific UTM combination."""
        if not self.token or not self.counter_id:
            return None

        date_to = datetime.now().strftime("%Y-%m-%d")
        date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        params = {
            "ids": self.counter_id,
            "metrics": "ym:s:visits,ym:s:bounceRate,ym:s:averageVisitDurationSeconds,ym:s:pageDepth",
            "dimensions": "ym:s:utmSource,ym:s:utmMedium,ym:s:utmCampaign",
            "filters": f"ym:s:utmSource=='telegram' AND ym:s:utmMedium=='{channel_handle}' AND ym:s:utmCampaign=='{campaign_slug}'",
            "date1": date_from,
            "date2": date_to,
            "accuracy": "full"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.BASE_URL, params=params, headers=self.headers) as response:
                    if response.status != 200:
                        err_text = await response.text()
                        logging.error(f"Yandex.Metrica API error ({response.status}): {err_text}")
                        return None
                    
                    data = await response.json()
                    
                    if not data.get("data"):
                        return {
                            "visits": 0,
                            "bounce_rate": 0,
                            "duration": 0,
                            "depth": 0
                        }
                    
                    totals = data.get("totals", [0, 0, 0, 0])
                    return {
                        "visits": int(totals[0]),
                        "bounce_rate": float(totals[1]) / 100.0 if totals[1] else 0, # Convert to 0.xx for Excel % format
                        "duration": int(totals[2]),
                        "depth": float(totals[3])
                    }
        except Exception as e:
            logging.error(f"Error fetching Yandex.Metrica stats: {e}")
            return None
