import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv(dotenv_path="../.env")


class SupabaseClient:
    def __init__(self) -> None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        if not url:
            raise ValueError("SUPABASE_URL is missing from .env")

        if not key:
            raise ValueError("SUPABASE_SERVICE_ROLE_KEY is missing from .env")

        self.client: Client = create_client(url, key)

    def test_connection(self):
        return self.client.table("bookings").select("*").limit(1).execute()