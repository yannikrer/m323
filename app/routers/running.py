from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import date, timedelta
from typing import List, Optional

from app.database.db import RunningSession, RunningGoal, get_db
from app.schemas.running import (
    RunningSessionCreate,
    RunningSessionUpdate,
    RunningSessionResponse,
    RunningStats,
    WeeklyRunning,
    PersonalBests,
    RunningGoalCreate,
    RunningGoalResponse
)

app = APIRouter()

def calculate_speed(distance_km: float, duration_minutes: float) -> float:
    if duration_minutes == 0:
        return 0
    return round((distance_km / duration_minutes) * 60, 2)

def estimate_calories(distance_km: float, weight_kg: float = 70) -> float:
    return round(distance_km * (weight_kg / 70) * 60, 1)

@app.post("/", response_model=RunningSessionResponse, status_code=201)
def create_running_session(session: RunningSessionCreate, db: Session = Depends(get_db)):
    avg_speed = calculate_speed(session.distance_km, session.duration_minutes)
    calories = estimate_calories(session.distance_km)
    
    db_session = RunningSession(
        date=session.date,
        time=session.time,
        distance_km=session.distance_km,
        duration_minutes=session.duration_minutes,
        avg_speed_kmh=avg_speed,
        calories_burned=calories,
        heart_rate_avg=session.heart_rate_avg,
        route=session.route,
        weather=session.weather,
        feeling=session.feeling,
        note=session.note
    )
    
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    
    return db_session

