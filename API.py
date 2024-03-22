from flask import Flask, request, jsonify
from xAPIConnector import APIClient, APIStreamClient, loginCommand
import time
import os
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import subprocess
from operator import itemgetter


app = Flask(__name__)
last_api_call_time = time.time()
load_dotenv()

def send_slack_message(message):
    slack_token = os.environ.get("SLACK_API_TOKEN")
    channel_id = os.environ.get("CHANNEL_ID")
        
    try:
        client = WebClient(token=slack_token)
        
        response = client.chat_postMessage(
            channel=channel_id,
            text=message
        )
    
    except SlackApiError as e:
        print(f"Slack API error: {e.response['error']}")

def check_api_call_time():
    global last_api_call_time
    current_time = time.time()
    if current_time - last_api_call_time > 600:
        send_slack_message("No API call made in the last 10 minutes.")
        last_api_call_time = current_time
        try:
            subprocess.run(["./restart_script.sh"])
            send_slack_message("Trading server restarted.")
        except Exception as e:
            send_slack_message(f"Server could not be restarted: {e}") 


def check_master(user_id, password):
    check_api_call_time()
    client = APIClient()
    loginResponse = client.execute(loginCommand(userId=user_id, password=password))
    client.disconnect()
    
    return loginResponse['status']

def check_user(user_id, password):
    check_api_call_time()
    client = APIClient()
    loginResponse = client.execute(loginCommand(userId=user_id, password=password))
    client.disconnect()
    
    return loginResponse['status']

def check_balance(user_id, password, min_deposit):
    check_api_call_time()
    client = APIClient()
    loginResponse = client.execute(loginCommand(userId=user_id, password=password))
    
    if loginResponse['status'] == False:
        client.disconnect()
        return False
    
    data = client.commandExecute("getMarginLevel")['returnData']
    
    client.disconnect()
    return data['margin_free'] > min_deposit


@app.route('/login-user', methods=['POST'])
def login_user():
    data = request.json
    user_id = data['user_id']
    password = data['password']
    status = check_user(user_id, password)
    return jsonify({'status': status}), 200

@app.route('/check-balance', methods=['POST'])
def balance():
    data = request.json
    user_id = data['user_id']
    password = data['password']
    min_deposit = data['min_deposit']
    status = check_balance(user_id, password, min_deposit)
    return jsonify({'status': status}), 200

@app.route('/login-master', methods=['POST'])
def login_master():
    data = request.json
    user_id = data['user_id']
    password = data['password']
    status = check_master(user_id, password)
    return jsonify({'status': status}), 200

@app.route('/get-balance', methods=['POST'])
def get_balance():
    data = request.json
    user_id = data['user_id']
    password = data['password']
    
    if not check_user(user_id, password):
        return jsonify({'status': "Wrong Credentials"}), 401

    client = APIClient()
    loginResponse = client.execute(loginCommand(userId=user_id, password=password))
    data = client.commandExecute("getMarginLevel")['returnData']
    args =  {
		"openedOnly": True,
	}
    data_open = client.commandExecute("getTrades", args)['returnData']
    client.disconnect()
    
    return jsonify({'balance': data['margin_free'], 'total_balance': data['balance'], 'open_trades' : len(data_open)}), 200
    
    
@app.route('/trade-history', methods=['POST'])
def get_trade_history():
    data = request.json
    user_id = data['user_id']
    password = data['password']
    
    if not check_user(user_id, password):
        return jsonify({'status': "Wrong Credentials"}), 401

    client = APIClient()
    loginResponse = client.execute(loginCommand(userId=user_id, password=password))
    current_timestamp = int(time.time() * 1000)  # Current timestamp in milliseconds
    args = {
        "end": current_timestamp,
        "start": 0
    }

    data_history = client.commandExecute("getTradesHistory", args)['returnData']
    args =  {
		"openedOnly": True,
	}
    
    data_open = client.commandExecute("getTrades", args)['returnData']
    data = data_open + data_history
    sorted_data = sorted(data, key=itemgetter('open_time'))  # Sort by open time
    client.disconnect()
    
    time_series = {}
    total_profit = 0
    total_trades = 0
    profit_trades = 0
    best_trade = None
    worst_trade = None
    
    for row in sorted_data:
        total_profit += row['profit']
        time_series[row['open_time']] = total_profit
        total_trades += 1
        profit_trades += 1 if row['profit'] > 0 else 0
        
        if best_trade is None or row['profit'] > best_trade:
            best_trade = row['profit']
            
        if worst_trade is None or row['profit'] < worst_trade:
            worst_trade = row['profit']
        
    return jsonify({
        'history': sorted_data,
        'time_series' : time_series,
        'total_trades' : total_trades,
        'profit_trades' : profit_trades,
        'profitability' : 1 if total_trades == 0 else profit_trades / total_trades,
        'avg_profit' : 0 if total_trades == 0 else total_profit / total_trades,
        'best_trade' : best_trade,
        'worst_trade' : worst_trade,
        'total_profit' : total_profit
        }), 200

