from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date as date_type
import datetime

class CalorieEntryCreate(BaseModel, frozen=True):
    date: Optional[date_type] = None
    meal: str = Field(..., description="Fruhstuck, Mittagessen, Abendessen, Snack")
    food: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0, description="Menge in Gramm")
    calories: float = Field(..., gt=0)
    protein: Optional[float] = Field(default=0.0, ge=0)
    carbs: Optional[float] = Field(default=0.0, ge=0)
    fat: Optional[float] = Field(default=0.0, ge=0)
    note: Optional[str] = None

    def model_post_init(self, _context):
        if self.date is None:
            object.__setattr__(self, 'date', datetime.date.today())

class CalorieEntryUpdate(BaseModel, frozen=True):
    meal: Optional[str] = None
    food: Optional[str] = None
    amount: Optional[float] = Field(None, gt=0)
    calories: Optional[float] = Field(None, gt=0)
    protein: Optional[float] = Field(None, ge=0)
    carbs: Optional[float] = Field(None, ge=0)
    fat: Optional[float] = Field(None, ge=0)
    note: Optional[str] = None

class CalorieEntryResponse(BaseModel, frozen=True):
    id: int
    date: date_type
    meal: str
    food: str
    amount: float
    calories: float
    protein: float
    carbs: float
    fat: float
    note: Optional[str]

    class Config:
        from_attributes = True

class DailySummary(BaseModel, frozen=True):
    date: date_type
    total_calories: float
    total_protein: float
    total_carbs: float
    total_fat: float
    meal_count: int
    meals: List[CalorieEntryResponse]

class WeeklySummary(BaseModel, frozen=True):
    start_date: date_type
    end_date: date_type
    total_calories: float
    avg_calories_per_day: float
    total_protein: float
    total_carbs: float
    total_fat: float
    daily_summaries: List[DailySummary]

class MealSummary(BaseModel, frozen=True):
    meal: str
    total_calories: float
    total_protein: float
    total_carbs: float
    total_fat: float
    entry_count: int

class MacroPercentages(BaseModel, frozen=True):
    protein_percent: float
    carbs_percent: float
    fat_percent: float
    protein_grams: float
    carbs_grams: float
    fat_grams: float

class NutritionGoals(BaseModel, frozen=True):
    calorie_goal: float
    protein_goal: float
    carbs_goal: float
    fat_goal: float

class DailyProgress(BaseModel, frozen=True):
    date: date_type
    consumed: DailySummary
    goals: NutritionGoals
    remaining_calories: float
    remaining_protein: float
    remaining_carbs: float
    remaining_fat: float
    calorie_progress_percent: float
    protein_progress_percent: float
    carbs_progress_percent: float
    fat_progress_percent: float
