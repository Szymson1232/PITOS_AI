
import httpx

BASE_URL = "https://api.the-odds-api.com/v4"


class OddsAPI:

    def __init__(self, api_key):
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            timeout=30,
            base_url=BASE_URL
        )

        self.quota = {}

    async def request(self, endpoint, params=None):

        params = params or {}
        params["apiKey"] = self.api_key

        response = await self.client.get(
            endpoint,
            params=params
        )

        self.quota = {
            "used": response.headers.get("x-requests-used"),
            "remaining": response.headers.get("x-requests-remaining"),
            "last": response.headers.get("x-requests-last")
        }

        response.raise_for_status()

        return response.json()

    async def get_sports(self):
        return await self.request(
            "/sports",
            {"all": "false"}
        )

    async def get_events(self, sport_key):
        return await self.request(
            f"/sports/{sport_key}/events"
        )

    async def get_odds(self, sport_key):
        return await self.request(
            f"/sports/{sport_key}/odds",
            {
                "regions": "eu",
                "markets": "h2h",
                "oddsFormat": "decimal"
            }
        )

    async def close(self):
        await self.client.aclose()
