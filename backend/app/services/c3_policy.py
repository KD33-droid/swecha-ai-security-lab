CONTROLS={"least_privilege","tool_authorization","approval_gate","parameter_validation"}

def normalize_controls(current,requested):
    unknown=set(requested)-CONTROLS
    if unknown:
        raise ValueError(f"Unsupported C3 control(s): {', '.join(sorted(unknown))}")

    r={
        k:{"enabled":bool(current.get(k,{}).get("enabled",False))}
        for k in CONTROLS
    }

    for k,v in requested.items():
        if not isinstance(v,dict) or set(v)-{"enabled"}:
            raise ValueError(f"Invalid configuration for control: {k}")
        r[k]={"enabled":bool(v.get("enabled",False))}

    return r


def is_refund_trigger(message):
    n=" ".join(message.lower().split())
    return any(
        x in n
        for x in (
            "issue a refund",
            "process a refund",
            "give me a refund",
            "refund this order",
        )
    )