@app.route('/closed-trades', methods=['POST'])
def get_closed_trades():
    data = request.json
    user_id = data['user_id']
    password = data['password']
    
    if not check_user(user_id, password):
        return jsonify({'status': "Wrong Credentials"}), 401

    client = APIClient()
    loginResponse = client.execute(loginCommand(userId=user_id, password=password))
    current_timestamp = int(time.time() * 1000)  #
    args = {
        "end": current_timestamp,
        "start": 0
    }

    data = client.commandExecute("getTradesHistory", args)['returnData']
    filtered_data = [trade for trade in data if trade.get('closed', False)]
    client.disconnect()
    
    return jsonify({'closed_trades': data}), 200

@app.route('/open-trades', methods=['POST'])
def get_open_trades():
    data = request.json
    user_id = data['user_id']
    password = data['password']
    
    if not check_user(user_id, password):
        return jsonify({'status': "Wrong Credentials"}), 401

    client = APIClient()
    loginResponse = client.execute(loginCommand(userId=user_id, password=password))
    args =  {
		"openedOnly": True,
	}
    
    data = client.commandExecute("getTrades", args)['returnData']
    
    return jsonify({'open_trades': data}), 200

@app.route('/profit', methods=['POST'])
def get_profit():
    data = request.json
    user_id = data['user_id']
    password = data['password']
    
    if not check_user(user_id, password):
        return jsonify({'status': "Wrong Credentials"}), 401
    
    client = APIClient()
    try:
        loginResponse = client.execute(loginCommand(userId=user_id, password=password))
        ssid = loginResponse['streamSessionId']

        data = {} 
        def pr(msg, data_dict):
            data_dict.update(msg)

        sclient = APIStreamClient(ssId=ssid, profitFun=lambda msg: pr(msg, data))
        try:
            sclient.subscribeProfits()
        except:
            pass
    except:
        pass
    
    sclient.disconnect()
    client.disconnect()
    
    return jsonify({'profit': data['data']['profit']}), 200

@app.route('/close-trade', methods=['POST'])
def close_trade():
    data = request.json
    user_id = data['user_id']
    password = data['password']
    order = data['order']

    client = APIClient()
    loginResponse = client.execute(loginCommand(userId=user_id, password=password))

    args =  {
        "openedOnly": True,
    }
        
    trades = client.commandExecute("getTrades", args)['returnData']
    main_trade = None

    for trade in trades:
        if trade['order'] == order:
            main_trade = trade

    if main_trade is None:
        return jsonify({'message':"Trade could not be found."}), 400

    args = {
        "tradeTransInfo": {
            "type": 2,
            "order": int(main_trade['order']),
            "symbol": main_trade['symbol'],
            "price": main_trade['close_price'],
            "volume": float(main_trade['volume'])
        }
    }
                    
    try:            
        data = client.commandExecute("tradeTransaction", args)['returnData']
    except:
        return jsonify({'message':"Markets are closed"}), 400
                    
    time.sleep(1)
                    
    order_response = data['order']
                    
    args =  {
        "order": order_response,
    }
            
    response = client.commandExecute("tradeTransactionStatus", args)['returnData']
    client.disconnect()       
                    
    if response["requestStatus"] in [0, 3]: 
        return jsonify({'message':"Trade successfully closed."}), 200
    else:
        return jsonify({'message':"Trade could not be closed."}), 500
    

@app.route('/check-api-call', methods=['GET'])
def check_api_call_route():
    check_api_call_time()
    global last_api_call_time
    last_api_call_time = time.time()
    return jsonify({'message': 'Check completed'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
