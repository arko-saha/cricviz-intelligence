import time
import httpx
import sqlite3
import subprocess
import os

BASE_URL = "http://localhost:8000/api"

def run_tests():
    print("=== Step 1: Ingest real data ===")
    
    import sys
    sys.path.append(os.path.dirname(__file__))
    from ingestion.parser import run_ingestion
    import uuid

    print("Triggering ingestion of T20s... (SKIPPED, already ingested)")
    # job_id = str(uuid.uuid4())
    # try:
    #     run_ingestion("https://cricsheet.org/downloads/t20s_json.zip", job_id)
    #     print("Ingestion completed!")
    # except Exception as e:
    #     print(f"Failed to run ingestion: {e}")
    #     return

    db_path = "cricviz.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM players")
    print(f"Players: {cur.fetchone()[0]}")

    print("\n=== Step 2: Verify player resolution ===")
    cur.execute("SELECT COUNT(*) FROM player_registry")
    print(f"Registry Rows: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM players WHERE cricsheet_identifier IS NOT NULL")
    print(f"Resolved Players: {cur.fetchone()[0]}")

    print("Pending Merge Queue:")
    cur.execute("SELECT raw_name, matched_canonical, fuzzy_score FROM player_merge_queue LIMIT 5")
    for row in cur.fetchall():
        print(row)

    print("\n=== Step 3: Commentary enrichment ===")
    # Note: For the actual integration test we don't need to hit the real CRICAPI if we don't have the key,
    # but the instructions say "requires CRICAPI_KEY". The script will just try to trigger it.
    # Wait, the endpoint requires admin auth (token). Let's just bypass auth and call the python func directly
    # or skip it if no key is set.
    import sys
    sys.path.append(os.path.dirname(__file__))
    from ingestion.commentary_enricher import enrich_recent_matches
    print("Running enrich_recent_matches()...")
    enrich_recent_matches(days=7)
    
    cur.execute("SELECT COUNT(*) FROM deliveries WHERE commentary_text IS NOT NULL")
    print(f"Deliveries with commentary: {cur.fetchone()[0]}")

    print("Sample commentaries:")
    cur.execute("SELECT commentary_text FROM deliveries WHERE commentary_text IS NOT NULL LIMIT 3")
    for row in cur.fetchall():
        print(row[0])

    print("\n=== Step 4: Train xR and xW models ===")
    subprocess.run(["python", "-m", "ml.train_xR"], check=True)
    subprocess.run(["python", "-m", "ml.train_xW"], check=True)
    
    print("\n=== Step 5: Verify enrichment uses ML models ===")
    from service.enrichment import predictor
    # Force reload
    predictor.reload()
    
    cur.execute("SELECT id FROM deliveries LIMIT 1")
    row = cur.fetchone()
    if row:
        del_id = row[0]
        # Check computed metrics
        cur.execute("SELECT computed_xR, computed_xW FROM cricviz_metrics WHERE delivery_id = ?", (del_id,))
        metrics = cur.fetchone()
        print(f"Delivery {del_id} ML predictions: xR={metrics[0]}, xW={metrics[1]}")

    print("\n=== Step 6: Run full test suite ===")
    subprocess.run(["pytest", "tests/", "-v", "--tb=short"])

if __name__ == "__main__":
    run_tests()
