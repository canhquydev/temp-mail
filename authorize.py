from google_auth_oauthlib.flow import InstalledAppFlow
import json

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def main():
    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json', SCOPES)
    creds = flow.run_local_server(port=5000)
    
    # Lưu token
    with open('token.json', 'w') as token_file:
        token_file.write(creds.to_json())

if __name__ == '__main__':
    main()
