from xAPIConnector import APIClient, loginCommand 
import os
from dotenv import load_dotenv
import time
from datetime import datetime
import psycopg2

load_dotenv()

DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_HOST = os.environ.get("DB_HOST")
DB_PORT = os.environ.get("DB_PORT")

conn = psycopg2.connect(
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT
)

cursor = conn.cursor()

def create_trade_tables():
    try:
        # Create table if not exists
        create_table_query = '''
        CREATE TABLE IF NOT EXISTS open_trades (
            id SERIAL PRIMARY KEY,
            cmd INTEGER,
            order_no INTEGER UNIQUE,
            symbol VARCHAR(50),
            volume FLOAT,
            open_price FLOAT,
            open_time TIMESTAMP,
            close_time TIMESTAMP,
            sl FLOAT,
            tp FLOAT
        )
        '''
        cursor.execute(create_table_query)    
        
        create_table_query = '''
        CREATE TABLE IF NOT EXISTS past_trades (
            id SERIAL PRIMARY KEY,
            cmd INTEGER,
            order_no INTEGER UNIQUE,
            symbol VARCHAR(50),
            volume FLOAT,
            open_price FLOAT,
            open_time TIMESTAMP,
            close_time TIMESTAMP,
            sl FLOAT,
            tp FLOAT
        )
        '''
        cursor.execute(create_table_query)    


        conn.commit()
        print("Table created successfully!")

    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL:", error)


def create_user_table():
    try:
        # Create table if not exists
        create_table_query = '''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id INTEGER UNIQUE,
            password VARCHAR(50)
        )
        '''
        cursor.execute(create_table_query)    
    
        conn.commit()
        print("User table created successfully!")
        
    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL:", error)   


def add_users(user_id, password):
    try:
        # Insert user data into the users table
        insert_query = '''
        INSERT INTO users (user_id, password)
        VALUES (%s, %s)
        '''
        cursor.execute(insert_query, (user_id, password))

        conn.commit()
        print("User added successfully!")

    except (Exception, psycopg2.Error) as error:
        print("Error while adding user to PostgreSQL:", error)


def drop_tables(table_names):
    try:
        # Drop each table in the list
        for table_name in table_names:
            cursor.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")

        # Commit the transaction
        conn.commit()
        print("Tables dropped successfully!")

    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL:", error)


def insert_data_trades_table(trades_data):
    inserted_rows_data = []
    removed_comments = []

    try:
        for trade in trades_data:
            if trade.get('close_time') is None:
                trade['close_time'] = 4102444800000

            cursor.execute("""
                INSERT INTO open_trades (cmd, order_no, symbol, volume, open_price, open_time, close_time, sl, tp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (order_no) DO NOTHING
                RETURNING *
                """, (
                    trade.get('cmd', ''),
                    trade.get('order', 0),
                    trade.get('symbol', ''),
                    trade.get('volume', 0.0),
                    trade.get('open_price', 0),
                    datetime.fromtimestamp(trade.get('open_time', 0) / 1000),
                    datetime.fromtimestamp(trade.get('close_time', 4102444800000) / 1000),
                    trade.get('sl', 0.0),
                    trade.get('tp', 0.0)
                )
            )

            row = cursor.fetchone()
            if row:
                inserted_rows_data.append(
                    {
                        'cmd': row[1],
                        'order': row[2],
                        'symbol': row[3],
                        'volume': row[4],
                        'open_price': row[5],
                        'open_time': row[6].strftime('%Y-%m-%d %H:%M:%S'),  # Corrected date format
                        'close_time': row[7].strftime('%Y-%m-%d %H:%M:%S'),  # Corrected date format
                        'sl': row[8],
                        'tp': row[9],
                    }
                )

        # Fetch all order numbers from open_trades
        cursor.execute("SELECT order_no FROM open_trades")
        all_order_numbers = [row[0] for row in cursor.fetchall()]

        # Find order numbers not in inserted_rows_data
        for order_no in all_order_numbers:
            if order_no not in [row['order'] for row in trades_data]:
                removed_comments.append(order_no)

        if removed_comments:
            for comment in removed_comments:
                cursor.execute("""
                    INSERT INTO past_trades (cmd, order_no, symbol, volume, open_price, open_time, close_time, sl, tp)
                    SELECT cmd, order_no, symbol, volume, open_price, open_time, now(), sl, tp
                    FROM open_trades
                    WHERE order_no = %s
                """, (comment,))

            # Delete rows from open_trades where order_no is in removed_comments
            cursor.execute("DELETE FROM open_trades WHERE order_no IN %s", (tuple(removed_comments),))


        conn.commit()

    except Exception as error:
        print("Error while inserting or moving trades:", error)

    return inserted_rows_data, removed_comments



