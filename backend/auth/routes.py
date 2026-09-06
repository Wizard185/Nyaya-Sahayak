"""Signup / login / profile routes, all backed by MongoDB's `users` collection."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from auth.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from db.mongo import users_collection

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ProfileUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class PasswordUpdateRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class PublicUser(BaseModel):
    id: str
    name: str
    email: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: PublicUser


def _public_user(user: dict) -> PublicUser:
    return PublicUser(id=str(user["_id"]), name=user["name"], email=user["email"])


@router.post("/signup", response_model=AuthResponse)
async def signup(req: SignupRequest):
    email = req.email.lower()
    existing = await users_collection().find_one({"email": email})
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    doc = {
        "name": req.name.strip(),
        "email": email,
        "password_hash": hash_password(req.password),
        "created_at": datetime.now(timezone.utc),
    }
    result = await users_collection().insert_one(doc)
    doc["_id"] = result.inserted_id
    token = create_access_token(str(doc["_id"]))
    return AuthResponse(access_token=token, user=_public_user(doc))


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    user = await users_collection().find_one({"email": req.email.lower()})
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    token = create_access_token(str(user["_id"]))
    return AuthResponse(access_token=token, user=_public_user(user))


@router.get("/me", response_model=PublicUser)
async def me(user: dict = Depends(get_current_user)):
    return _public_user(user)


@router.put("/profile", response_model=PublicUser)
async def update_profile(req: ProfileUpdateRequest, user: dict = Depends(get_current_user)):
    await users_collection().update_one({"_id": user["_id"]}, {"$set": {"name": req.name.strip()}})
    user["name"] = req.name.strip()
    return _public_user(user)


@router.put("/password")
async def update_password(req: PasswordUpdateRequest, user: dict = Depends(get_current_user)):
    if not verify_password(req.current_password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")
    await users_collection().update_one(
        {"_id": user["_id"]}, {"$set": {"password_hash": hash_password(req.new_password)}}
    )
    return {"status": "ok"}
