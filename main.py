import os
import requests
from flask import Flask, request, redirect, render_template_string
from urllib.parse import urlencode

app = Flask(__name__)

# Your Intuit creds (set as env vars in Render later)
CLIENT_ID = os.getenv('QBO_CLIENT_ID')
CLIENT_SECRET = os.getenv('QBO_CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI', 'https://your-app-name.onrender.com/callback')  # Render will set this
BASE_URL = 'https://appcenter.intuit.com/connect'

@app.route('/')
def home():
    return "Grok-QBO Integration Server is Running! Visit /auth to test."

@app.route('/auth')
def auth():
    params = {
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': 'com.intuit.quickbooks.accounting',
        'state': 'test_state'
    }
    auth_url = f"{BASE_URL}/v1/authorize?{urlencode(params)}"
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if code and CLIENT_ID and CLIENT_SECRET:
        token_data = {
            'grant_type': 'authorization_code',
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'redirect_uri': REDIRECT_URI,
            'code': code
        }
        response = requests.post(f"{BASE_URL}/oauth2/token", data=token_data)
        if response.status_code == 200:
            tokens = response.json()
            return render_template_string(LAUNCH_HTML, token=tokens.get('access_token', 'received'))
        else:
            return f"Error: {response.text}", 500
    return "Auth failed—no code or creds."

# Simple static pages
LAUNCH_HTML = """
<!DOCTYPE html>
<html><body>
<h1>Success! Connected to QuickBooks.</h1>
<p>Access token received (hidden in prod).</p>
<a href="/auth">Test Again</a> | <a href="/disconnect">Disconnect</a>
</body></html>
"""

DISCONNECT_HTML = """
<!DOCTYPE html>
<html><body>
<h1>Disconnected from QuickBooks.</h1>
<p>Thanks for using Grok Business Advisor!</p>
<a href="/auth">Reconnect</a>
</body></html>
"""

@app.route('/launch')
def launch():
    return render_template_string(LAUNCH_HTML)

@app.route('/disconnect')
def disconnect():
    return render_template_string(DISCONNECT_HTML)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))  # Render uses PORT env var
    app.run(host='0.0.0.0', port=port, debug=True)
