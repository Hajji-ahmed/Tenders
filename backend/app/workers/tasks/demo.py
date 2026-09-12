from app.workers.tracking import tracked_task


@tracked_task("demo")
def demo_task(db, job, *, x: int) -> dict:
    """Tâche de démonstration : valide la chaîne API → Redis → worker → base."""
    if x < 0:
        raise ValueError("x doit être positif")
    return {"doubled": x * 2}
