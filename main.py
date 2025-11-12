import os
from datetime import datetime, timezone
from typing import Optional, List, Dict

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bson import ObjectId

from database import db, create_document, get_documents

app = FastAPI(title="Solo Leveling Productivity API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utilities
LEVEL_STEP = 100  # EXP per level
RANKS = ["E", "D", "C", "B", "A", "S", "Shadow Monarch"]


def str_id(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    return obj


def serialize(doc: dict) -> dict:
    if not doc:
        return doc
    d = {**doc}
    if d.get("_id"):
        d["id"] = str_id(d.pop("_id"))
    return d


def compute_rank(level: int) -> str:
    if level >= 30:
        return "Shadow Monarch"
    elif level >= 25:
        return "S"
    elif level >= 20:
        return "A"
    elif level >= 15:
        return "B"
    elif level >= 10:
        return "C"
    elif level >= 5:
        return "D"
    return "E"


# Models
class HunterCreate(BaseModel):
    display_name: str
    email: Optional[str] = None


class QuestCreate(BaseModel):
    hunter_id: str
    title: str
    description: Optional[str] = None
    type: str = Field(default="daily")  # daily | weekly | main | dungeon
    exp_reward: int = Field(default=20, ge=0)
    stat_reward: Optional[Dict[str, int]] = Field(default_factory=dict)
    due_date: Optional[datetime] = None


# Routes
@app.get("/")
def read_root():
    return {"message": "Solo Leveling API running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = getattr(db, 'name', None) or "Unknown"
            try:
                cols = db.list_collection_names()
                response["collections"] = cols[:10]
                response["database"] = "✅ Connected & Working"
                response["connection_status"] = "Connected"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


@app.post("/api/hunter")
def create_or_get_hunter(payload: HunterCreate):
    # Try to find by email if provided, else by display name
    query = {"email": payload.email} if payload.email else {"display_name": payload.display_name}
    existing = db["hunter"].find_one(query)
    if existing:
        return serialize(existing)

    hunter_doc = {
        "display_name": payload.display_name,
        "email": payload.email,
        "rank": "E",
        "level": 1,
        "exp": 0,
        "total_exp": 0,
        "energy": 100,
        "title": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    res_id = db["hunter"].insert_one(hunter_doc).inserted_id

    # default stats
    stats_doc = {
        "hunter_id": str(res_id),
        "STR": 1,
        "INT": 1,
        "DEX": 1,
        "STA": 1,
        "LUK": 1,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    db["stats"].insert_one(stats_doc)

    # welcome log
    db["log"].insert_one({
        "hunter_id": str(res_id),
        "message": "System: You have awakened as a Hunter.",
        "level": "success",
        "created_at": datetime.now(timezone.utc)
    })

    hunter_doc["_id"] = res_id
    return serialize(hunter_doc)


@app.get("/api/hunter/{hunter_id}")
def get_hunter(hunter_id: str):
    doc = db["hunter"].find_one({"_id": ObjectId(hunter_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Hunter not found")
    return serialize(doc)


@app.get("/api/stats")
def get_stats(hunter_id: str = Query(...)):
    doc = db["stats"].find_one({"hunter_id": hunter_id})
    if not doc:
        # Initialize if missing
        doc = {
            "hunter_id": hunter_id,
            "STR": 1, "INT": 1, "DEX": 1, "STA": 1, "LUK": 1,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        db["stats"].insert_one(doc)
    return serialize(doc)


@app.post("/api/quests")
def create_quest(payload: QuestCreate):
    # Basic quota: reduce energy when creating a dungeon quest, else no change
    quest = payload.model_dump()
    quest.update({
        "status": "pending",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    })
    res = db["quest"].insert_one(quest)
    db["log"].insert_one({
        "hunter_id": payload.hunter_id,
        "message": f"System: Registered new quest — {payload.title}",
        "level": "info",
        "created_at": datetime.now(timezone.utc)
    })
    quest["_id"] = res.inserted_id
    return serialize(quest)


@app.get("/api/quests")
def list_quests(hunter_id: str, type: Optional[str] = None):
    flt = {"hunter_id": hunter_id}
    if type:
        flt["type"] = type
    docs = db["quest"].find(flt).sort("created_at", -1)
    return [serialize(d) for d in docs]


@app.post("/api/quests/{quest_id}/complete")
def complete_quest(quest_id: str):
    q = db["quest"].find_one({"_id": ObjectId(quest_id)})
    if not q:
        raise HTTPException(status_code=404, detail="Quest not found")
    if q.get("status") in ("completed", "claimed"):
        return {"status": q.get("status")}
    db["quest"].update_one({"_id": q["_id"]}, {"$set": {"status": "completed", "updated_at": datetime.now(timezone.utc)}})
    db["log"].insert_one({
        "hunter_id": q["hunter_id"],
        "message": f"Quest completed: {q.get('title')}",
        "level": "success",
        "created_at": datetime.now(timezone.utc)
    })
    return {"status": "completed"}


@app.post("/api/quests/{quest_id}/claim")
def claim_quest(quest_id: str):
    q = db["quest"].find_one({"_id": ObjectId(quest_id)})
    if not q:
        raise HTTPException(status_code=404, detail="Quest not found")
    if q.get("status") == "claimed":
        return {"status": "claimed"}

    # Award EXP and stats
    hunter = db["hunter"].find_one({"_id": ObjectId(q["hunter_id"])})
    if not hunter:
        raise HTTPException(status_code=404, detail="Hunter not found")

    new_total = int(hunter.get("total_exp", 0)) + int(q.get("exp_reward", 0))
    new_exp = int(hunter.get("exp", 0)) + int(q.get("exp_reward", 0))
    level = int(hunter.get("level", 1))

    leveled_up = False
    while new_exp >= LEVEL_STEP:
        new_exp -= LEVEL_STEP
        level += 1
        leveled_up = True

    new_rank = compute_rank(level)

    db["hunter"].update_one({"_id": hunter["_id"]}, {"$set": {
        "exp": new_exp,
        "total_exp": new_total,
        "level": level,
        "rank": new_rank,
        "updated_at": datetime.now(timezone.utc)
    }})

    # Apply stat rewards
    stat_reward = q.get("stat_reward") or {}
    if stat_reward:
        stats = db["stats"].find_one({"hunter_id": str(hunter["_id"])}) or {"hunter_id": str(hunter["_id"]) }
        for k, v in stat_reward.items():
            stats[k] = int(stats.get(k, 0)) + int(v)
        stats["updated_at"] = datetime.now(timezone.utc)
        db["stats"].update_one({"hunter_id": str(hunter["_id"])}, {"$set": stats}, upsert=True)

    # Mark quest claimed
    db["quest"].update_one({"_id": q["_id"]}, {"$set": {"status": "claimed", "updated_at": datetime.now(timezone.utc)}})

    # Logs
    if leveled_up:
        db["log"].insert_one({
            "hunter_id": str(hunter["_id"]),
            "message": f"Level Up! You are now Level {level} — Rank {new_rank}.",
            "level": "success",
            "created_at": datetime.now(timezone.utc)
        })
    db["log"].insert_one({
        "hunter_id": str(hunter["_id"]),
        "message": f"Rewards claimed: +{q.get('exp_reward', 0)} EXP" + (f", +{stat_reward} stats" if stat_reward else ""),
        "level": "info",
        "created_at": datetime.now(timezone.utc)
    })

    return {"status": "claimed", "level": level, "rank": new_rank, "exp": new_exp, "total_exp": new_total}


@app.get("/api/logs")
def get_logs(hunter_id: str, limit: int = 20):
    cur = db["log"].find({"hunter_id": hunter_id}).sort("created_at", -1).limit(int(limit))
    return [serialize(d) for d in cur]


# Simple seed endpoint to add sample daily quests
@app.post("/api/seed/dailies")
def seed_dailies(hunter_id: str):
    samples = [
        {"title": "Study 1 hour", "type": "daily", "exp_reward": 25, "stat_reward": {"INT": 1}},
        {"title": "Workout 30 mins", "type": "daily", "exp_reward": 30, "stat_reward": {"STR": 1, "STA": 1}},
        {"title": "Read 20 pages", "type": "daily", "exp_reward": 20, "stat_reward": {"INT": 1}},
    ]
    created = []
    for s in samples:
        payload = {
            "hunter_id": hunter_id,
            **s,
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        res = db["quest"].insert_one(payload)
        payload["_id"] = res.inserted_id
        created.append(serialize(payload))
    db["log"].insert_one({
        "hunter_id": hunter_id,
        "message": "System: Daily quests generated.",
        "level": "info",
        "created_at": datetime.now(timezone.utc)
    })
    return created


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
