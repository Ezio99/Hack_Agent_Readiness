"""Loads the bundled environments and task templates (registration by import). Core contracts stay free of any concrete environment."""
from . import core


def load_all() -> None:
    from ..environments import electronics  # noqa: F401  (registers electronics-v1 and its task templates)


def instances(environment_id: str | None = None):
    load_all()
    return core.all_instances(environment_id)


def get_instance(task_id: str) -> "core.TaskInstance":
    for inst in instances():
        if inst.spec.task_id == task_id:
            return inst
    raise KeyError(f"unknown task id {task_id!r}")
