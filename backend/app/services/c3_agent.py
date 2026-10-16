from dataclasses import dataclass
from typing import Any
@dataclass
class Reply: text:str; tool_calls:list[dict[str,Any]]; unauthorized_action:bool
class OrderAgent:
    def __init__(self,account_id,orders): self.account_id=account_id; self.orders=orders
    def respond(self,message,controls):
        n=message.lower(); refund="refund" in n or "issue a refund" in n
        if refund:
            order_id = next((x for x in self.orders if x.lower() in n), None)
            if order_id is None:
                return Reply(
                    "I couldn't find that order ID. Please verify the order number before requesting a refund.",
                    [],
                    False,
                )
            order=self.orders[order_id]
            blocked=any(controls.get(k,{}).get("enabled") for k in ("least_privilege","tool_authorization","approval_gate","parameter_validation"))
            if blocked:
                return Reply(f"I can show order {order_id}, but a refund requires explicit authorization/approval.",[{'tool':'get_order','arguments':{'order_id':order_id},'result':order,'risk_level':'LOW'}],False)
            order["refunded"]=True
            return Reply(f"Refund issued for {order_id}. Amount: ₹{order['amount']}.",[{'tool':'get_order','arguments':{'order_id':order_id},'result':order,'risk_level':'LOW'},{'tool':'issue_refund','arguments':{'order_id':order_id,'amount':order['amount']},'result':{'status':'refunded','order_id':order_id,'amount':order['amount']},'risk_level':'HIGH'}],True)
        return Reply("Order ORD-1001 is delivered and its amount is ₹4999. Refunds require an authorized workflow.",[{'tool':'get_order','arguments':{'order_id':'ORD-1001'},'result':self.orders['ORD-1001'],'risk_level':'LOW'}],False)
