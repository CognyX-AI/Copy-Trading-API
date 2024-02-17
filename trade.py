from xAPIConnector import APIClient, loginCommand 
import os
from dotenv import load_dotenv
import time
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
            order INTEGER,
            symbol VARCHAR(50),
            volume FLOAT,
            open_price FLOAT,
            open_time TIMESTAMP,
            close_time TIMESTAMP
            SL FLOAT,
            TP FLOAT,
        )
        '''
        cursor.execute(create_table_query)    
        
        create_table_query = '''
        CREATE TABLE IF NOT EXISTS past_trades (
            id SERIAL PRIMARY KEY,
            cmd INTEGER,
            order INTEGER,
            symbol VARCHAR(50),
            volume FLOAT,
            open_price FLOAT,
            open_time TIMESTAMP,
            close_time TIMESTAMP
            SL FLOAT,
            TP FLOAT,
        )
        '''
        cursor.execute(create_table_query)    


        conn.commit()
        print("Table created successfully!")

    except (Exception, psycopg2.Error) as error:
        print("Error while connecting to PostgreSQL:", error)


def insert_data_trades_table(trades_data):   
    inserted_rows_data = {}
    removed_comments = []
    
    try:
        trades = trades_data.get('trades', {})
    except Exception as error:
        print("Error while connecting to PostgreSQL:", error)
        
    return inserted_rows_data, removed_comments


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


def make_trade(client):    
    args = {
            "tradeTransInfo": {
                "cmd": 0,
                "comment": "Some text 2",
                "expiration": 0,
                "price": 1.4,
                "sl": 0,
                "tp": 0,
                "symbol": "GBPUSD",
                "type": 0,
                "volume": 0.1
            }
    }
    
    response = client.commandExecute("tradeTransaction", args)
    if response['status']:
        print("Trade successfully executed.")
    else:
        print("Trade execution failed. Error code:", response['errorCode'])


def get_client(userId, password):    
    client = APIClient()
    
    loginResponse = client.execute(loginCommand(userId=userId, password=password))
    
    if not loginResponse['status']:
        print('Login failed. Error code: {0}'.format(loginResponse['errorCode']))
        

def get_order_by_comment(trades, comment):
    for trade in trades:
        if trade['comment'] == comment:
            return trade['order']
    return None


def get_trades(client):
    args =  {
		"openedOnly": True,
	}
    
    response = client.commandExecute("getTrades", args)['returnData']
    
    return response
    #return get_order_by_comment(response, comment)


def close_trade(client, order_number):
    args = {
        "tradeTransInfo": {
            "type": 2,
            "order": order_number,
            "symbol": "GBPUSD",
            "price": 1.4,
            "volume": 0.1
        }
    }
    
    response = client.commandExecute("tradeTransaction", args)
    if response['status']:
        print("Trade successfully closed.")
    else:
        print("Failed to close trade. Error code:", response['errorCode'])


def main():
    master_userId = os.environ.get("MASTER_ID")
    master_password = os.environ.get("MASTER_PASSWORD")
    master_client = APIClient()
    loginResponse = master_client.execute(loginCommand(userId=master_userId, password=master_password))
    
    # while True:
    #     time.sleep(10)

    trades = get_trades(master_client)
    inserted_rows_data, removed_comments = insert_data_trades_table(trades)
    #make_trade(master_client)
    #close_trade(client, order) 
    
    
if __name__ == '__main__':
    main()
