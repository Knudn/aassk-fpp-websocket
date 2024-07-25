import asyncio
import websockets
import json
import requests
from flask import Flask, request
from threading import Thread, Event

app = Flask(__name__)

# Global variables
websocket_thread = None
stop_event = Event()

# Existing functions
def enable_model_state():
    headers = {
        'Content-Type': 'application/json'
    }
    response = requests.request("GET", "http://localhost/api/overlays/model/LED Panels/state", headers=headers)
    if json.loads(response.text)["isActive"] == 0:
        payload = json.dumps({
            "State": 1,
        })
        response = requests.request("PUT", "http://localhost/api/overlays/model/LED Panels/state", headers=headers, data=payload)

def send_time_to_led_matrix(text):
    payload = json.dumps({
        "Message": str(text),
        "Position": "center",
        "Font": "Helvetica",
        "FontSize": 60,
        "AntiAlias": False,
        "PixelsPerSecond": 20,
        "Color": "#FFFFFF",
        "AutoEnable": True
        })
    headers = {
        'Content-Type': 'application/json'
    }
    requests.request("PUT", "http://localhost/api/overlays/model/LED Panels/text", headers=headers, data=payload)

def send_bid_display(text):
    payload = json.dumps({
        "Message": str(text),
        "Position": "center",
        "Font": "Helvetica",
        "FontSize": 35,
        "AntiAlias": False,
        "PixelsPerSecond": 20,
        "Color": "#FFFFFF",
        "AutoEnable": True
        })
    headers = {
        'Content-Type': 'application/json'
    }
    requests.request("PUT", "http://localhost/api/overlays/model/LED Panels/text", headers=headers, data=payload)

async def receive_data(websocket, track):
    print(track)
    connection_closed = False
    while not stop_event.is_set():
        try:

            data = await asyncio.wait_for(websocket.recv(), timeout=1.0)
            json_data = json.loads(data)
            if not connection_closed or (len(json_data["Driver"+str(track)]["time"]) <= 4):
                send_time_to_led_matrix("[" + json_data["Driver"+str(track)]["bid"] + "]" + "\n" + json_data["Driver"+str(track)]["time"])
            if len(json_data["Driver"+str(track)]["time"]) > 4:
                connection_closed = True
                send_time_to_led_matrix("[" + json_data["Driver"+str(track)]["bid"] + "]" + "\n" + json_data["Driver"+str(track)]["time"])
            else:
                connection_closed = False
        except asyncio.TimeoutError:
            continue
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket connection closed.")
            break

async def start_websocket(track):
    websocket_url = f"ws://192.168.20.218:4444/"
    while not stop_event.is_set():
        try:
            async with websockets.connect(websocket_url) as websocket:
                await receive_data(websocket, track)
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed, attempting to reconnect...")
            await asyncio.sleep(5)

def run_asyncio_coroutine(coroutine):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(coroutine)

@app.route('/driver_start')
def driver_start():
    global websocket_thread, stop_event
    track = request.args.get('track', default=1, type=int)

    if websocket_thread and websocket_thread.is_alive():
        return "WebSocket is already running", 400

    # Reset the stop event
    stop_event.clear()

    # Enable the model state
    enable_model_state()

    # Start the WebSocket connection in a separate thread
    websocket_thread = Thread(target=run_asyncio_coroutine, args=(start_websocket(track),))
    websocket_thread.start()

    return f"Driver started for track {track}"

@app.route('/stop')
def stop_websocket():
    global stop_event, websocket_thread

    if not websocket_thread or not websocket_thread.is_alive():
        return "No WebSocket is currently running", 400

    stop_event.set()
    websocket_thread.join(timeout=5)  # Wait for the thread to finish

    if websocket_thread.is_alive():
        return "Failed to stop the WebSocket thread", 500

    websocket_thread = None
    return "WebSocket stopped successfully"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
