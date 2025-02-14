from fastapi import FastAPI, HTTPException, APIRouter
from pydantic import BaseModel, Field, validator
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone, timedelta
from typing import Optional, List

app = FastAPI()
router = APIRouter()
client = AsyncIOMotorClient("mongodb+srv://queenxytra:queenxytra@cluster0.ivuxz80.mongodb.net/?retryWrites=true&w=majority")
db = client.blog_db

# IST (Indian Standard Time) as UTC +5:30
ist = timezone(timedelta(hours=5, minutes=30))

@router.get("/alive")
async def health_check():
    return {"status": "alive"}

@app.get("/alive")
async def health_check():
    return {"status": "alive"}
    
class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return str(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")

class Blog(BaseModel):
    _id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    title: str
    content: str
    author: str
    tags: List[str]
    views: int = 0
    likes: int = 0
    createdAt: datetime
    updatedAt: datetime

    class Config:
        allow_population_by_field_name = True
        json_encoders = {ObjectId: str}

class BlogCreate(BaseModel):
    title: str
    content: str
    author: str
    tags: List[str]

class BlogUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    tags: Optional[List[str]] = None

class BlogStatsUpdate(BaseModel):
    views: Optional[int] = None
    likes: Optional[int] = None

    @validator('*', pre=True, allow_reuse=True)
    def check_positive(cls, v):
        if v is not None and v < 0:
            raise ValueError("Value must be positive")
        return v

@router.get("/", response_model=List[Blog])
async def get_all_blogs():
    try:
        blogs = []
        async for blog in db.blogs.find():
            blog['_id'] = str(blog['_id'])
            blogs.append(Blog(**blog))
        return blogs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{id}", response_model=Blog)
async def get_blog(id: str):
    try:
        blog = await db.blogs.find_one({"_id": ObjectId(id)})
        if not blog:
            raise HTTPException(status_code=404, detail="Blog not found")
        blog['_id'] = str(blog['_id'])
        return Blog(**blog)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=Blog)
async def create_blog(blog: BlogCreate):
    try:
        blog_data = blog.dict()
        blog_data['_id'] = ObjectId()
        blog_data['createdAt'] = blog_data['updatedAt'] = datetime.now(ist)
        blog_data['views'] = 0
        blog_data['likes'] = 0
        await db.blogs.insert_one(blog_data)
        blog_data['_id'] = str(blog_data['_id'])
        return Blog(**blog_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{id}", response_model=Blog)
async def update_blog(id: str, blog_update: BlogUpdate):
    try:
        update_data = blog_update.dict(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No data provided for update")
        update_data['updatedAt'] = datetime.now(ist)
        result = await db.blogs.update_one(
            {"_id": ObjectId(id)},
            {"$set": update_data}
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Blog not found")
        updated_blog = await db.blogs.find_one({"_id": ObjectId(id)})
        updated_blog['_id'] = str(updated_blog['_id'])
        return Blog(**updated_blog)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{id}")
async def delete_blog(id: str):
    try:
        result = await db.blogs.delete_one({"_id": ObjectId(id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail ="Blog not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{id}", response_model=Blog)
async def update_blog_stats(id: str, stats: BlogStatsUpdate):
    try:
        stats_data = stats.dict(exclude_unset=True)
        if not stats_data:
            raise HTTPException(status_code =400, detail="No stats provided")
        increment = {}
        if 'views' in stats_data:
            increment['views'] = stats_data['views']
        if 'likes' in stats_data:
            increment['likes'] = stats_data['likes']
        if not increment:
            raise HTTPException(status_code=400, detail="No valid stats provided")
        update_data = {
            "$inc": increment,
            "$set": {"updatedAt": datetime.now(ist)}
        }
        result = await db.blogs.update_one(
            {"_id": ObjectId(id)},
            update_data
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Blog not found")
        updated_blog = await db.blogs.find_one({"_id": ObjectId(id)})
        updated_blog['_id'] = str(updated_blog['_id'])
        return Blog(**updated_blog)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

app.include_router(router, prefix="/api/blogs")

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
