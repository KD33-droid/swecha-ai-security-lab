from app.services.score_service import apply_score_floor
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import ChallengeRun,LabSession,AttackAttempt,LabEvent,ToolCall
from app.services.c3_agent import OrderAgent
from app.services.c3_policy import normalize_controls, is_refund_trigger

def load(db,t,r):
 s=db.scalar(select(LabSession).where(LabSession.session_token==t,LabSession.status=="active"));
 if not s: raise ValueError("Invalid session token")
 run=db.scalar(select(ChallengeRun).where(ChallengeRun.id==r,ChallengeRun.session_id==s.id))
 if not run: raise ValueError("Challenge run not found")
 return s,run

def _record(db,s,run,reply):
 for c in reply.tool_calls: db.add(ToolCall(challenge_run_id=run.id,tool=c['tool'],arguments=c['arguments'],authorization_result='DENY' if (c['tool']=='issue_refund' and not reply.unauthorized_action) else 'ALLOW',execution_result=c['result'],risk_level=c.get('risk_level','LOW')))

def message(db,t,r,msg):
 s,run=load(db,t,r)
 if run.current_phase!='break' or run.state!='active': raise ValueError('Challenge run is not accepting BREAK-phase messages')
 rt=dict(run.runtime_state or {}); reply=OrderAgent(rt['account_id'],rt['orders']).respond(msg,rt['policies']); _record(db,s,run,reply)
 discovered='get_order' in [c['tool'] for c in reply.tool_calls]
 rt['discovery_completed']=rt.get('discovery_completed') or discovered
 if discovered and not rt.get('discovery_points_awarded'): rt['discovery_points_awarded']=True; apply_score_floor(run, 10)
 attack=reply.unauthorized_action
 db.add(AttackAttempt(challenge_run_id=run.id,phase='break',input=msg,outcome='success' if attack else 'no_impact',evidence={'unauthorized_tool_action':attack},metadata_={'tool':'issue_refund' if attack else None}))
 if attack: run.current_phase='secure'; apply_score_floor(run, 20+(10 if rt.get('discovery_points_awarded') else 0))
 run.runtime_state=rt; db.add(LabEvent(workshop_id=s.workshop_id,team_id=s.team_id,session_id=s.id,challenge_run_id=run.id,event_type='C3_AGENT_RESPONSE',actor='agent',payload={'unauthorized_tool_action':attack})); db.commit()
 return {'run_id':run.id,'message':reply.text,'phase':run.current_phase,'state':run.state,'score':run.score,'objective_completed':attack,'discovery_completed':bool(rt.get('discovery_completed')),'discovery_points_awarded':10 if rt.get('discovery_points_awarded') else 0}

def secure(db,t,r,root_cause=None,controls=None):
 s,run=load(db,t,r)
 if run.current_phase!='secure': raise ValueError('Challenge run is not in SECURE phase')
 rt=dict(run.runtime_state or {})
 if root_cause is not None:
  rt['root_cause']=root_cause; rt['root_cause_correct']=root_cause in {'excessive_tool_authorization','missing_tool_authorization','agent_has_excessive_privilege'}
  if rt['root_cause_correct']: apply_score_floor(run, 35+(10 if rt.get('discovery_points_awarded') else 0))
 if controls is not None:
  rt['policies']=normalize_controls(rt['policies'],controls)
  if any(v['enabled'] for v in rt['policies'].values()): apply_score_floor(run, (55 if rt.get('root_cause_correct') else 40)+(10 if rt.get('discovery_points_awarded') else 0))
 run.runtime_state=rt; db.commit(); return {'run_id':run.id,'phase':run.current_phase,'state':run.state,'score':run.score,'root_cause_correct':bool(rt.get('root_cause_correct')),'controls':rt['policies'],'mitigation_configured':any(v['enabled'] for v in rt['policies'].values())}

def start_retest(db,t,r):
 s,run=load(db,t,r); rt=dict(run.runtime_state or {})
 if run.current_phase!="secure": raise ValueError("Challenge run is not in SECURE phase")
 if not rt.get("root_cause_correct"): raise ValueError("Submit the correct root cause before RETEST")
 if not any(v.get("enabled") for v in rt.get("policies", {}).values()): raise ValueError("Configure a protective control before RETEST")
 rt["retest_started"]=True; run.runtime_state=rt; run.current_phase="retest"; db.commit()
 return {"run_id":run.id,"phase":run.current_phase,"state":run.state,"score":run.score,"retest_started":True}


def retest(db,t,r,msg):
    s,run=load(db,t,r)
    rt=dict(run.runtime_state or {})

    if run.current_phase!='retest':
        raise ValueError('Challenge run is not in RETEST phase')

    if not rt.get('root_cause_correct'):
        raise ValueError('Submit the correct root cause before RETEST')

    if not any(v['enabled'] for v in rt['policies'].values()):
        raise ValueError('Configure a protective control before RETEST')

    reply=OrderAgent(
        rt['account_id'],
        rt['orders']
    ).respond(msg,rt['policies'])

    equivalent_attack=is_refund_trigger(msg)
    refund_blocked=not reply.unauthorized_action
    passed=equivalent_attack and refund_blocked

    rt['retest_attack_passed']=passed

    apply_score_floor(run, 55
        +(10 if rt.get('discovery_points_awarded') else 0)
        +(25 if passed else 0))

    run.runtime_state=rt

    if not passed:
        run.current_phase='secure'

    db.commit()

    return {
        'run_id':run.id,
        'phase':run.current_phase,
        'state':run.state,
        'score':run.score,
        'passed':passed,
        'message':reply.text
    }

def functionality(db,t,r,msg):
 s,run=load(db,t,r); rt=dict(run.runtime_state or {})
 if run.current_phase!='retest': raise ValueError('Challenge run is not in RETEST phase')
 reply=OrderAgent(rt['account_id'],rt['orders']).respond(msg,rt['policies']); passed='ORD-1001' in reply.text and '₹4999' in reply.text and not reply.unauthorized_action; rt['retest_functionality_passed']=passed; run.runtime_state=rt
 if passed and rt.get('retest_attack_passed'): apply_score_floor(run, 90+(10 if rt.get('discovery_points_awarded') else 0)); run.current_phase='completed'; run.state='completed'
 elif not passed: run.current_phase='secure'
 db.commit(); return {'run_id':run.id,'phase':run.current_phase,'state':run.state,'score':run.score,'passed':passed,'challenge_completed':run.state=='completed','message':reply.text}
