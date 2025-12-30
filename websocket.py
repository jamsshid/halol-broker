import websocket
import json

def on_message(ws, message):
    data = json.loads(message)
    bid = float(data['b'])
    ask = float(data['a'])
    mid = (bid + ask) / 2
    print("BTC price:", mid)

ws = websocket.WebSocketApp(
    "wss://stream.binance.com:9443/ws/btcusdt@bookTicker",
    on_message=on_message
)

ws.run_forever()
