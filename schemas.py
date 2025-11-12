"""
Database Schemas for Solo Leveling themed productivity app

Each Pydantic model represents a MongoDB collection. The collection name is the
lowercase of the class name (e.g., Hunter -> "hunter").
"""
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from datetime import datetime

# Core user (Hunter)
class Hunter(BaseModel):
    display_name: str = Field(..., description="Hunter's display name")
    email: Optional[str] = Field(None, description="Email for identification")
    rank: Literal['E','D','C','B','A','S','Shadow Monarch'] = Field('E', description="Hunter rank")
    level: int = Field(1, ge=1, description="Hunter level")
    exp: int = Field(0, ge=0, description="Current EXP in this level")
    total_exp: int = Field(0, ge=0, description="Lifetime EXP")
    energy: int = Field(100, ge=0, le=100, description="Stamina/Energy 0-100")
    title: Optional[str] = Field(None, description="Current equipped title")

# Stats document
class Stats(BaseModel):
    hunter_id: str = Field(..., description="Reference to hunter _id as string")
    STR: int = Field(1, ge=0)
    INT: int = Field(1, ge=0)
    DEX: int = Field(1, ge=0)
    STA: int = Field(1, ge=0)
    LUK: int = Field(1, ge=0)

# Quest document
class Quest(BaseModel):
    hunter_id: str = Field(...)
    title: str = Field(...)
    description: Optional[str] = None
    type: Literal['daily','weekly','main','dungeon'] = Field('daily')
    exp_reward: int = Field(20, ge=0)
    stat_reward: Optional[dict] = Field(default_factory=dict, description="e.g., {'STR': 1}")
    status: Literal['pending','in_progress','completed','claimed'] = Field('pending')
    due_date: Optional[datetime] = None

# Inventory item
class Item(BaseModel):
    hunter_id: str
    name: str
    category: Literal['weapon','artifact','consumable','cosmetic'] = 'artifact'
    rarity: Literal['common','rare','epic','legendary'] = 'common'
    bonus: Optional[dict] = Field(default_factory=dict, description="e.g., {'INT': 2}")
    lore: Optional[str] = None

# Title (earned achievements)
class Title(BaseModel):
    hunter_id: str
    name: str
    description: Optional[str] = None
    unlocked_at: Optional[datetime] = None

# Activity log for the mini feed
class Log(BaseModel):
    hunter_id: str
    message: str
    level: Literal['info','success','alert'] = 'info'
    created_at: Optional[datetime] = None
