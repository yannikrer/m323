from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import Boolean, Table, create_engine, Column, Integer, String, ForeignKey, Date, Float, Text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

DATABASE_URL = "sqlite:///./gymtracker.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

"""
workout_exercises = Table(
    "workout_exercises",
    Base.metadata,
    Column("workout_id", Integer, ForeignKey("workouts.id"), primary_key=True),
    Column("exercise_id", Integer, ForeignKey("exercises.id"), primary_key=True),
)
"""

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String) 

class Water(Base):
    __tablename__ = "water"

    id = Column(Integer, primary_key=True, index=True)
    datum = Column(Date, index=True)
    menge_ml = Column(Integer, default=0)
    ziel_ml = Column(Integer, default=2000) 

class Calories(Base):
    __tablename__ = "calories"

    id       = Column(Integer, primary_key=True, index=True)
    date     = Column(Date, default=datetime.date.today)
    meal     = Column(String, nullable=False)        
    food     = Column(String, nullable=False)        
    amount   = Column(Float, nullable=False)         
    calories = Column(Float, nullable=False)         
    protein  = Column(Float, default=0.0)            
    carbs    = Column(Float, default=0.0)            
    fat      = Column(Float, default=0.0)            
    note     = Column(String, nullable=True)

class MealPlan(Base):
    __tablename__ = "mealplans"

    id            = Column(Integer, primary_key=True, index=True)
    date          = Column(Date, default=datetime.date.today)
    age           = Column(Integer,  nullable=False)
    height        = Column(Float,    nullable=False)
    weight        = Column(Float,    nullable=False)
    eating_habit  = Column(String,   nullable=False)
    favorite_foods= Column(String,   nullable=False)
    goal          = Column(String,   default="ausgewogen")
    days          = Column(Integer,  default=7)
    plan          = Column(Text,     nullable=False)

class RunningSession(Base):
    __tablename__ = "running_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, default=datetime.date.today)
    time = Column(String, nullable=True)
    distance_km = Column(Float, nullable=False)
    duration_minutes = Column(Float, nullable=False)
    avg_speed_kmh = Column(Float, nullable=True)
    calories_burned = Column(Float, nullable=True)
    heart_rate_avg = Column(Integer, nullable=True)
    route = Column(String, nullable=True)
    weather = Column(String, nullable=True)
    feeling = Column(String, nullable=True)
    note = Column(Text, nullable=True)

class RunningGoal(Base):
    __tablename__ = "running_goals"
    
    id = Column(Integer, primary_key=True, index=True)
    goal_type = Column(String, nullable=False)
    target_distance_km = Column(Float, nullable=True)
    target_time_minutes = Column(Float, nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    achieved = Column(Boolean, default=False)
    
# Hier könnten wir dann noch hinzufügen, dass man Übungen und Workouts erstellen kann
"""
class Exercise(Base):
    __tablename__ = "exercises"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    weight = Column(Integer)
    reps = Column(Integer)
    note = Column(String)

    workouts = relationship(
        "Workout", 
        secondary=workout_exercises,
        back_populates="exercises"
    )

class Workout(Base):
    __tablename__ = "workouts"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    exercises = relationship(
        "Exercise",
        secondary=workout_exercises,
        back_populates="workouts"
    )
"""
def create_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
