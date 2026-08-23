import json

from app.core.database import SessionLocal
from app.services.publishing import process_due_posts


def main() -> None:
    db = SessionLocal()
    try:
        result = process_due_posts(db)
        print(json.dumps(result, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
