import os
import requests
from flask import Flask, request, redirect, render_template_string
from urllib.parse import urlencode

app = Flask(__name__)

# Your Intuit creds (set in Render env vars)
CLIENT_ID = os.getenv('QBO_CLIENT_ID')
CLIENT_SECRET = os.getenv('QBO_CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI', 'https://grok-qbo-integration.onrender.com/callback')
BASE_URL = 'https://appcenter.intuit.com/connect'

@app.route('/')
def home():
    return "Grok-QuickBooks Integration Server is Running! Visit /auth to test."

@app.route('/auth')
def auth():
    params = {
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': 'com.intuit.quickbooks.accounting',
        'state': 'test_state'
    }
    auth_url = f"{BASE_URL}/oauth2?{urlencode(params)}"
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    realm_id = request.args.get('realmId')
    if code and CLIENT_ID and CLIENT_SECRET and realm_id:
        token_data = {
            'grant_type': 'authorization_code',
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'redirect_uri': REDIRECT_URI,
            'code': code
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        response = requests.post(f"{BASE_URL}/oauth2/token", data=token_data, headers=headers, auth=(CLIENT_ID, CLIENT_SECRET))
        if response.status_code == 200:
            try:
                tokens = response.json()
                access_token = tokens.get('access_token')
                pl_data = fetch_profit_loss(access_token, realm_id)
                if 'error' not in pl_data:
                    xai_api_key = os.getenv('XAI_API_KEY')
                    advice = analyze_with_grok(pl_data['data'], xai_api_key) if xai_api_key else "No xAI key set"
                    return render_template_string(LAUNCH_HTML, token=access_token, net_income=pl_data['net_income'], advice=advice)
                else:
                    return f"Error fetching data: {pl_data['error']}", 500
            except requests.exceptions.JSONDecodeError:
                return f"JSONDecodeError: Status {response.status_code}, Response: {response.text}", 500
        else:
            return f"Token request failed: Status {response.status_code}, Response: {response.text}", response.status_code
    return "Auth failed—no code or creds."

@app.route('/prompt', methods=['GET', 'POST'])
def prompt():
    if request.method == 'POST':
        user_prompt = request.form.get('prompt')
        xai_api_key = os.getenv('XAI_API_KEY')
        if user_prompt and xai_api_key:
            # Simulate using latest fetched data (in prod, store in DB)
            sample_data = {'Report': {'Header': {'NetIncome': '5000'}, 'Rows': {'Row': [{'ColData': [{'value': 'Sales'}, {'value': '10000'}]}]}}}
            advice = analyze_with_grok(sample_data, xai_api_key, user_prompt)
            return render_template_string(PROMPT_HTML, advice=advice, prompt=user_prompt)
        return "Missing prompt or xAI key."
    return render_template_string(PROMPT_HTML, advice="", prompt="")

@app.route('/launch')
def launch():
    return render_template_string(LAUNCH_HTML, token="hidden", net_income="N/A", advice="Connect via /auth to fetch data.")

@app.route('/disconnect')
def disconnect():
    return render_template_string(DISCONNECT_HTML)

def fetch_profit_loss(access_token, realm_id=None, start_date='2024-01-01', end_date='2024-12-31'):
    if not realm_id:
        realm_id = '9130352342769926'  # Your live QuickBooks company
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }
    params = {
        'start_date': start_date,
        'end_date': end_date
    }
    url = f'https://quickbooks.api.intuit.com/v3/company/{realm_id}/reports/ProfitAndLoss'
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        net_income = data.get('Report', {}).get('Header', {}).get('NetIncome', 'N/A')
        return {'net_income': net_income, 'data': data}
    else:
        return {'error': f"Status {response.status_code}: {response.text}"}

def analyze_with_grok(qbo_data, api_key, user_prompt=None):
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    prompt = user_prompt or f"Analyze this QuickBooks Profit & Loss data: {qbo_data}. Provide concise business advice: trends, risks, optimization tips."
    payload = {
        'model': 'grok-4',  # Or 'grok-3' for free tier
        'messages': [
            {'role': 'system', 'content': 'You are a business advisor.'},
            {'role': 'user', 'content': prompt}
        ],
        'max_tokens': 500
    }
    response = requests.post('https://api.x.ai/v1/chat/completions', headers=headers, json=payload)
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content']
    return f"Error: {response.text}"

# Static pages
LAUNCH_HTML = """
<!DOCTYPE html>
<html><body>
<h1>Success! Connected to QuickBooks.</h1>
<p>Access token received (hidden in prod).</p>
<p>Net Income (2024): {{ net_income }}</p>
<p>Grok's Business Advice: {{ advice }}</p>
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

PROMPT_HTML = """
<!DOCTYPE html>
<html><body>
<h1>Grok Business Advisor</h1>
<form method="post">
    <label>Enter your question:</label><br>
    <input type="text" name="prompt" value="{{ prompt }}" style="width: 300px;"><br>
    <input type="submit" value="Ask Grok">
</form>
<h2>Advice:</h2>
<p>{{ advice }}</p>
<a href="/auth">Reconnect</a> | <a href="/disconnect">Disconnect</a>
</body></html>
"""

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
