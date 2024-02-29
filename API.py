from flask import Flask, request, jsonify
from xAPIConnector import APIClient, loginCommand
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
    current_timestamp = int(time.time() * 1000)  # Current timestamp in milliseconds
    args = {
        "end": current_timestamp,
        "start": 0
    }

    data = client.commandExecute("getTradesHistory", args)['returnData']
    filtered_data = [trade for trade in data if trade.get('closed', False)]
    client.disconnect()
    
    return jsonify({'history': data})

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
