import os
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import Room, Countdown, Motd, Ping, Todo

app = FastAPI(title="Long Distance Companion API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utility to serialize Mongo documents
from bson import ObjectId

def serialize_doc(doc):
    if not doc:
        return doc
    d = dict(doc)
    _id = d.get("_id")
    if isinstance(_id, ObjectId):
        d["id"] = str(_id)
        del d["_id"]
    # Convert datetimes to iso
    for k, v in list(d.items()):
        if isinstance(v, datetime):
            d[k] = v.astimezone(timezone.utc).isoformat()
    return d


@app.get("/")
def read_root():
    return {"message": "Long Distance Companion Backend", "ok": True}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "❌ Not Set",
        "database_name": "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = getattr(db, 'name', 'unknown') or "unknown"
            response["connection_status"] = "Connected"
            try:
                response["collections"] = db.list_collection_names()
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# Rooms
class CreateRoomRequest(BaseModel):
    code: str
    title: Optional[str] = None

@app.post("/rooms")
def create_room(req: CreateRoomRequest):
    existing = db["room"].find_one({"code": req.code}) if db else None
    if existing:
        return serialize_doc(existing)
    room = Room(code=req.code, title=req.title)
    _id = create_document("room", room)
    created = db["room"].find_one({"_id": ObjectId(_id)})
    return serialize_doc(created)

@app.get("/rooms/{code}")
def get_room(code: str):
    room = db["room"].find_one({"code": code})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return serialize_doc(room)


# Countdown
class SetCountdownRequest(BaseModel):
    target_iso: str

@app.put("/rooms/{code}/countdown")
def set_countdown(code: str, payload: SetCountdownRequest):
    # Upsert countdown for room
    now = datetime.now(timezone.utc)
    data = {
        "room_code": code,
        "target_iso": payload.target_iso,
        "updated_at": now,
        "created_at": now,
    }
    db["countdown"].update_one({"room_code": code}, {"$set": data}, upsert=True)
    doc = db["countdown"].find_one({"room_code": code})
    return serialize_doc(doc)

@app.get("/rooms/{code}/countdown")
def get_countdown(code: str):
    doc = db["countdown"].find_one({"room_code": code})
    if not doc:
        return {"room_code": code, "target_iso": None}
    return serialize_doc(doc)


# Message of the Day (MOTD)
class CreateMotdRequest(BaseModel):
    text: str
    author: Optional[str] = None

@app.post("/rooms/{code}/motd")
def create_motd(code: str, payload: CreateMotdRequest):
    motd = Motd(room_code=code, text=payload.text, author=payload.author, at=datetime.now(timezone.utc))
    _id = create_document("motd", motd)
    doc = db["motd"].find_one({"_id": ObjectId(_id)})
    return serialize_doc(doc)

@app.get("/rooms/{code}/motd")
def list_motd(code: str, limit: int = 20):
    docs = db["motd"].find({"room_code": code}).sort("at", -1).limit(int(limit))
    return [serialize_doc(d) for d in docs]


# Pings
class CreatePingRequest(BaseModel):
    note: Optional[str] = None
    author: Optional[str] = None

@app.post("/rooms/{code}/pings")
def create_ping(code: str, payload: CreatePingRequest):
    ping = Ping(room_code=code, note=payload.note, author=payload.author, at=datetime.now(timezone.utc))
    _id = create_document("ping", ping)
    doc = db["ping"].find_one({"_id": ObjectId(_id)})
    return serialize_doc(doc)

@app.get("/rooms/{code}/pings")
def list_pings(code: str, limit: int = 20):
    docs = db["ping"].find({"room_code": code}).sort("at", -1).limit(int(limit))
    return [serialize_doc(d) for d in docs]


# Todos
class CreateTodoRequest(BaseModel):
    text: str

class UpdateTodoRequest(BaseModel):
    done: Optional[bool] = None

@app.get("/rooms/{code}/todos")
def list_todos(code: str):
    docs = db["todo"].find({"room_code": code}).sort("created_at", -1)
    return [serialize_doc(d) for d in docs]

@app.post("/rooms/{code}/todos")
def add_todo(code: str, payload: CreateTodoRequest):
    todo = Todo(room_code=code, text=payload.text, done=False, created_at=datetime.now(timezone.utc))
    _id = create_document("todo", todo)
    doc = db["todo"].find_one({"_id": ObjectId(_id)})
    return serialize_doc(doc)

@app.patch("/rooms/{code}/todos/{todo_id}")
def update_todo(code: str, todo_id: str, payload: UpdateTodoRequest):
    q = {"_id": ObjectId(todo_id), "room_code": code}
    upd = {"$set": {}}
    if payload.done is not None:
        upd["$set"]["done"] = payload.done
        upd["$set"]["updated_at"] = datetime.now(timezone.utc)
    res = db["todo"].update_one(q, upd)
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Todo not found")
    doc = db["todo"].find_one(q)
    return serialize_doc(doc)

@app.delete("/rooms/{code}/todos/{todo_id}")
def delete_todo(code: str, todo_id: str):
    q = {"_id": ObjectId(todo_id), "room_code": code}
    res = db["todo"].delete_one(q)
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Todo not found")
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
