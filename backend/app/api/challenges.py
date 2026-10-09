from fastapi import APIRouter
from app.services.challenge_registry import load_challenge_manifests

router = APIRouter(prefix="/challenges", tags=["challenges"])

@router.get("")
def list_challenges():
    return {"items": load_challenge_manifests()}
