from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date as date_type

class RunningSessionCreate(BaseModel):
    date: Optional[date_type] = Field(default_factory=date_type.today)
    time: Optional[str] = None
    distance_km: float = Field(gt=0)
    duration_minutes: float = Field(gt=0)
    heart_rate_avg: Optional[int] = None
    route: Optional[str] = None
    weather: Optional[str] = None
    feeling: Optional[str] = None
    note: Optional[str] = None

class RunningSessionUpdate(BaseModel):
    distance_km: Optional[float] = Field(None, gt=0)
    duration_minutes: Optional[float] = Field(None, gt=0)
    heart_rate_avg: Optional[int] = None
    route: Optional[str] = None
    weather: Optional[str] = None
    feeling: Optional[str] = None
    note: Optional[str] = None

class RunningSessionResponse(BaseModel):
    id: int
    date: date_type
    time: Optional[str]
    distance_km: float
    duration_minutes: float
    avg_speed_kmh: float
    calories_burned: float
    heart_rate_avg: Optional[int]
    route: Optional[str]
    weather: Optional[str]
    feeling: Optional[str]
    note: Optional[str]
    
    class Config:
        from_attributes = True

class RunningStats(BaseModel):
    total_distance_km: float
    total_duration_minutes: float
    total_sessions: int
    avg_distance_per_run: float
    avg_speed_kmh: float
    total_calories_burned: float
    best_5k_time: Optional[float]
    best_10k_time: Optional[float]

class WeeklyRunning(BaseModel):
    date: date_type
    distance_km: float
    duration_minutes: float
    avg_speed_kmh: float
    calories_burned: float

class PersonalBests(BaseModel):
    best_5k_minutes: Optional[float]
    best_10k_minutes: Optional[float]
    longest_distance_km: Optional[float]
    fastest_avg_speed: Optional[float]

class RunningGoalCreate(BaseModel):
    goal_type: str
    target_distance_km: Optional[float] = None
    target_time_minutes: Optional[float] = None
    start_date: date_type
    end_date: Optional[date_type] = None

class RunningGoalResponse(BaseModel):
    id: int
    goal_type: str
    target_distance_km: Optional[float]
    target_time_minutes: Optional[float]
    start_date: date_type
    end_date: Optional[date_type]
    achieved: bool
    
    class Config:
        from_attributes = True