from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from datetime import datetime
import os

from database import SessionLocal
from models import PlayerMergeQueue, PlayerRegistry

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class ResolveRequest(BaseModel):
    action: str  # "merge" or "new"
    canonical: str = None

@router.get("/merge-queue")
def get_merge_queue(db: Session = Depends(get_db), x_admin_key: str = Header(None)):
    # Assuming VITE_ADMIN_MODE is loosely validated if at all from backend, but standard is fine
    # Actually, the user asked to just return PlayerMergeQueue
    # For now, no strict auth block unless requested, but let's be safe.
    
    records = db.query(PlayerMergeQueue).filter(PlayerMergeQueue.status == 'pending').order_by(desc(PlayerMergeQueue.fuzzy_score)).all()
    
    return [
        {
            "id": r.id,
            "raw_name": r.raw_name,
            "matched_canonical": r.matched_canonical,
            "fuzzy_score": r.fuzzy_score,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
        for r in records
    ]

@router.patch("/merge-queue/{queue_id}/resolve")
def resolve_merge(queue_id: int, req: ResolveRequest, db: Session = Depends(get_db), x_admin_key: str = Header(None)):
    queue_item = db.query(PlayerMergeQueue).filter(PlayerMergeQueue.id == queue_id).first()
    if not queue_item:
        raise HTTPException(status_code=404, detail="Queue item not found")
        
    if req.action == "merge":
        if not req.canonical:
            raise HTTPException(status_code=400, detail="canonical name required for merge")
        
        # Find player in registry
        player = db.query(PlayerRegistry).filter(PlayerRegistry.name == req.canonical).first()
        if not player:
            # Create player
            player = PlayerRegistry(
                identifier=f"generated-{int(datetime.now().timestamp())}",
                name=req.canonical,
                unique_name=req.canonical
            )
            db.add(player)
            db.flush()
            
        queue_item.resolved_player_id = player.identifier
        queue_item.status = 'merged'
        
    elif req.action == "new":
        player = PlayerRegistry(
            identifier=f"generated-{int(datetime.now().timestamp())}",
            name=queue_item.raw_name,
            unique_name=queue_item.raw_name
        )
        db.add(player)
        db.flush()
        
        queue_item.resolved_player_id = player.identifier
        queue_item.status = 'new_player'
        
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
        
    db.commit()
    return {"status": "success", "action": req.action, "resolved_player_id": queue_item.resolved_player_id}
