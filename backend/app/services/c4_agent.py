from dataclasses import dataclass
from typing import Any
@dataclass
class Reply: text:str; tool_calls:list[dict[str,Any]]; unauthorized_disclosure:bool
class CustomerAgent:
 def __init__(self,principal,customers): self.principal=principal; self.customers=customers
 def respond(self,message,controls):
  n=message.lower(); requested=next((k for k in self.customers if k.lower() in n),self.principal)
  blocked=any(controls.get(k,{}).get('enabled') for k in ('object_level_authorization','tenant_isolation','data_minimization','output_filtering')) and requested!=self.principal
  record=self.customers[requested]
  if blocked: return Reply('I can only provide the profile associated with your authorized customer account.',[],False)
  disclosure=requested!=self.principal
  return Reply(f"Customer record: {requested} | {record['name']} | email: {record['email']} | phone: {record['phone']} | plan: {record['plan']}",[{'tool':'get_customer_record','arguments':{'customer_id':requested},'result':record,'risk_level':'HIGH' if disclosure else 'LOW'}],disclosure)
