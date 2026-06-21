def summarize(rows):
    targets = [row for row in rows if row["kind"] == "target"]
    entities = [row for row in rows if row["kind"] == "entity"]
    return {"targets": len(targets), "entities": len(entities)}
