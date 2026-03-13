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
    WaterStats
)

app = APIRouter()

def calculate_percentage(menge_ml: int, ziel_ml: int) -> float:
    if ziel_ml == 0:
        return 0.0
    return round((menge_ml / ziel_ml) * 100, 1)

@app.post("/", response_model=WaterEntryResponse, status_code=201)
def create_water_entry(entry: WaterEntryCreate, db: Session = Depends(get_db)):
    existing = db.query(Water).filter(Water.datum == entry.datum).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Eintrag für {entry.datum} existiert bereits. Nutze PUT zum Aktualisieren."
        )
    
    db_entry = Water(
        datum=entry.datum,
        menge_ml=entry.menge_ml,
        ziel_ml=entry.ziel_ml
    )
    
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    
    return WaterEntryResponse(
        id=db_entry.id,
        datum=db_entry.datum,
        menge_ml=db_entry.menge_ml,
        ziel_ml=db_entry.ziel_ml,
        prozent=calculate_percentage(db_entry.menge_ml, db_entry.ziel_ml)
    )

@app.get("/today", response_model=WaterEntryResponse)
def get_today_water(db: Session = Depends(get_db)):
    today = date.today()
    entry = db.query(Water).filter(Water.datum == today).first()
    
    if not entry:
        entry = Water(datum=today, menge_ml=0, ziel_ml=2000)
        db.add(entry)
        db.commit()
        db.refresh(entry)
    
    return WaterEntryResponse(
        id=entry.id,
        datum=entry.datum,
        menge_ml=entry.menge_ml,
        ziel_ml=entry.ziel_ml,
        prozent=calculate_percentage(entry.menge_ml, entry.ziel_ml)
    )

@app.post("/today/add", response_model=WaterEntryResponse)
def add_water_today(amount: WaterAddAmount, db: Session = Depends(get_db)):
    today = date.today()
    entry = db.query(Water).filter(Water.datum == today).first()
    
    if not entry:
        entry = Water(datum=today, menge_ml=0, ziel_ml=2000)
        db.add(entry)
    
    entry.menge_ml += amount.menge_ml
    db.commit()
    db.refresh(entry)
    
    return WaterEntryResponse(
        id=entry.id,
        datum=entry.datum,
        menge_ml=entry.menge_ml,
        ziel_ml=entry.ziel_ml,
        prozent=calculate_percentage(entry.menge_ml, entry.ziel_ml)
    )

@app.get("/", response_model=List[WaterEntryResponse])
def get_all_water_entries(
    skip: int = 0,
    limit: int = 30,
    db: Session = Depends(get_db)
):
    entries = db.query(Water).order_by(Water.datum.desc()).offset(skip).limit(limit).all()
    
    return [
        WaterEntryResponse(
            id=entry.id,
            datum=entry.datum,
            menge_ml=entry.menge_ml,
            ziel_ml=entry.ziel_ml,
            prozent=calculate_percentage(entry.menge_ml, entry.ziel_ml)
        )
        for entry in entries
    ]

@app.get("/date/{datum}", response_model=WaterEntryResponse)
def get_water_by_date(datum: date, db: Session = Depends(get_db)):
    entry = db.query(Water).filter(Water.datum == datum).first()
    
    if not entry:
        raise HTTPException(
            status_code=404,
            detail=f"Kein Eintrag für {datum} gefunden"
        )
    
    return WaterEntryResponse(
        id=entry.id,
        datum=entry.datum,
        menge_ml=entry.menge_ml,
        ziel_ml=entry.ziel_ml,
        prozent=calculate_percentage(entry.menge_ml, entry.ziel_ml)
    )

@app.put("/{entry_id}", response_model=WaterEntryResponse)
def update_water_entry(
    entry_id: int,
    update_data: WaterEntryUpdate,
    db: Session = Depends(get_db)
):
    entry = db.query(Water).filter(Water.id == entry_id).first()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    
    if update_data.menge_ml is not None:
        entry.menge_ml = update_data.menge_ml
    if update_data.ziel_ml is not None:
        entry.ziel_ml = update_data.ziel_ml
    
    db.commit()
    db.refresh(entry)
    
    return WaterEntryResponse(
        id=entry.id,
        datum=entry.datum,
        menge_ml=entry.menge_ml,
        ziel_ml=entry.ziel_ml,
        prozent=calculate_percentage(entry.menge_ml, entry.ziel_ml)
    )

@app.delete("/{entry_id}")
def delete_water_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = db.query(Water).filter(Water.id == entry_id).first()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    
    db.delete(entry)
    db.commit()
    
    return {"message": f"Eintrag vom {entry.datum} gelöscht"}

@app.get("/stats/week", response_model=List[WaterStats])
def get_week_stats(db: Session = Depends(get_db)):
    today = date.today()
    week_ago = today - timedelta(days=7)
    
    entries = db.query(Water).filter(
        Water.datum >= week_ago,
        Water.datum <= today
    ).order_by(Water.datum.desc()).all()
    
    return [
        WaterStats(
            datum=entry.datum,
            menge_ml=entry.menge_ml,
            ziel_ml=entry.ziel_ml,
            prozent=calculate_percentage(entry.menge_ml, entry.ziel_ml),
            erreicht=entry.menge_ml >= entry.ziel_ml
        )
        for entry in entries
    ]

@app.get("/stats/summary")
def get_summary_stats(db: Session = Depends(get_db)):
    total_entries = db.query(func.count(Water.id)).scalar()
    avg_consumption = db.query(func.avg(Water.menge_ml)).scalar() or 0
    
    days_goal_reached = db.query(func.count(Water.id)).filter(
        Water.menge_ml >= Water.ziel_ml
    ).scalar()
    
    week_ago = date.today() - timedelta(days=7)
    week_avg = db.query(func.avg(Water.menge_ml)).filter(
        Water.datum >= week_ago
    ).scalar() or 0
    
    return {
        "total_entries": total_entries,
        "avg_consumption_ml": round(avg_consumption, 1),
        "days_goal_reached": days_goal_reached,
        "success_rate": round((days_goal_reached / total_entries * 100), 1) if total_entries > 0 else 0,
        "week_avg_ml": round(week_avg, 1)
    }