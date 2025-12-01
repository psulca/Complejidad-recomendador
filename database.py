import os
from typing import Optional
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_supabase: Optional[Client] = None


def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            raise ValueError(
                "Las variables de entorno SUPABASE_URL y SUPABASE_KEY deben estar configuradas en el archivo .env"
            )
        
        _supabase = create_client(supabase_url, supabase_key)
    return _supabase

