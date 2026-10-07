"""Script temporaneo di SOLA LETTURA per esplorare il DB e ricalcolare i rendimenti."""
import os
import json
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))


def dump(name, limit=50):
    try:
        r = sb.table(name).select("*").execute()
        print(f"\n=== {name} === righe: {len(r.data)}")
        if r.data:
            print("colonne:", list(r.data[0].keys()))
            for row in r.data[:limit]:
                print(json.dumps(row, default=str, ensure_ascii=False))
    except Exception as e:
        print(f"\n=== {name} === ERRORE: {e}")


# Vista annuale (output attuale)
dump("v_portafoglio_rendimento_annuo")

# Transazioni grezze per capire acquisti/vendite per anno
dump("transaction", limit=500)
