import uuid


def new_step_id() -> str:
    return str(uuid.uuid4())


def new_session_id() -> str:
    return str(uuid.uuid4())
