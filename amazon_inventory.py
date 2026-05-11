import os
import time
import requests
from datetime import datetime
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

load_dotenv(override=False)

SELLER_EMAIL = os.getenv('SELLER_CENTRAL_EMAIL')
SELLER_PASSWORD = os.getenv('SELLER_CENTRAL_PASSWORD')
GOOGLE_SHEETS_ID = os.getenv('GOOGLE_SHEETS_ID')
CHATWORK_API_KEY = os.getenv('CHATWORK_API_KEY')
CHATWORK_ROOM_ID = os.getenv('CHATWORK_ROOM_ID')

# 必要な環境変数をチェック
required_vars = {
    'SELLER_CENTRAL_EMAIL': SELLER_EMAIL,
    'SELLER_CENTRAL_PASSWORD': SELLER_PASSWORD,
    'GOOGLE_SHEETS_ID': GOOGLE_SHEETS_ID,
    'CHATWORK_API_KEY': CHATWORK_API_KEY,
    'CHATWORK_ROOM_ID': CHATWORK_ROOM_ID,
}

missing_vars = [key for key, value in required_vars.items() if not value]
if missing_vars:
    print(f"❌ エラー: 以下の環境変数が設定されていません: {', '.join(missing_vars)}")
    print("💡 ローカル実行: .env ファイルを確認してください")
    print("☁️  リモート実行: 環境変数を設定してください")
    exit(1)

def login_seller_central():
    """Seller Central にログイン"""
    print("🔓 Seller Central ログイン中...")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)
    driver.get('https://sellercentral.amazon.co.jp/')

    try:
        email_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "ap_email"))
        )
        email_field.send_keys(SELLER_EMAIL)

        password_field = driver.find_element(By.ID, "ap_password")
        password_field.send_keys(SELLER_PASSWORD)

        login_button = driver.find_element(By.ID, "signInSubmit")
        login_button.click()

        time.sleep(3)
        print("✅ ログイン成功")
        return driver
    except Exception as e:
        print(f"❌ ログイン失敗: {e}")
        driver.quit()
        return None

def download_inventory_report(driver):
    """在庫レポートをダウンロード"""
    print("📥 在庫レポート取得中...")

    try:
        driver.get('https://sellercentral.amazon.co.jp/reports/report.html?report_type=FBA_INVENTORY_PLANNING_REPORT')
        time.sleep(2)

        download_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'ダウンロード')]"))
        )
        download_button.click()

        time.sleep(3)
        print("✅ レポート取得成功")
        return True
    except Exception as e:
        print(f"❌ レポート取得失敗: {e}")
        return False

def get_latest_csv(download_dir):
    """最新のダウンロードファイルを取得"""
    files = [f for f in os.listdir(download_dir) if f.endswith('.csv')]
    if files:
        latest_file = max(files, key=lambda x: os.path.getctime(os.path.join(download_dir, x)))
        return os.path.join(download_dir, latest_file)
    return None

def update_google_sheets(inventory_data):
    """Google Sheets に在庫データを記載"""
    print("📝 Google Sheets 更新中...")

    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

    try:
        creds = None
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)

            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()

        updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for idx, item in enumerate(inventory_data[:20], start=2):
            values = [[
                item.get('SKU', ''),
                item.get('ASIN', ''),
                item.get('在庫', ''),
                updated_at
            ]]

            range_name = f'Sheet1!E{idx}:H{idx}'
            body = {'values': values}
            sheet.values().update(
                spreadsheetId=GOOGLE_SHEETS_ID,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()

        print("✅ Google Sheets 更新完了")
        return True
    except Exception as e:
        print(f"❌ Google Sheets エラー: {e}")
        return False

def notify_chatwork(message):
    """Chatwork に通知"""
    url = f'https://api.chatwork.com/v2/rooms/{CHATWORK_ROOM_ID}/messages'
    headers = {'X-ChatworkToken': CHATWORK_API_KEY}
    data = {'body': message}

    response = requests.post(url, headers=headers, data=data)
    return response.status_code == 200

def main():
    print("=" * 40)
    print("=== Amazon 在庫自動取得開始 ===")
    print("=" * 40)

    updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    driver = login_seller_central()

    if not driver:
        notify_chatwork(f"❌ Seller Central ログイン失敗 ({updated_at})")
        return

    try:
        download_inventory_report(driver)

        download_dir = os.path.expanduser('~\\Downloads')
        csv_file = get_latest_csv(download_dir)

        if csv_file:
            inventory_data = []
            import csv
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    inventory_data.append(row)

            update_google_sheets(inventory_data)

            message = f"""
[toall] 🔔 Amazon 在庫更新完了

更新時刻: {updated_at}
更新件数: {len(inventory_data)}

詳細はスプレッドシートをご確認ください。
            """.strip()

            if notify_chatwork(message):
                print("✅ Chatwork 通知完了")
        else:
            print("❌ CSV ファイルが見つかりません")
            notify_chatwork(f"⚠️ CSV ダウンロード失敗 ({updated_at})")

    except Exception as e:
        print(f"❌ エラー: {e}")
        notify_chatwork(f"❌ エラーが発生しました: {str(e)}")

    finally:
        driver.quit()
        print("=" * 40)
        print("処理完了")
        print("=" * 40)

if __name__ == '__main__':
    main()
