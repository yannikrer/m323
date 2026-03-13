from pydantic import BaseModel, Field
from typing import Optional
from datetime import date

class WaterEntryCreate(BaseModel):
    datum: Optional[date] = Field(default_factory=date.today)
    menge_ml: int = Field(gt=0, description="Wassermenge in ml")
    ziel_ml: Optional[int] = Field(default=2000, description="Tagesziel in ml")

class WaterEntryUpdate(BaseModel):
    menge_ml: Optional[int] = Field(None, gt=0)
    ziel_ml: Optional[int] = Field(None, gt=0)

class WaterEntryResponse(BaseModel):
    id: int
    datum: date
    menge_ml: int
    ziel_ml: int
    prozent: float
    
    class Config:
        from_attributes = True

class WaterAddAmount(BaseModel):
    menge_ml: int = Field(gt=0, description="Hinzuzufügende Wassermenge in ml")

class WaterStats(BaseModel):
    datum: date
    menge_ml: int
    ziel_ml: int
    prozent: float
    erreicht: bool