from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from core.database import SessionLocal
from core.models import User

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/users")
def get_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return users

@app.post("/users")
def create_user(user_data: dict, db: Session = Depends(get_db)):
    user = User(tg_id=user_data['tg_id'], name=user_data['name'])
    db.add(user)
    db.commit()
    return {"status": "created"}