from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import APIRouter, Depends, HTTPException
from datetime import date, timedelta
from typing import List

from app.database.db import Water, get_db
from app.schemas.water_counter import (
    WaterEntryCreate,
    WaterEntryUpdate,
    WaterEntryResponse,
    WaterAddAmount,
    WaterStats,
)
from app.utils.fp import (
    pipe,
    curry,
    apply_when_some,
    merge,
    sum_by,
    group_by,
    filter_by,
    validator,
    all_validators,
)

app = APIRouter()


# ── Validators (Closures) ─────────────────────────────────────

positive_int = validator(lambda x: isinstance(x, int) and x > 0, "Wert muss positiv sein")
valid_goal = validator(lambda x: isinstance(x, int) and x >= 100, "Ziel muss >= 100ml sein")


# ── Pure Functions ─────────────────────────────────────────────

def calculate_percentage(menge_ml: int, ziel_ml: int) -> float:
    """Pure: Prozentsatz berechnen."""
    return 0.0 if ziel_ml == 0 else round((menge_ml / ziel_ml) * 100, 1)


def is_goal_reached(menge_ml: int, ziel_ml: int) -> bool:
    """Pure: Ziel erreicht?"""
    return menge_ml >= ziel_ml


@curry
def create_water_response(entry: Water, ziel_ml: int = None) -> WaterEntryResponse:
    """Curried pure function: Water-DB-Entry zu Response transformieren."""
    target = ziel_ml if ziel_ml is not None else entry.ziel_ml
    return WaterEntryResponse(
        id=entry.id,
        datum=entry.datum,
        menge_ml=entry.menge_ml,
        ziel_ml=target,
        prozent=calculate_percentage(entry.menge_ml, target),
    )


def create_water_stats(entry: Water) -> WaterStats:
    """Pure: Water-DB-Entry zu Stats transformieren."""
    return WaterStats(
        datum=entry.datum,
        menge_ml=entry.menge_ml,
        ziel_ml=entry.ziel_ml,
        prozent=calculate_percentage(entry.menge_ml, entry.ziel_ml),
        erreicht=is_goal_reached(entry.menge_ml, entry.ziel_ml),
    )


def add_water_pure(current_ml: int, amount: int) -> int:
    """Pure: Wasser hinzufugen ohne Mutation."""
    return current_ml + positive_int(amount)


def update_entry_fields_pure(entry_data: dict, update: WaterEntryUpdate) -> dict:
    """Pure: Neue Felder berechnen ohne Mutation der Eingabe."""
    updates = {
        k: v for k, v in [
            ("menge_ml", update.menge_ml),
            ("ziel_ml", update.ziel_ml),
        ] if v is not None
    }
    return merge(entry_data, updates)


# ── Database Service Functions ─────────────────────────────────

def get_water_by_date(db: Session, target_date: date) -> Water | None:
    return db.query(Water).filter(Water.datum == target_date).first()


def get_water_by_id(db: Session, entry_id: int) -> Water | None:
    return db.query(Water).filter(Water.id == entry_id).first()


def create_water_entry(db: Session, data: WaterEntryCreate) -> Water:
    entry = Water(datum=data.datum, menge_ml=data.menge_ml, ziel_ml=data.ziel_ml)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_or_create_today_entry(db: Session) -> Water:
    today = date.today()
    entry = get_water_by_date(db, today)
    if not entry:
        entry = Water(datum=today, menge_ml=0, ziel_ml=2000)
        db.add(entry)
        db.commit()
        db.refresh(entry)
    return entry


def delete_water_by_id(db: Session, entry_id: int) -> Water | None:
    entry = get_water_by_id(db, entry_id)
    if entry:
        db.delete(entry)
        db.commit()
    return entry


# ── Route Handlers ─────────────────────────────────────────────

@app.post("/", response_model=WaterEntryResponse, status_code=201)
def create_water_entry_route(entry: WaterEntryCreate, db: Session = Depends(get_db)):
    existing = get_water_by_date(db, entry.datum)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Eintrag fur {entry.datum} existiert bereits. Nutze PUT zum Aktualisieren.",
        )

    db_entry = create_water_entry(db, entry)
    return create_water_response(db_entry)


@app.get("/today", response_model=WaterEntryResponse)
def get_today_water(db: Session = Depends(get_db)):
    entry = get_or_create_today_entry(db)
    return create_water_response(entry)


@app.post("/today/add", response_model=WaterEntryResponse)
def add_water_today(amount: WaterAddAmount, db: Session = Depends(get_db)):
    entry = get_or_create_today_entry(db)
    entry.menge_ml = add_water_pure(entry.menge_ml, amount.menge_ml)
    db.commit()
    db.refresh(entry)
    return create_water_response(entry)


@app.get("/", response_model=List[WaterEntryResponse])
def get_all_water_entries(skip: int = 0, limit: int = 30, db: Session = Depends(get_db)):
    entries = (
        db.query(Water)
        .order_by(Water.datum.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return list(map(create_water_response, entries))


@app.get("/date/{datum}", response_model=WaterEntryResponse)
def get_water_by_date_route(datum: date, db: Session = Depends(get_db)):
    entry = get_water_by_date(db, datum)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Kein Eintrag fur {datum} gefunden")
    return create_water_response(entry)


@app.put("/{entry_id}", response_model=WaterEntryResponse)
def update_water_entry(entry_id: int, update_data: WaterEntryUpdate, db: Session = Depends(get_db)):
    entry = get_water_by_id(db, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")

    updated = update_entry_fields_pure(
        {"menge_ml": entry.menge_ml, "ziel_ml": entry.ziel_ml},
        update_data,
    )
    if "menge_ml" in updated:
        entry.menge_ml = updated["menge_ml"]
    if "ziel_ml" in updated:
        entry.ziel_ml = valid_goal(updated["ziel_ml"])

    db.commit()
    db.refresh(entry)
    return create_water_response(entry)


@app.delete("/{entry_id}")
def delete_water_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = delete_water_by_id(db, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    return {"message": f"Eintrag vom {entry.datum} geloscht"}


@app.get("/stats/week", response_model=List[WaterStats])
def get_week_stats(db: Session = Depends(get_db)):
    today = date.today()
    week_ago = today - timedelta(days=7)

    entries = (
        db.query(Water)
        .filter(Water.datum >= week_ago, Water.datum <= today)
        .order_by(Water.datum.desc())
        .all()
    )
    return list(map(create_water_stats, entries))


@app.get("/stats/summary")
def get_summary_stats(db: Session = Depends(get_db)):
    total_entries = db.query(func.count(Water.id)).scalar() or 0
    avg_consumption = db.query(func.avg(Water.menge_ml)).scalar() or 0

    days_goal_reached = (
        db.query(func.count(Water.id)).filter(Water.menge_ml >= Water.ziel_ml).scalar() or 0
    )

    week_ago = date.today() - timedelta(days=7)
    week_avg = (
        db.query(func.avg(Water.menge_ml)).filter(Water.datum >= week_ago).scalar() or 0
    )

    success_rate = round((days_goal_reached / total_entries * 100), 1) if total_entries > 0 else 0

    return {
        "total_entries": total_entries,
        "avg_consumption_ml": round(avg_consumption, 1),
        "days_goal_reached": days_goal_reached,
        "success_rate": success_rate,
        "week_avg_ml": round(week_avg, 1),
    }
