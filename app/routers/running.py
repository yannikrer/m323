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
    RunningGoalResponse,
)
from app.utils.fp import merge, validator

app = APIRouter()


# ── Validators (Closures) ─────────────────────────────────────

positive_distance = validator(lambda d: isinstance(d, (int, float)) and d > 0, "Distanz muss positiv sein")
positive_duration = validator(lambda d: isinstance(d, (int, float)) and d > 0, "Dauer muss positiv sein")


# ── Pure Functions ─────────────────────────────────────────────

def calculate_speed(distance_km: float, duration_minutes: float) -> float:
    """Pure: Geschwindigkeit berechnen."""
    return 0 if duration_minutes == 0 else round((distance_km / duration_minutes) * 60, 2)


def estimate_calories(distance_km: float, weight_kg: float = 70) -> float:
    """Pure: Kalorienverbrauch schatzen."""
    return round(distance_km * (weight_kg / 70) * 60, 1)


def is_distance_in_range(distance: float, target: float, tolerance: float = 0.1) -> bool:
    """Pure: Prüfen ob Distanz im Zielbereich liegt."""
    return abs(distance - target) <= tolerance


def safe_divide(numerator: float, denominator: float) -> float:
    """Pure: Sichere Division."""
    return round(numerator / denominator, 2) if denominator > 0 else 0


def create_weekly_running(session: RunningSession) -> WeeklyRunning:
    """Pure: RunningSession zu WeeklyRunning transformieren."""
    return WeeklyRunning(
        date=session.date,
        distance_km=session.distance_km,
        duration_minutes=session.duration_minutes,
        avg_speed_kmh=session.avg_speed_kmh,
        calories_burned=session.calories_burned,
    )


# ── DB Service Functions ───────────────────────────────────────

def get_session_by_id(db: Session, session_id: int) -> RunningSession | None:
    return db.query(RunningSession).filter(RunningSession.id == session_id).first()


def get_sessions_by_date(db: Session, target_date: date) -> List[RunningSession]:
    return db.query(RunningSession).filter(RunningSession.date == target_date).all()


def get_sessions_in_range(db: Session, start: date, end: date) -> List[RunningSession]:
    return (
        db.query(RunningSession)
        .filter(and_(RunningSession.date >= start, RunningSession.date <= end))
        .order_by(RunningSession.date.desc())
        .all()
    )


def build_session(data: RunningSessionCreate) -> dict:
    """Pure: Session-Daten mit berechneten Feldern aufbauen."""
    avg_speed = calculate_speed(data.distance_km, data.duration_minutes)
    calories = estimate_calories(data.distance_km)
    return merge(
        {
            "date": data.date, "time": data.time,
            "distance_km": data.distance_km,
            "duration_minutes": data.duration_minutes,
        },
        {
            "avg_speed_kmh": avg_speed,
            "calories_burned": calories,
            "heart_rate_avg": data.heart_rate_avg,
            "route": data.route, "weather": data.weather,
            "feeling": data.feeling, "note": data.note,
        },
    )


def create_running_session(db: Session, data: RunningSessionCreate) -> RunningSession:
    session_data = build_session(data)
    session = RunningSession(**session_data)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def delete_session_by_id(db: Session, session_id: int) -> RunningSession | None:
    session = get_session_by_id(db, session_id)
    if session:
        db.delete(session)
        db.commit()
    return session


def update_session_fields(session: RunningSession, data: RunningSessionUpdate) -> None:
    """Mutates session - side effect isolated in service layer."""
    updates = {
        "distance_km": data.distance_km,
        "duration_minutes": data.duration_minutes,
        "heart_rate_avg": data.heart_rate_avg,
        "route": data.route, "weather": data.weather,
        "feeling": data.feeling, "note": data.note,
    }
    for field, value in updates.items():
        if value is not None:
            setattr(session, field, value)

    if data.distance_km or data.duration_minutes:
        session.avg_speed_kmh = calculate_speed(session.distance_km, session.duration_minutes)
        session.calories_burned = estimate_calories(session.distance_km)


# ── Goal Service Functions ─────────────────────────────────────

def get_goal_by_id(db: Session, goal_id: int) -> RunningGoal | None:
    return db.query(RunningGoal).filter(RunningGoal.id == goal_id).first()