def print_open_trades():
    try:
        cursor.execute("SELECT * FROM open_trades")
        rows = cursor.fetchall()
        
        if rows:
            print("Contents of open_trades table:")
            for row in rows:
                print(row)
        else:
            print("No records found in open_trades table.")

    except (Exception, psycopg2.Error) as error:
        print("Error while fetching data from open_trades table:", error)


def print_past_trades():
    try:
        cursor.execute("SELECT * FROM past_trades")
        rows = cursor.fetchall()
        
        if rows:
            print("Contents of past_trades table:")
            for row in rows:
                print(row)
        else:
            print("No records found in past_trades table.")

    except (Exception, psycopg2.Error) as error:
        print("Error while fetching data from past_trades table:", error)


def print_users_trades():
    try:
        cursor.execute("SELECT * FROM users")
        rows = cursor.fetchall()
        
        if rows:
            print("Contents of users table:")
            for row in rows:
                print(row)
        else:
            print("No records found in users table.")

    except (Exception, psycopg2.Error) as error:
        print("Error while fetching data from users table:", error)


def get_all_users():
    try:
        cursor.execute("SELECT * FROM users")
        rows = cursor.fetchall()
        return rows        

    except (Exception, psycopg2.Error) as error:
        print("Error while fetching data from users table:", error)

def make_trade(user_client, inserted_rows_data):   
    for inserted_row_data in inserted_rows_data: 
        args = {
                "tradeTransInfo": {
                    "cmd": inserted_row_data['cmd'],
                    "comment": str(inserted_row_data['order']),
                    "expiration": 0,
                    "price": inserted_row_data['open_price'],
                    "sl": inserted_row_data['sl'],
                    "tp": inserted_row_data['tp'],
                    "symbol": inserted_row_data['symbol'],
                    "type": 0,
                    "volume": inserted_row_data['volume']
                }
        }
        
        response = user_client.commandExecute("tradeTransaction", args)
        if response['status']:
            print("Trade successfully executed.")
        else:
            print("Trade execution failed. Error code:", response['errorCode'])


def get_client(userId, password):    
    client = APIClient()
    
    loginResponse = client.execute(loginCommand(userId=userId, password=password))
    
    if not loginResponse['status']:
        print('Login failed. Error code: {0}'.format(loginResponse['errorCode']))
        

def get_order_by_comment(client, comment):
    trades = get_trades(client)
    
    for trade in trades:
        if trade['comment'] == comment:
            return trade
    
    return None


def get_trades(client):
    args =  {
		"openedOnly": True,
	}
    
    response = client.commandExecute("getTrades", args)['returnData']
    
    return response


def close_trade(user_client, removed_comments):
    for removed_comment in removed_comments:
        trade_by_comment = get_order_by_comment(user_client, removed_comment)
        print(trade_by_comment)
        
        args = {
            "tradeTransInfo": {
                "type": 2,
                "order": int(trade_by_comment['order']),
                "symbol": trade_by_comment['symbol'],
                "price": trade_by_comment['close_price'],
                "volume": float(trade_by_comment['volume'])
            }
        }
        
        print(args)
        
        response = user_client.commandExecute("tradeTransaction", args)
        if response['status']:
            print("Trade successfully closed.")
        else:
            print("Failed to close trade. Error code:", response['errorCode'])


def main():
    master_userId = os.environ.get("MASTER_ID")
    master_password = os.environ.get("MASTER_PASSWORD")
    master_client = APIClient()
    loginResponse = master_client.execute(loginCommand(userId=master_userId, password=master_password))
    
    # drop_tables(['open_trades', 'past_trades'])
    # create_trade_tables()
    # create_user_table()
    
    while True:
        time.sleep(5)

        trades_data = get_trades(master_client)
        inserted_rows_data, removed_comments = insert_data_trades_table(trades_data)

        users = get_all_users()
        
        for user in users:
            user_client = APIClient()
            loginResponse = user_client.execute(loginCommand(userId=user[1], password=user[2]))
            make_trade(user_client, inserted_rows_data)
            close_trade(user_client, removed_comments) 
    
    
if __name__ == '__main__':
    main()
