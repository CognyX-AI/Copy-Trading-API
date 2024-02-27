from flask import Flask, request, jsonify
from xAPIConnector import APIClient, loginCommand

app = Flask(__name__)

def check_master(user_id, password):
    client = APIClient()
    loginResponse = client.execute(loginCommand(userId=user_id, password=password))
    client.disconnect()
    
    return loginResponse['status']

def check_user(user_id, password, min_deposit):
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
    min_deposit = data['min_deposit']
    status = check_user(user_id, password, min_deposit)
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
