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
import requests


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
            tp FLOAT,
            master_id VARCHAR(50)
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
            tp FLOAT,
            master_id VARCHAR(50)
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


def get_symbol_cateogry(user_client, symbol):
    args = {
            "symbol": symbol
    }
                    
    response = user_client.commandExecute("getSymbol", args)
    return response['returnData']['categoryName']

def insert_data_trades_table(trades_data, master_id, is_stock, client):
    inserted_rows_data = []
    removed_comments = []

    try:
        for trade in trades_data:
            if trade.get('close_time') is None:
                trade['close_time'] = 4102444800000

            cursor.execute("""
                INSERT INTO open_trades (cmd, order_no, symbol, volume, open_price, open_time, close_time, sl, tp, master_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    trade.get('tp', 0.0),
                    master_id
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
                        'master_id' : master_id,
                        'is_stock' : is_stock,
                        'category' : get_symbol_cateogry(client ,row[3])
                    }
                )
               
        cursor.execute("SELECT order_no FROM open_trades WHERE master_id = %s", (master_id,))
        all_order_numbers = [row[0] for row in cursor.fetchall()]

        # Find order numbers not in inserted_rows_data
        for order_no in all_order_numbers:
            if order_no not in [row['order'] for row in trades_data]:
                removed_comments.append((order_no, master_id, is_stock))

        if removed_comments:
            for comment in removed_comments:
                cursor.execute("""
                    INSERT INTO past_trades (cmd, order_no, symbol, volume, open_price, open_time, close_time, sl, tp, master_id)
                    SELECT cmd, order_no, symbol, volume, open_price, open_time, now(), sl, tp, master_id
                    FROM open_trades
                    WHERE order_no = %s AND master_id = %s
                """, (comment[0], comment[1]))

            # Delete rows from open_trades where order_no is in removed_comments
            placeholders = ','.join(['%s'] * len(removed_comments))
            cursor.execute("DELETE FROM open_trades WHERE (order_no, master_id) IN ({})".format(placeholders), [x[:2] for x in removed_comments])

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
        cursor_user.execute("""
                            SELECT xc.id, cx.xstation_id, cx.password, cx.verification, xc.is_active, xc.master_id_id, cx.user_id_id, xc.allocated_balance, xc.forex_multiplier, xc.is_paused, xc.copy_prev FROM users_xstation_connection as xc JOIN users_credentials_xstation as cx ON xc.xstation_table_id_id = cx.id 
                            WHERE cx.verification = TRUE AND xc.is_active = TRUE AND xc.master_id_id IS NOT NULL AND xc.is_paused = FALSE
                            """)
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


def get_balance_user(user_client):
    user_balance = user_client.commandExecute("getMarginLevel")['returnData']['balance']
    
    return user_balance

def get_balance_master(master_id, masters):
    master_balance = masters[master_id][0].commandExecute("getMarginLevel")['returnData']['balance']
    
    return master_balance

def create_trades_made_table():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades_made (
            id SERIAL PRIMARY KEY,
            datetime TIMESTAMP NOT NULL,
            userid VARCHAR(255) NOT NULL,
            masterid VARCHAR(255) NOT NULL,
            symbol VARCHAR(255) NOT NULL,
            volume NUMERIC(10, 2) NOT NULL,
            success BOOLEAN NOT NULL
        );
    """)
    conn.commit()

def make_trade(user_client, inserted_rows_data, userId, master_id, master_balances, allocated_amount, forex_multiplier, product_dic):   
    try:
        if any(row['is_stock'] for row in inserted_rows_data):
            user_balance = allocated_amount if allocated_amount else get_balance_user(user_client)
            master_balance = master_balances[master_id]
        
        for inserted_row_data in inserted_rows_data: 
            if not inserted_row_data['is_stock'] or inserted_row_data['category'] in ("FX", "CMD"):
                V = forex_multiplier if forex_multiplier else 1
            else:
                V = user_balance / master_balance
                
            
            if round((inserted_row_data['volume'] * V), 2) <= 0:
                return
            
            if inserted_row_data['master_id'] == master_id:
                volume = min(round((inserted_row_data['volume'] * V), 2), 100)
                comment = product_dic[master_id] + ' ' + str(inserted_row_data['order'])
                args = {
                        "tradeTransInfo": {
                            "cmd": inserted_row_data['cmd'],
                            "comment": comment,
                            "expiration": 0,
                            "price": inserted_row_data['open_price'],
                            "sl": inserted_row_data['sl'],
                            "tp": inserted_row_data['tp'],
                            "symbol": inserted_row_data['symbol'],
                            "type": 0,
                            "volume": volume
                    }
                }
                
                response = user_client.commandExecute("tradeTransaction", args)
                
                status = False
                if response['status'] == True:
                    print("Trade successfully executed.")
                    status = True
                elif response['errorCode'] == 'BE127':
                    print('Value of Trade too low')
                else:
                    print("Trade execution failed. Error code:", response['errorCode'])
                    send_slack_message(f"Trade failed for userId: {userId}, Error code: {response['errorCode']}, data : {inserted_rows_data}")
                
                current_time = time.strftime('%Y-%m-%d %H:%M:%S')
                sql = """INSERT INTO trades_made (datetime, userid, masterid, symbol, volume, success) VALUES (%s, %s, %s, %s, %s, %s)"""
                values = (current_time, userId, master_id, inserted_row_data['symbol'], volume, status)
                cursor.execute(sql, values)
                conn.commit()
                
                time.sleep(2)
    
    except Exception as e:
        script_logger.error(f"Error in Make Trade: {e} for userId: {userId}, data : {inserted_rows_data}")
        send_slack_message(f"Error in Make Trade: {e} for userId: {userId}, data : {inserted_rows_data}")


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


