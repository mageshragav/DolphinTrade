# from mitmproxy import http, websocket

# def websocket_message(flow: http.HTTPFlow):
#     # Check if the message is a WebSocket message
#     if isinstance(flow.messages[-1], websocket.WebSocketMessage):
#         ws_message = flow.messages[-1]
#         url = flow.request.url
#         request_headers = flow.request.headers

#         # Extract WebSocket URL and request headers
#         print("WebSocket URL:", url)
#         print("Request Headers:")
#         for header, value in request_headers.items():
#             print(f"{header}: {value}")
#         print("\n")

# def request(flow: http.HTTPFlow):
#     # Enable WebSocket interception for all requests
#     flow.intercept()
# import mitmproxy.http

# def websocket_message(flow: mitmproxy.http.HTTPFlow):
#     if flow.websocket:
#         print(flow.websocket.messages)
from mitmproxy import http

# Dictionary to store WebSocket URLs and request headers
websocket_data = {}

def request(flow: http.HTTPFlow):
    # Check if the request is a WebSocket upgrade request (wss://)
    if flow.request.scheme == "wss":
        url = flow.request.pretty_url
        request_headers = flow.request.headers
        websocket_data[url] = request_headers

def response(flow: http.HTTPFlow):
    # Check if the response is a WebSocket upgrade response (101 status code)
    if flow.response.status_code == 101:
        url = flow.request.pretty_url
        request_headers = websocket_data.get(url, {})
        response_headers = flow.response.headers
        print("WebSocket URL:", url)
        print("Request Headers:")
        for header, value in request_headers.items():
            print(f"{header}: {value}")
        print("Response Headers:")
        for header, value in response_headers.items():
            print(f"{header}: {value}")
        print("\n")