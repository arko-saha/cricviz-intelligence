import logging
import requests
import config

logger = logging.getLogger("cricviz.commentary")


def fetch_match_commentary(match_id: str) -> dict:
    """
    Fetches full match commentary from CricAPI.
    Returns dict mapping "innings_over_ball" -> "commentary string".
    Does not block the ingestion transaction if it fails.
    """
    if not config.CRICAPI_KEY:
        return {}
        
    url = "https://api.cricapi.com/v1/match_commentary"
    params = {
        "apikey": config.CRICAPI_KEY,
        "id": match_id,
        "offset": 0
    }
    
    try:
        resp = requests.get(url, params=params, timeout=3.0)
        
        if resp.status_code == 429:
            logger.warning("CricAPI rate limited")
            return {}
            
        if resp.status_code == 200:
            data = resp.json()
            commentary_dict = {}
            # Assume data contains a list of ball events in 'data'
            for ball in data.get("data", []):
                inn = ball.get("innings", 1)
                ov = ball.get("over", 0)
                b = ball.get("ball", 1)
                comm = ball.get("text", "")
                if comm:
                    commentary_dict[f"{inn}_{ov}_{b}"] = comm
                    
            return commentary_dict
            
    except Exception as e:
        logger.warning(f"CricAPI commentary fetch failed: {e}")
        
    return {}
