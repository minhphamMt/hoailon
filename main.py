import pyodbc

conn_str = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=PHAMDINHMINH\\SQLEXPRESS;DATABASE=aihoailon;UID=sa;PWD=123456'
try:
    conn = pyodbc.connect(conn_str)
    print("Kết nối thành công!")
    conn.close()
except Exception as e:
    print(f"Lỗi kết nối: {e}")
