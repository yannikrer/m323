from pydantic import BaseModel
from typing import Optional, List
from datetime import date

class MealPlanRequest(BaseModel):
    age:            int
    height:         float
    weight:         float
    eating_habit:   str
    favorite_foods: List[str]
    goal:           Optional[str] = "ausgewogen"
    days:           Optional[int] = 7

class MealPlanResponse(BaseModel):
    request: MealPlanRequest
    plan: str
    date: date

class MealPlanListItem(BaseModel):
    id: int
    date: date
    age: int
    eating_habit: str
    goal: str
    days: int
