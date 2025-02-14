from fastapi import FastAPI, HTTPException, APIRouter, Depends
from pydantic import BaseModel, Field, validator
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from datetime import datetime, timezone, timedelta
from typing import Optional, List
import os

app = FastAPI()
router = APIRouter()
ist = timezone(timedelta(hours=5, minutes=30))

# MongoDB connection setup
async def get_db() -> AsyncIOMotorDatabase:
    return app.mongodb_client.get_database("blog_db")

@app.on_event("startup")
async def startup_db_client():
    try:
        app.mongodb_client = AsyncIOMotorClient(os.getenv("MONGODB_URI", "mongodb+srv://queenxytra:queenxytra@cluster0.ivuxz80.mongodb.net/?retryWrites=true&w=majority"))
        await app.mongodb_client.admin.command('ping')
        print("✅ MongoDB connected successfully!")
    except Exception as e:
        print("❌ MongoDB connection failed:", e)
        raise

@app.on_event("shutdown")
async def shutdown_db_client():
    app.mongodb_client.close()

@router.get("/alive")
async def health_check(db: AsyncIOMotorDatabase = Depends(get_db)):
    try:
        await db.command('ping')
        return {"status": "alive", "database": "connected"}
    except Exception as e:
        return {"status": "alive", "database": "disconnected", "error": str(e)}

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
async def get_all_blogs(db: AsyncIOMotorDatabase = Depends(get_db)):
    try:
        blogs = []
        async for blog in db.blogs.find():
            blog['_id'] = str(blog['_id'])
            blogs.append(Blog(**blog))
        return blogs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{id}", response_model=Blog)
async def get_blog(id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    try:
        blog = await db.blogs.find_one({"_id": ObjectId(id)})
        if not blog:
            raise HTTPException(status_code=404, detail="Blog not found")
        blog['_id'] = str(blog['_id'])
        return Blog(**blog)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=Blog)
async def create_blog(blog: BlogCreate, db: AsyncIOMotorDatabase = Depends(get_db)):
    try:
        blog_data = blog.dict()
        blog_data['_id'] = ObjectId()
        blog_data['createdAt'] = blog_data['updatedAt'] = datetime.now(ist)
        await db.blogs.insert_one(blog_data)
        return Blog(**blog_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{id}", response_model=Blog)
async def update_blog(id: str, blog_update: BlogUpdate, db: AsyncIOMotorDatabase = Depends(get_db)):
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
        return Blog(**updated_blog)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{id}")
async def delete_blog(id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    try:
        result = await db.blogs.delete_one({"_id": ObjectId(id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Blog not found")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{id}", response_model=Blog)
async def update_blog_stats(id: str, stats: BlogStatsUpdate, db: AsyncIOMotorDatabase = Depends(get_db)):
    try:
        stats_data = stats.dict(exclude_unset=True)
        if not stats_data:
            raise HTTPException(status_code=400, detail="No stats provided")
        
        increment = {k: v for k, v in stats_data.items() if k in ['views', 'likes']}
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
        return Blog(**updated_blog)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

app.include_router(router, prefix="/api/blogs")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