@app.get("/", response_model=List[RunningSessionResponse])
def get_all_sessions(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    sessions = db.query(RunningSession).order_by(RunningSession.date.desc()).offset(skip).limit(limit).all()
    return sessions

@app.get("/today", response_model=List[RunningSessionResponse])
def get_today_sessions(db: Session = Depends(get_db)):
    today = date.today()
    sessions = db.query(RunningSession).filter(RunningSession.date == today).all()
    return sessions

@app.get("/date/{target_date}", response_model=List[RunningSessionResponse])
def get_sessions_by_date(target_date: date, db: Session = Depends(get_db)):
    sessions = db.query(RunningSession).filter(RunningSession.date == target_date).all()
    return sessions

@app.get("/week", response_model=List[WeeklyRunning])
def get_week_sessions(start_date: Optional[date] = None, db: Session = Depends(get_db)):
    if start_date is None:
        end_date = date.today()
        start_date = end_date - timedelta(days=6)
    else:
        end_date = start_date + timedelta(days=6)
    
    sessions = db.query(RunningSession).filter(
        and_(RunningSession.date >= start_date, RunningSession.date <= end_date)
    ).order_by(RunningSession.date.desc()).all()
    
    return [
        WeeklyRunning(
            date=s.date,
            distance_km=s.distance_km,
            duration_minutes=s.duration_minutes,
            avg_speed_kmh=s.avg_speed_kmh,
            calories_burned=s.calories_burned
        )
        for s in sessions
    ]

@app.get("/stats/week", response_model=RunningStats)
def get_week_stats(db: Session = Depends(get_db)):
    week_ago = date.today() - timedelta(days=7)
    
    result = db.query(
        func.sum(RunningSession.distance_km).label('total_distance'),
        func.sum(RunningSession.duration_minutes).label('total_duration'),
        func.count(RunningSession.id).label('total_sessions'),
        func.avg(RunningSession.avg_speed_kmh).label('avg_speed'),
        func.sum(RunningSession.calories_burned).label('total_calories')
    ).filter(RunningSession.date >= week_ago).first()
    
    total_distance = result.total_distance or 0
    total_sessions = result.total_sessions or 0
    
    best_5k = db.query(RunningSession).filter(
        RunningSession.distance_km >= 4.9,
        RunningSession.distance_km <= 5.1,
        RunningSession.date >= week_ago
    ).order_by(RunningSession.duration_minutes.asc()).first()
    
    best_10k = db.query(RunningSession).filter(
        RunningSession.distance_km >= 9.9,
        RunningSession.distance_km <= 10.1,
        RunningSession.date >= week_ago
    ).order_by(RunningSession.duration_minutes.asc()).first()
    
    return RunningStats(
        total_distance_km=round(total_distance, 2),
        total_duration_minutes=round(result.total_duration or 0, 1),
        total_sessions=total_sessions,
        avg_distance_per_run=round(total_distance / total_sessions, 2) if total_sessions > 0 else 0,
        avg_speed_kmh=round(result.avg_speed or 0, 2),
        total_calories_burned=round(result.total_calories or 0, 1),
        best_5k_time=best_5k.duration_minutes if best_5k else None,
        best_10k_time=best_10k.duration_minutes if best_10k else None
    )

@app.get("/stats/all-time", response_model=RunningStats)
def get_all_time_stats(db: Session = Depends(get_db)):
    result = db.query(
        func.sum(RunningSession.distance_km).label('total_distance'),
        func.sum(RunningSession.duration_minutes).label('total_duration'),
        func.count(RunningSession.id).label('total_sessions'),
        func.avg(RunningSession.avg_speed_kmh).label('avg_speed'),
        func.sum(RunningSession.calories_burned).label('total_calories')
    ).first()
    
    total_distance = result.total_distance or 0
    total_sessions = result.total_sessions or 0
    
    best_5k = db.query(RunningSession).filter(
        RunningSession.distance_km >= 4.9,
        RunningSession.distance_km <= 5.1
    ).order_by(RunningSession.duration_minutes.asc()).first()
    
    best_10k = db.query(RunningSession).filter(
        RunningSession.distance_km >= 9.9,
        RunningSession.distance_km <= 10.1
    ).order_by(RunningSession.duration_minutes.asc()).first()
    
    return RunningStats(
        total_distance_km=round(total_distance, 2),
        total_duration_minutes=round(result.total_duration or 0, 1),
        total_sessions=total_sessions,
        avg_distance_per_run=round(total_distance / total_sessions, 2) if total_sessions > 0 else 0,
        avg_speed_kmh=round(result.avg_speed or 0, 2),
        total_calories_burned=round(result.total_calories or 0, 1),
        best_5k_time=best_5k.duration_minutes if best_5k else None,
        best_10k_time=best_10k.duration_minutes if best_10k else None
    )

@app.get("/stats/personal-bests", response_model=PersonalBests)
def get_personal_bests(db: Session = Depends(get_db)):
    best_5k = db.query(RunningSession).filter(
        RunningSession.distance_km >= 4.9,
        RunningSession.distance_km <= 5.1
    ).order_by(RunningSession.duration_minutes.asc()).first()
    
    best_10k = db.query(RunningSession).filter(
        RunningSession.distance_km >= 9.9,
        RunningSession.distance_km <= 10.1
    ).order_by(RunningSession.duration_minutes.asc()).first()
    
    longest_run = db.query(RunningSession).order_by(RunningSession.distance_km.desc()).first()
    
    fastest_run = db.query(RunningSession).order_by(RunningSession.avg_speed_kmh.desc()).first()
    
    return PersonalBests(
        best_5k_minutes=best_5k.duration_minutes if best_5k else None,
        best_10k_minutes=best_10k.duration_minutes if best_10k else None,
        longest_distance_km=longest_run.distance_km if longest_run else None,
        fastest_avg_speed=fastest_run.avg_speed_kmh if fastest_run else None
    )

@app.get("/search", response_model=List[RunningSessionResponse])
def search_sessions(
    route: Optional[str] = None,
    min_distance: Optional[float] = None,
    max_distance: Optional[float] = None,
    min_speed: Optional[float] = None,
    db: Session = Depends(get_db)
):
    query = db.query(RunningSession)
    
    if route:
        query = query.filter(RunningSession.route.ilike(f"%{route}%"))
    if min_distance:
        query = query.filter(RunningSession.distance_km >= min_distance)
    if max_distance:
        query = query.filter(RunningSession.distance_km <= max_distance)
    if min_speed:
        query = query.filter(RunningSession.avg_speed_kmh >= min_speed)
    
    sessions = query.order_by(RunningSession.date.desc()).limit(50).all()
    return sessions

@app.put("/{session_id}", response_model=RunningSessionResponse)
def update_session(session_id: int, update_data: RunningSessionUpdate, db: Session = Depends(get_db)):
    session = db.query(RunningSession).filter(RunningSession.id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session nicht gefunden")
    
    if update_data.distance_km is not None:
        session.distance_km = update_data.distance_km
    if update_data.duration_minutes is not None:
        session.duration_minutes = update_data.duration_minutes
    if update_data.heart_rate_avg is not None:
        session.heart_rate_avg = update_data.heart_rate_avg
    if update_data.route is not None:
        session.route = update_data.route
    if update_data.weather is not None:
        session.weather = update_data.weather
    if update_data.feeling is not None:
        session.feeling = update_data.feeling
    if update_data.note is not None:
        session.note = update_data.note
    
    if update_data.distance_km or update_data.duration_minutes:
        session.avg_speed_kmh = calculate_speed(session.distance_km, session.duration_minutes)
        session.calories_burned = estimate_calories(session.distance_km)
    
    db.commit()
    db.refresh(session)
    
    return session

@app.delete("/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(RunningSession).filter(RunningSession.id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session nicht gefunden")
    
    db.delete(session)
    db.commit()
    
    return {"message": f"Session vom {session.date} gelöscht"}

@app.post("/goals", response_model=RunningGoalResponse, status_code=201)
def create_goal(goal: RunningGoalCreate, db: Session = Depends(get_db)):
    db_goal = RunningGoal(
        goal_type=goal.goal_type,
        target_distance_km=goal.target_distance_km,
        target_time_minutes=goal.target_time_minutes,
        start_date=goal.start_date,
        end_date=goal.end_date,
        achieved=False
    )
    
    db.add(db_goal)
    db.commit()
    db.refresh(db_goal)
    
    return db_goal

@app.get("/goals", response_model=List[RunningGoalResponse])
def get_all_goals(db: Session = Depends(get_db)):
    goals = db.query(RunningGoal).order_by(RunningGoal.start_date.desc()).all()
    return goals

@app.get("/goals/active", response_model=List[RunningGoalResponse])
def get_active_goals(db: Session = Depends(get_db)):
    today = date.today()
    goals = db.query(RunningGoal).filter(
        RunningGoal.achieved == False,
        RunningGoal.start_date <= today
    ).all()
    return goals

@app.put("/goals/{goal_id}/complete")
def complete_goal(goal_id: int, db: Session = Depends(get_db)):
    goal = db.query(RunningGoal).filter(RunningGoal.id == goal_id).first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Ziel nicht gefunden")
    
    goal.achieved = True
    db.commit()
    
    return {"message": "Ziel erreicht!"}

@app.delete("/goals/{goal_id}")
def delete_goal(goal_id: int, db: Session = Depends(get_db)):
    goal = db.query(RunningGoal).filter(RunningGoal.id == goal_id).first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Ziel nicht gefunden")
    
    db.delete(goal)
    db.commit()
    
    return {"message": "Ziel gelöscht"}