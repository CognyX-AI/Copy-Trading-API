from xAPIConnector import APIClient, loginCommand 

def make_trade(client):
    args = {
            "tradeTransInfo": {
                "cmd": 0,
                "comment": "Some text 2",
                "expiration": 0,
                # "order": 0,
                "price": 1.4,
                # "sl": 0,
                # "tp": 0,
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


def get_trades(client, comment):
    args =  {
		"openedOnly": True,
	}
    
    response = client.commandExecute("getTrades", args)['returnData']
    
    return get_order_by_comment(response, comment)


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
    userId = 15767323
    password = "Password123"
    
    client = APIClient()
    
    loginResponse = client.execute(loginCommand(userId=userId, password=password))

    #make_trade(client)
    #order = get_trades(client, "Some text 2")
    #close_trade(client, order) 
    
    
if __name__ == '__main__':
    main()
