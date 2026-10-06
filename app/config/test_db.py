from sqlalchemy import text

from app.config.database import engine


try:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        print("MySQL connection successful!")
        print(result.fetchone())

except Exception as e:
    print("MySQL connection failed!")
    print(e)