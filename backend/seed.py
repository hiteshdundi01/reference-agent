"""uv run -m backend.seed: rebuild the database at APP_DB from data/."""

from backend.database import engine, seed

if __name__ == "__main__":
    seed(engine())
    print("Seeded the database from data/")
