from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode
import requests
import json
import os

CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI = "https://libraries-tub-bruce-capable.trycloudflare.com/callback"
SCOPES = "https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send"

class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path == "/":
            # Generate auth URL
            params = {
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "response_type": "code",
                "scope": SCOPES,
                "access_type": "offline",
                "prompt": "consent"
            }
            auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
            
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            html = f"""
            <h1>Google OAuth Setup</h1>
            <p><a href="{auth_url}" target="_blank">Clicca qui per autorizzare</a></p>
            <p>Oppure copia questo URL:</p>
            <textarea style="width:100%;height:100px">{auth_url}</textarea>
            """
            self.wfile.write(html.encode())
            
        elif parsed.path == "/callback":
            # Handle callback
            params = parse_qs(parsed.query)
            code = params.get("code", [None])[0]
            
            if code:
                # Exchange code for tokens
                token_url = "https://oauth2.googleapis.com/token"
                data = {
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": REDIRECT_URI
                }
                response = requests.post(token_url, data=data)
                tokens = response.json()
                
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                
                if "refresh_token" in tokens:
                    refresh_token = tokens["refresh_token"]
                    html = f"""
                    <h1>Successo!</h1>
                    <h2>Refresh Token:</h2>
                    <textarea style="width:100%;height:150px">{refresh_token}</textarea>
                    <p>Copia questo token e aggiungilo al file .env</p>
                    <pre>{json.dumps(tokens, indent=2)}</pre>
                    """
                    # Save to file
                    with open("/root/ai-agents/refresh_token.txt", "w") as f:
                        f.write(refresh_token)
                    print(f"\n\n=== REFRESH TOKEN ===\n{refresh_token}\n=====================\n")
                else:
                    html = f"<h1>Errore</h1><pre>{json.dumps(tokens, indent=2)}</pre>"
                
                self.wfile.write(html.encode())
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing code")

print("=" * 50)
print("Server OAuth in ascolto su porta 9999")
print("=" * 50)
print(f"\n1. Vai su: http://srv938822.hstgr.cloud:9999/")
print("\n2. IMPORTANTE: Aggiungi questo redirect URI nella Google Cloud Console:")
print(f"   {REDIRECT_URI}")
print("\n3. Clicca il link e autorizza")
print("=" * 50)

HTTPServer(("0.0.0.0", 9999), OAuthHandler).serve_forever()
