import os
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Carica le variabili dal file .env
load_dotenv() 
# Reference Supabase: https://supabase.com/docs/reference/python/eq

url: str = os.getenv("SUPABASE_URL","")
key: str = os.getenv("SUPABASE_KEY","")
supabase: Client = create_client(url, key)

# Esempio SELECT
response = (
    supabase.table("etf_data")
    .select("*")
    .execute()
)

print(response)

# Esempio INSERT
response = (
    supabase.table("etf_data")
    .insert({"id": 1, "name": "Pluto"})
    .execute()
)

# Esempio UPDATE
response = (
    supabase.table("instruments")
    .update({"name": "piano"})
    .eq("id", 1)
    .execute()
)
# Esempio DELETE
response = (
    supabase.table("countries")
    .delete()
    .eq("id", 1)
    .execute()
)