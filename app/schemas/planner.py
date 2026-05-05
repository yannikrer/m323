from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date

class MealPlanRequest(BaseModel, frozen=True):
    age:            int   = Field(gt=0, le=120)
    height:         float = Field(gt=0)
    weight:         float = Field(gt=0)
    eating_habit:   str   = Field(min_length=1)
    favorite_foods: List[str] = Field(min_length=1)
    goal:           Optional[str] = Field(default="ausgewogen", min_length=1)
    days:           Optional[int]   = Field(default=7, gt=0, le=30)

class MealPlanResponse(BaseModel, frozen=True):
    request: MealPlanRequest
    plan: str
    date: date

class MealPlanListItem(BaseModel, frozen=True):
    id: int
    date: date
    age: int
    eating_habit: str
    goal: str
    days: int
