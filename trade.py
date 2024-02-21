from xAPIConnector import APIClient, loginCommand 
import os
from dotenv import load_dotenv
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import psycopg2
import logging
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import pandas as pd


load_dotenv()

script_logger = logging.getLogger(__name__)
file_handler = logging.FileHandler('Logfile.log', encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
script_logger.addHandler(file_handler)

DB_NAME = os.environ.get("DB_NAME")
DB_NAME_MAIN = os.environ.get("DB_NAME_MAIN")
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

conn_user = psycopg2.connect(
    dbname=DB_NAME_MAIN,
    user=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT
)

cursor_user = conn_user.cursor()

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
            xstation_id INTEGER UNIQUE,
            password VARCHAR(255)
        )
        '''
        cursor.execute(create_table_query)    
    
        conn.commit()
        print("User table created successfully!")
        
    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL:", error)   


def encrypt(text):
    key = os.environ.get('AES_KEY').encode()
    cipher = AES.new(key, AES.MODE_ECB)
    padded_text = pad(text.encode(), AES.block_size)
    encrypted_text = cipher.encrypt(padded_text)
    return base64.b64encode(encrypted_text).decode()

def decrypt(encrypted_text):
    key = os.environ.get('AES_KEY').encode()
    cipher = AES.new(key, AES.MODE_ECB)
    encrypted_bytes = base64.b64decode(encrypted_text)
    decrypted_bytes = cipher.decrypt(encrypted_bytes)
    unpadded_text = unpad(decrypted_bytes, AES.block_size)
    return unpadded_text.decode()


def add_users(user_id, password):
    try:
        # Insert user data into the users table
        insert_query = '''
        INSERT INTO users (xstation_id, password)
        VALUES (%s, %s)
        '''
        cursor.execute(insert_query, (user_id, encrypt(password)))

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
        cursor_user.execute("SELECT * FROM users_credentials_xstation")
        rows = cursor_user.fetchall()
        
        if rows:
            print("Contents of users_credentials_xstation table:")
            for row in rows:
                print(row)
        else:
            print("No records found in users_credentials_xstationusers table.")

    except (Exception, psycopg2.Error) as error:
        print("Error while fetching data from users_credentials_xstation table:", error)


def get_all_users():
    try:
        cursor_user.execute("SELECT * FROM users_credentials_xstation WHERE verification = TRUE")
        rows = cursor_user.fetchall()
        return rows        

    except (Exception, psycopg2.Error) as error:
        print("Error while fetching data from users_credentials_xstation table:", error)


def get_all_users_test():
    try:
        cursor.execute("SELECT * FROM users")
        rows = cursor.fetchall()
        return rows        

    except (Exception, psycopg2.Error) as error:
        print("Error while fetching data from users table:", error)


def send_slack_message(e):
    slack_token = os.environ.get("SLACK_API_TOKEN")
    channel_id = os.environ.get("CHANNEL_ID")
        
    try:
        client = WebClient(token=slack_token)
        
        message = f"Error encountered: {e}"
        response = client.chat_postMessage(
            channel=channel_id,
            text=message
        )
    
    except SlackApiError as e:
            print(f"Slack API error: {e.response['error']}")


def make_trade(user_client, inserted_rows_data, userId):   
    try:
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
            
            time.sleep(1)
    
    except Exception as e:
        script_logger.error(f"Error: {e} for userId: {userId}")
        send_slack_message(f"Error: {e} for userId: {userId}")


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


def close_trade(user_client, removed_comments, userId):    
    try:
        for removed_comment in removed_comments:
            trade_by_comment = get_order_by_comment(user_client, str(removed_comment))

            if not trade_by_comment:
                continue
            
            args = {
                "tradeTransInfo": {
                    "type": 2,
                    "order": int(trade_by_comment['order']),
                    "symbol": trade_by_comment['symbol'],
                    "price": trade_by_comment['close_price'],
                    "volume": float(trade_by_comment['volume'])
                }
            }
            
            order_response = user_client.commandExecute("tradeTransaction", args)['returnData']['order']
            time.sleep(2)
            
            args =  {
		        "order": order_response,
	        }
    
            response = user_client.commandExecute("tradeTransactionStatus", args)['returnData']
            
            if response["requestStatus"] in [0, 3]: 
                print("Trade successfully closed.")
            else:
                args = {
                    "tradeTransInfo": {
                        "type": 2,
                        "order": int(trade_by_comment['order']),
                        "symbol": trade_by_comment['symbol'],
                        "price": trade_by_comment['close_price'],
                        "volume": float(trade_by_comment['volume'])
                    }
                }
                
                response = user_client.commandExecute("tradeTransaction", args)
    
    except Exception as e:
        script_logger.error(f"Error: {e} for userId: {userId}")
        send_slack_message(f"Error: {e} for userId: {userId}")


def update_verification(xstation_id, verification_status):
    try:
        print("xstation_id: ", xstation_id)
        cursor_user.execute(f"UPDATE users_credentials_xstation SET verification = {verification_status} WHERE xstation_id = {xstation_id}")
        conn_user.commit()
    except (Exception, psycopg2.Error) as error:
        print("Error while updating verification status:", error)


def user_trading(user, inserted_rows_data, removed_comments):
    user_client = None  # Initialize user_client outside the try block
    try:
        user_client = APIClient()
        loginResponse = user_client.execute(loginCommand(userId=user[1], password=decrypt(user[2])))
                  
        if loginResponse['status']:  
            if inserted_rows_data:
                make_trade(user_client, inserted_rows_data, user[1])
            
            if removed_comments:
                close_trade(user_client, removed_comments, user[1]) 
        
        else:
            print("Failed: ", user[1])
            update_verification(user[1], False)    
                    
    except Exception as e:
        script_logger.error("Error: ", e)
        send_slack_message(e)
    finally:
        if user_client:
            user_client.disconnect()

def load_demo_users(file):
    df = pd.read_csv(file)
    for _, row in df.iterrows():
        user_id = row['User ID']
        password = row['Password']
        add_users(user_id, password)
    
    

def main():
    master_userId = os.environ.get("MASTER_ID")
    master_password = os.environ.get("MASTER_PASSWORD")
    master_client = APIClient()
    loginResponse = master_client.execute(loginCommand(userId=master_userId, password=master_password))
    
    drop_tables(['open_trades', 'past_trades'])
    create_trade_tables()
    
    # drop_tables(['users'])
    # create_user_table()
    # load_demo_users("xStation_Credentials.csv")

    # add_users(15770950, 'Abcd@1234')
    # add_users(15780436, 'Check@123')
    # add_users(15780442, 'Bhim@123')
    # add_users(15780445, 'Password@123')
    # add_users(15780439, 'Prince@123')
    
    # add_users(15792177, 'Check@123')
    
    # add_users(15792180, 'Check@123')
    # add_users(15792191, 'Check@123')
    # add_users(15792193, 'Check@123')
    # add_users(15792200, 'Check@123')
    # add_users(15792205, 'Check@123')

    # add_users(15792273, 'Check@123')
    # add_users(15792266, 'Check@123')
    # add_users(15792277, 'Check@123')
    # add_users(15792281, 'Check@123')
    # add_users(15792284, 'Check@123')
    # add_users(15792299, 'Check@123')
    # add_users(15792300, 'Check@123')
    # add_users(15792303, 'Check@123')
    # add_users(15792304, 'Check@123')
    # add_users(15792312, 'Check@123')
    
    # add_users(15792325, 'Check@123')
    # add_users(15792330, 'Check@123')
    # add_users(15792337, 'Check@123')
    # add_users(15792342, 'Check@123')
    # add_users(15792348, 'Check@123')
    
    # add_users(15792357, 'Check@123')
    # add_users(15792363, 'Check@123')
    # add_users(15792371, 'Check@123')
    
    # add_users(15792377, 'Check@123')
    # add_users(15792392, 'Check@123')
    # add_users(15792387, 'Check@123')
    # add_users(15792409, 'Check@123')
    
    
    while True:
        try:
            trades_data = get_trades(master_client)
            inserted_rows_data, removed_comments = insert_data_trades_table(trades_data)
            
            if inserted_rows_data or removed_comments:
                
                # users = get_all_users()
                users = get_all_users_test()
                
                if users:
                    with ThreadPoolExecutor(max_workers=len(users)) as executor:
                        for user in users:
                            executor.submit(user_trading, user, inserted_rows_data, removed_comments)
            
            time.sleep(5)
        
        except Exception as e:
            script_logger.error("Error: ", e)
            send_slack_message(e)
    
if __name__ == '__main__':
    main()
