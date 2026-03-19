from storage.db import create_all_tables


if __name__ == "__main__":
    create_all_tables()
    print("SQLite tables created.")