def create_running_goal(db: Session, data: RunningGoalCreate) -> RunningGoal:
    goal = RunningGoal(
        goal_type=data.goal_type,
        target_distance_km=data.target_distance_km,
        target_time_minutes=data.target_time_minutes,
        start_date=data.start_date,
        end_date=data.end_date,
        achieved=False,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def get_active_goals(db: Session) -> List[RunningGoal]:
    today = date.today()
    return db.query(RunningGoal).filter(
        RunningGoal.achieved == False,
        RunningGoal.start_date <= today,
    ).all()


def complete_goal_by_id(db: Session, goal_id: int) -> RunningGoal | None:
    goal = get_goal_by_id(db, goal_id)
    if goal:
        goal.achieved = True
        db.commit()
    return goal


def delete_goal_by_id(db: Session, goal_id: int) -> RunningGoal | None:
    goal = get_goal_by_id(db, goal_id)
    if goal:
        db.delete(goal)
        db.commit()
    return goal


# ── Statistics Functions ────────────────────────────────────────

def get_best_time_for_distance(db: Session, target_distance: float, start_date: date = None) -> RunningSession | None:
    query = db.query(RunningSession).filter(
        RunningSession.distance_km >= target_distance - 0.1,
        RunningSession.distance_km <= target_distance + 0.1,
    )
    if start_date:
        query = query.filter(RunningSession.date >= start_date)
    return query.order_by(RunningSession.duration_minutes.asc()).first()


def calculate_stats_from_result(result, total_distance: float) -> RunningStats:
    """Pure: Stats aus DB-Resultat berechnen."""
    total_sessions = result.total_sessions or 0
    return RunningStats(
        total_distance_km=round(total_distance, 2),
        total_duration_minutes=round(result.total_duration or 0, 1),
        total_sessions=total_sessions,
        avg_distance_per_run=safe_divide(total_distance, total_sessions),
        avg_speed_kmh=round(result.avg_speed or 0, 2),
        total_calories_burned=round(result.total_calories or 0, 1),
        best_5k_time=None,
        best_10k_time=None,
    )


# ── Route Handlers ─────────────────────────────────────────────

@app.post("/", response_model=RunningSessionResponse, status_code=201)
def create_running_session_route(session: RunningSessionCreate, db: Session = Depends(get_db)):
    positive_distance(session.distance_km)
    positive_duration(session.duration_minutes)
    return create_running_session(db, session)


@app.get("/", response_model=List[RunningSessionResponse])
def get_all_sessions(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return db.query(RunningSession).order_by(
        RunningSession.date.desc()
    ).offset(skip).limit(limit).all()


@app.get("/today", response_model=List[RunningSessionResponse])
def get_today_sessions(db: Session = Depends(get_db)):
    return get_sessions_by_date(db, date.today())


@app.get("/date/{target_date}", response_model=List[RunningSessionResponse])
def get_sessions_by_date_route(target_date: date, db: Session = Depends(get_db)):
    return get_sessions_by_date(db, target_date)


@app.get("/week", response_model=List[WeeklyRunning])
def get_week_sessions(start_date: Optional[date] = None, db: Session = Depends(get_db)):
    if start_date is None:
        end_date = date.today()
        start_date = end_date - timedelta(days=6)
    else:
        end_date = start_date + timedelta(days=6)

    sessions = get_sessions_in_range(db, start_date, end_date)
    return list(map(create_weekly_running, sessions))


@app.get("/stats/week", response_model=RunningStats)
def get_week_stats(db: Session = Depends(get_db)):
    week_ago = date.today() - timedelta(days=7)

    result = db.query(
        func.sum(RunningSession.distance_km).label("total_distance"),
        func.sum(RunningSession.duration_minutes).label("total_duration"),
        func.count(RunningSession.id).label("total_sessions"),
        func.avg(RunningSession.avg_speed_kmh).label("avg_speed"),
        func.sum(RunningSession.calories_burned).label("total_calories"),
    ).filter(RunningSession.date >= week_ago).first()

    stats = calculate_stats_from_result(result, result.total_distance or 0)

    best_5k = get_best_time_for_distance(db, 5.0, week_ago)
    best_10k = get_best_time_for_distance(db, 10.0, week_ago)

    return RunningStats(
        total_distance_km=stats.total_distance_km,
        total_duration_minutes=stats.total_duration_minutes,
        total_sessions=stats.total_sessions,
        avg_distance_per_run=stats.avg_distance_per_run,
        avg_speed_kmh=stats.avg_speed_kmh,
        total_calories_burned=stats.total_calories_burned,
        best_5k_time=best_5k.duration_minutes if best_5k else None,
        best_10k_time=best_10k.duration_minutes if best_10k else None,
    )


@app.get("/stats/all-time", response_model=RunningStats)
def get_all_time_stats(db: Session = Depends(get_db)):
    result = db.query(
        func.sum(RunningSession.distance_km).label("total_distance"),
        func.sum(RunningSession.duration_minutes).label("total_duration"),
        func.count(RunningSession.id).label("total_sessions"),
        func.avg(RunningSession.avg_speed_kmh).label("avg_speed"),
        func.sum(RunningSession.calories_burned).label("total_calories"),
    ).first()

    stats = calculate_stats_from_result(result, result.total_distance or 0)

    best_5k = get_best_time_for_distance(db, 5.0)
    best_10k = get_best_time_for_distance(db, 10.0)

    return RunningStats(
        total_distance_km=stats.total_distance_km,
        total_duration_minutes=stats.total_duration_minutes,
        total_sessions=stats.total_sessions,
        avg_distance_per_run=stats.avg_distance_per_run,
        avg_speed_kmh=stats.avg_speed_kmh,
        total_calories_burned=stats.total_calories_burned,
        best_5k_time=best_5k.duration_minutes if best_5k else None,
        best_10k_time=best_10k.duration_minutes if best_10k else None,
    )


@app.get("/stats/personal-bests", response_model=PersonalBests)
def get_personal_bests(db: Session = Depends(get_db)):
    best_5k = get_best_time_for_distance(db, 5.0)
    best_10k = get_best_time_for_distance(db, 10.0)

    longest_run = db.query(RunningSession).order_by(
        RunningSession.distance_km.desc()
    ).first()

    fastest_run = db.query(RunningSession).order_by(
        RunningSession.avg_speed_kmh.desc()
    ).first()

    return PersonalBests(
        best_5k_minutes=best_5k.duration_minutes if best_5k else None,
        best_10k_minutes=best_10k.duration_minutes if best_10k else None,
        longest_distance_km=longest_run.distance_km if longest_run else None,
        fastest_avg_speed=fastest_run.avg_speed_kmh if fastest_run else None,
    )


@app.get("/search", response_model=List[RunningSessionResponse])
def search_sessions(
    route: Optional[str] = None,
    min_distance: Optional[float] = None,
    max_distance: Optional[float] = None,
    min_speed: Optional[float] = None,
    db: Session = Depends(get_db),
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

    return query.order_by(RunningSession.date.desc()).limit(50).all()


@app.put("/{session_id}", response_model=RunningSessionResponse)
def update_session(session_id: int, update_data: RunningSessionUpdate, db: Session = Depends(get_db)):
    session = get_session_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session nicht gefunden")

    update_session_fields(session, update_data)
    db.commit()
    db.refresh(session)
    return session


@app.delete("/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db)):
    session = delete_session_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session nicht gefunden")
    return {"message": f"Session vom {session.date} geloscht"}


# ── Goal Routes ────────────────────────────────────────────────

@app.post("/goals", response_model=RunningGoalResponse, status_code=201)
def create_goal(goal: RunningGoalCreate, db: Session = Depends(get_db)):
    return create_running_goal(db, goal)


@app.get("/goals", response_model=List[RunningGoalResponse])
def get_all_goals(db: Session = Depends(get_db)):
    return db.query(RunningGoal).order_by(RunningGoal.start_date.desc()).all()


@app.get("/goals/active", response_model=List[RunningGoalResponse])
def get_active_goals_route(db: Session = Depends(get_db)):
    return get_active_goals(db)


@app.put("/goals/{goal_id}/complete")
def complete_goal(goal_id: int, db: Session = Depends(get_db)):
    goal = complete_goal_by_id(db, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Ziel nicht gefunden")
    return {"message": "Ziel erreicht!"}


@app.delete("/goals/{goal_id}")
def delete_goal(goal_id: int, db: Session = Depends(get_db)):
    goal = delete_goal_by_id(db, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Ziel nicht gefunden")
    return {"message": "Ziel geloscht"}
