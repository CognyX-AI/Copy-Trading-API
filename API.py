from flask import Flask, request, jsonify
from xAPIConnector import APIClient, loginCommand

app = Flask(__name__)

def check(user_id, password):
    client = APIClient()
    loginResponse = client.execute(loginCommand(userId=user_id, password=password))
    client.disconnect()
    return loginResponse['status']

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    user_id = data['user_id']
    password = data['password']
    status = check(user_id, password)
    return jsonify({'status': status})

if __name__ == '__main__':
    app.run(debug=True)
