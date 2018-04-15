from database import setup_database, delete_old_data

if __name__ == '__main__':
    conn = setup_database()
    delete_old_data(conn)