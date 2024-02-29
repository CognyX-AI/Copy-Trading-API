from flask import Flask, request, jsonify
from xAPIConnector import APIClient, APIStreamClient, loginCommand
import time

app = Flask(__name__)

def check_master(user_id, password):
    client = APIClient()
    loginResponse = client.execute(loginCommand(userId=user_id, password=password))
    client.disconnect()
    
    return loginResponse['status']

def check_user(user_id, password):
    client = APIClient()
    loginResponse = client.execute(loginCommand(userId=user_id, password=password))
    client.disconnect()
    
    return loginResponse['status']

def check_balance(user_id, password, min_deposit):
    client = APIClient()
    loginResponse = client.execute(loginCommand(userId=user_id, password=password))
    
    if loginResponse['status'] == False:
        client.disconnect()
        return False
    
    data = client.commandExecute("getMarginLevel")['returnData']
    
    client.disconnect()
    return data['balance'] > min_deposit


@app.route('/login-user', methods=['POST'])
def login_user():
    data = request.json
    user_id = data['user_id']
    password = data['password']
    status = check_user(user_id, password)
    return jsonify({'status': status})

@app.route('/check-balance', methods=['POST'])
def balance():
    data = request.json
    user_id = data['user_id']
    password = data['password']
    min_deposit = data['min_deposit']
    status = check_balance(user_id, password, min_deposit)
    return jsonify({'status': status})

@app.route('/login-master', methods=['POST'])
def login_master():
    data = request.json
    user_id = data['user_id']
    password = data['password']
    status = check_master(user_id, password)
    return jsonify({'status': status})

@app.route('/get-balance', methods=['POST'])
def get_balance():
    data = request.json
    user_id = data['user_id']
    password = data['password']
    
    if not check_user(user_id, password):
        return jsonify({'status': "Wrong Credentials"})

    client = APIClient()
    loginResponse = client.execute(loginCommand(userId=user_id, password=password))
    data = client.commandExecute("getMarginLevel")['returnData']
    client.disconnect()
    
    return jsonify({'balance': data['balance']})
    
    
@app.route('/trade-history', methods=['POST'])
def get_trade_history():
    data = request.json
    user_id = data['user_id']
    password = data['password']
    
    if not check_user(user_id, password):
        return jsonify({'status': "Wrong Credentials"})

    client = APIClient()
    loginResponse = client.execute(loginCommand(userId=user_id, password=password))
    current_timestamp = int(time.time() * 1000)  # Current timestamp in milliseconds
    args = {
        "end": current_timestamp,
        "start": 0
    }

    data = client.commandExecute("getTradesHistory", args)['returnData']
    client.disconnect()
    
    return jsonify({'history': data})

@app.route('/closed-trades', methods=['POST'])
def get_closed_trades():
    data = request.json
    user_id = data['user_id']
    password = data['password']
    
    if not check_user(user_id, password):
        return jsonify({'status': "Wrong Credentials"})

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
    
    return jsonify({'closed_trades': data})

@app.route('/open-trades', methods=['POST'])
def get_open_trades():
    data = request.json
    user_id = data['user_id']
    password = data['password']
    
    if not check_user(user_id, password):
        return jsonify({'status': "Wrong Credentials"})

    client = APIClient()
    loginResponse = client.execute(loginCommand(userId=user_id, password=password))
    args =  {
		"openedOnly": True,
	}
    
    data = client.commandExecute("getTrades", args)['returnData']
    
    return jsonify({'open_trades': data})

@app.route('/profit', methods=['POST'])
def get_profit():
    data = request.json
    user_id = data['user_id']
    password = data['password']
    
    if not check_user(user_id, password):
        return jsonify({'status': "Wrong Credentials"})
    
    client = APIClient()
    loginResponse = client.execute(loginCommand(userId=user_id, password=password))
    ssid = loginResponse['streamSessionId']

    data = {} 
    def pr(msg, data_dict):
        data_dict.update(msg)

    sclient = APIStreamClient(ssId=ssid, profitFun=lambda msg: pr(msg, data))
    sclient.subscribeProfits()
    sclient.disconnect()
    client.disconnect()
    
    return jsonify({'profit': data['data']['profit']})

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
        return jsonify({'message':"Trade could not be found."})

    args = {
        "tradeTransInfo": {
            "type": 2,
            "order": int(main_trade['order']),
            "symbol": main_trade['symbol'],
            "price": main_trade['close_price'],
            "volume": float(main_trade['volume'])
        }
    }
                    
    data = client.commandExecute("tradeTransaction", args)['returnData']
                    
    time.sleep(1)
                    
    order_response = data['order']
                    
    args =  {
        "order": order_response,
    }
            
    response = client.commandExecute("tradeTransactionStatus", args)['returnData']
    client.disconnect()       
                    
    if response["requestStatus"] in [0, 3]: 
        return jsonify({'message':"Trade successfully closed."})
    else:
        return jsonify({'message':"Trade could not be closed."})
    

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
