def keep_candidate(candidate):
    if candidate.invalidity_reason:
        return False
    return candidate.rri >= 0.5


def describe_target(target_id, entity_name):
    return f"target={target_id} entity={entity_name}"
