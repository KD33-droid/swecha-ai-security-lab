from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.c234 import MessageRequest,SecureRequest
from app.services import c2_runtime,c3_runtime,c4_runtime
from app.services.challenge_timer import refresh_expiry, timer_status

def make_router(slug,svc):
 r=APIRouter(prefix=f'/{slug}',tags=[slug])
 def call(fn,*args):
  try:return fn(*args)
  except ValueError as e:raise HTTPException(400,str(e)) from e
 @r.get('/status')
 def status(session_token:str,run_id:str,db:Session=Depends(get_db)):
  from uuid import UUID
  s,run=call(svc.load,db,session_token,UUID(run_id)); refresh_expiry(db,run); timer=timer_status(run, db=db); rt=run.runtime_state or {}
  return {'run_id':run.id,'phase':run.current_phase,'state':run.state,'score':run.score,'best_score':max(int(run.best_score or 0),int(run.score or 0)),**timer,'discovery_completed':bool(rt.get('discovery_completed')),'discovery_points_awarded':10 if rt.get('discovery_points_awarded') else 0,'root_cause_correct':bool(rt.get('root_cause_correct')),'controls':rt.get('policies',{}),'mitigation_configured':any(v.get('enabled') for v in rt.get('policies',{}).values()),'retest_started':bool(rt.get('retest_started')),'retest_attack_passed':rt.get('retest_attack_passed'),'retest_functionality_passed':rt.get('retest_functionality_passed')}
 @r.post('/message')
 def message(req:MessageRequest,db:Session=Depends(get_db)): return call(svc.message,db,req.session_token,req.run_id,req.message)
 @r.patch('/secure')
 def secure(req:SecureRequest,db:Session=Depends(get_db)): return call(svc.secure,db,req.session_token,req.run_id,req.root_cause,req.controls)
 @r.post('/retest/start')
 def retest_start(req:SecureRequest,db:Session=Depends(get_db)): return call(svc.start_retest,db,req.session_token,req.run_id)
 @r.post('/retest/attack')
 def attack(req:MessageRequest,db:Session=Depends(get_db)): return call(svc.retest,db,req.session_token,req.run_id,req.message)
 @r.post('/retest/functionality')
 def functionality(req:MessageRequest,db:Session=Depends(get_db)): return call(svc.functionality,db,req.session_token,req.run_id,req.message)
 return r
c2_router=make_router('c2',c2_runtime); c3_router=make_router('c3',c3_runtime); c4_router=make_router('c4',c4_runtime)