def close_trade(user_client, removed_comments, userId, master_id, product_dic):    
    try:
        for removed_comment in removed_comments:
            if removed_comment[1]:
                comment = product_dic[master_id] + ' ' + str(removed_comment[0])
                trade_by_comment = get_order_by_comment(user_client, comment)

                while trade_by_comment is not None:
                    args = {
                        "tradeTransInfo": {
                            "type": 2,
                            "order": int(trade_by_comment['order']),
                            "symbol": trade_by_comment['symbol'],
                            "price": trade_by_comment['close_price'],
                            "volume": float(trade_by_comment['volume'])
                        }
                    }
                    
                    data = user_client.commandExecute("tradeTransaction", args)['returnData']
                    
                    time.sleep(2)
                    
                    order_response = data['order']
                    
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
                        
                    trade_by_comment = get_order_by_comment(user_client, comment)
        
    except Exception as e:
        script_logger.error(f"Error in close trade: {e} for userId: {userId}, data: {removed_comments}")
        send_slack_message(f"Error in close trade: {e} for userId: {userId}, data: {removed_comments}")


def update_verification(xstation_id, verification_status):
    try:
        cursor_user.execute(f"UPDATE users_credentials_xstation SET verification = {verification_status} WHERE xstation_id = {xstation_id}")
        conn_user.commit()
    except (Exception, psycopg2.Error) as error:
        print("Error while updating verification status:", error)


def user_trading(user, inserted_rows_data, removed_comments, masters, master_balances, product_dic):
    user_client = None
    try:
        user_client = APIClient()
        loginResponse = user_client.execute(loginCommand(userId=user[1], password=decrypt(user[2])))
        master_id = user[5]                 
                  
        if loginResponse['status']:  
            if inserted_rows_data:
                make_trade(user_client, inserted_rows_data, user[1], master_id, master_balances, user[7], user[8], product_dic)
            
            if removed_comments:
                close_trade(user_client, removed_comments, user[1], master_id, product_dic) 
        
        else:
            print("Failed: ", user[1])
            update_verification(user[1], False)    
                    
    except Exception as e:
        script_logger.error(f"Error: {e} for user {user[1]}, password {user[2]}, decrypted {decrypt(user[2])}")
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
    

def update_master_verification(xstation_id, verification_status):
    try:
        print("xstation_id: ", xstation_id)
        cursor_user.execute(f"UPDATE users_credentials_master_xstation SET verification = {verification_status} WHERE xstation_id = {xstation_id}")
        conn_user.commit()
    except (Exception, psycopg2.Error) as error:
        print("Error while updating verification status:", error)


def load_masters():
    try:
        cursor_user.execute("""
            SELECT u.id, u.xstation_id, u.password, u.verification, u.min_deposit, u.account_type_stock, u.stripe_product_id_id, user_id_id
            FROM users_credentials_master_xstation AS u
            JOIN products_product AS p ON u.stripe_product_id_id = p.stripe_product_id
            WHERE u.verification = TRUE AND is_active = TRUE;
        """)
        
        rows = cursor_user.fetchall()
        
    except (Exception, psycopg2.Error) as error:
        print("Error while fetching data from users_credentials_master_xstation table:", error)
        return []
    
    masters = {}
    for row in rows:
        if row[3]:
            master_client = APIClient()
            loginResponse = master_client.execute(loginCommand(userId=row[1], password=decrypt(row[2])))
            
            if loginResponse['status']:    
                masters[row[0]] = (master_client, row[5])
            else: 
                update_master_verification(row[1])
                
                if row[0] in masters.keys():
                    masters.pop(row[0])
                    
                master_client.disconnect() 

    return masters

def disconnect_masters(masters):
    keys = list(masters.keys())
    for master in keys:
        masters[master][0].disconnect()
        masters.pop(master)
        
    return masters

