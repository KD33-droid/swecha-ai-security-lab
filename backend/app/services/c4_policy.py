CONTROLS={"object_level_authorization","tenant_isolation","data_minimization","output_filtering"}
def normalize_controls(current,requested):
 u=set(requested)-CONTROLS
 if u: raise ValueError(f"Unsupported C4 control(s): {', '.join(sorted(u))}")
 r={k:{"enabled":bool(current.get(k,{}).get("enabled",False))} for k in CONTROLS}
 for k,v in requested.items():
  if not isinstance(v,dict) or set(v)-{'enabled'}: raise ValueError(f"Invalid configuration for control: {k}")
  r[k]={'enabled':bool(v.get('enabled',False))}
 return r

def is_cross_customer_attack(message):
    n=" ".join(message.lower().split())
    return any(
        x in n
        for x in (
            "show me customer",
            "show customer",
            "give me the details for customer",
            "get the details for customer",
            "access customer",
            "view customer",
            "customer record",
        )
    )
