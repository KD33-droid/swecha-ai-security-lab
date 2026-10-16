from dataclasses import dataclass
from typing import Any
@dataclass
class Reply: text:str; tool_calls:list[dict[str,Any]]; unauthorized_disclosure:bool
class CustomerAgent:
    def __init__(self, principal, customers):
        self.principal = principal
        self.customers = customers

    def respond(self, message, controls):
        import re

        mentioned = re.search(r"\bCUST-\d+\b", message, re.IGNORECASE)
        requested_id = mentioned.group(0).upper() if mentioned else None
        requested = next(
            (key for key in self.customers if key.lower() == (requested_id or "").lower()),
            None,
        )

        if requested_id and requested is None:
            return Reply(f"Customer ID {requested_id} was not found.", [], False)

        requested = requested or self.principal
        blocked = any(
            controls.get(key, {}).get("enabled")
            for key in (
                "object_level_authorization",
                "tenant_isolation",
                "data_minimization",
                "output_filtering",
            )
        ) and requested != self.principal

        if blocked:
            return Reply(
                "I can only provide the profile associated with your authorized customer account.",
                [],
                False,
            )

        record = self.customers[requested]
        disclosure = requested != self.principal
        return Reply(
            f"Customer record: {requested} | {record['name']} | email: {record['email']} | "
            f"phone: {record['phone']} | plan: {record['plan']}",
            [{
                "tool": "get_customer_record",
                "arguments": {"customer_id": requested},
                "result": record,
                "risk_level": "HIGH" if disclosure else "LOW",
            }],
            disclosure,
        )