def send_check():
    url = os.environ.get('API_URL') + 'check-api-call'
    response = requests.get(url)

def update_copy_prev(connection_id, copy_prev):
    try:
        query = "UPDATE users_xstation_connection SET copy_prev = %s WHERE id = %s"
        cursor_user.execute(query, (copy_prev, connection_id))
    except (Exception, psycopg2.Error) as error:
        print("Error while updating verification status:", error)


def copy_all_make_trade(user_client, trades_data, V, master_id, forex_multiplier):
    for trade in trades_data:
        try:
            if round((trade['volume'] * V), 2) <= 0:
                    return
            
            category = get_symbol_cateogry(user_client, trade['symbol'])
            
            if category in ("FX", "CMD"):
                Vx = forex_multiplier if forex_multiplier else 1    
            else:    
                Vx = V
            
            args = {
                "tradeTransInfo": {
                "cmd": trade['cmd'],
                "comment": master_id + ' ' + str(trade['order']),
                "expiration": 0,
                "price": trade['open_price'],
                "sl": trade['sl'],
                "tp": trade['tp'],
                "symbol": trade['symbol'],
                "type": 0,
                "volume": round((trade['volume'] * Vx), 2)
                }
            }
                    
            response = user_client.commandExecute("tradeTransaction", args)
                
            if response['status'] == True:
                print("Trade successfully executed.")
            elif response['errorCode'] == 'BE127':
                print('Value of Trade too low')
            else:
                print("Trade execution failed. Error code:", response['errorCode'])
                send_slack_message(f"Trade failed Error code: {response['errorCode']}, data : {trade}")
                
            time.sleep(1)
    
        except Exception as e:
            script_logger.error(f"Error in Copy new Make Trade: {e} data : {trade}")
            send_slack_message(f"Error in Copy new Make Trade: {e} data : {trade}")
        

def copy_all_to_users(users, masters, master_balances):
    for user in users:
        connection_id = user[0]
        copy_prev = user[10]
        master_id = user[5]
        allocated_amount = user[7]
        forex_multiplier = user[8]
        
        if copy_prev:
            try:
                user_client = APIClient()
                loginResponse = user_client.execute(loginCommand(userId=user[1], password=decrypt(user[2])))
                
                if masters[master_id][1]:
                    master_balance = master_balances[user[5]]
                    user_balance = allocated_amount if allocated_amount else get_balance_user(user_client)
                    V = user_balance / master_balance       
                else:
                    V = forex_multiplier
                
                trades_data = get_trades(masters[master_id][0])
                copy_all_make_trade(user_client, trades_data, V, master_id, forex_multiplier)
            except:
                pass
        
            update_copy_prev(connection_id, False)
        
def copy_products_dict():
    try:
        cursor_user.execute("""
            SELECT uc.id, pp.name
            FROM users_credentials_master_xstation AS uc
            JOIN products_product AS pp ON uc.stripe_product_id_id = pp.stripe_product_id
            WHERE pp.is_copy_trading = TRUE
            AND pp.is_active = TRUE
            AND pp.show = TRUE;
        """)
        rows = cursor_user.fetchall()
        
        dic = {}
        for row in rows:
            dic[row[0]] = row[0].replace(' ', '_')
        
        return dic
    except:
        pass

def main():
    
    # Reset trades table
    # drop_tables(['open_trades', 'past_trades'])
    # create_trade_tables()
    # create_trades_made_table()
    
    counter = 0
    masters = load_masters()

    while True:
        try:
            send_check()
            
            if masters:
                inserted_rows_data, removed_comments = [], []
                master_keys = list(masters.keys())
                
                for key in master_keys:
                    trades_data = get_trades(masters[key][0])
                    inserted_rows_data_tmp, removed_comments_tmp = insert_data_trades_table(trades_data, key, masters[key][1], masters[key][0])
                    inserted_rows_data.extend(inserted_rows_data_tmp)
                    removed_comments.extend(removed_comments_tmp)
                
                users = get_all_users()
                
                master_balances = {}
                for master_key in master_keys:
                    master_balances[master_key] = get_balance_user(masters[master_key][0])
 
                if users:    
                    copy_all_to_users(users, masters, master_balances)

                
                if users and (inserted_rows_data or removed_comments):
                    product_dict = copy_products_dict()
                    
                    with ThreadPoolExecutor(max_workers=len(users)) as executor:
                        for user in users:
                            executor.submit(user_trading, user, inserted_rows_data, removed_comments, masters, master_balances, product_dict)
                
            time.sleep(5)
        
            counter += 1  
            if counter % 60 == 0:
                masters = disconnect_masters(masters)
                masters = load_masters() 
    
        except Exception as e:
            script_logger.error("Error: ", e)
            send_slack_message(e)
            
    
if __name__ == '__main__':
    main()                
