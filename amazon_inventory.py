import os
import sys
import csv
import time
import glob
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

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv(override=False)

TOOL4SELLER_EMAIL = os.getenv('SELLER_CENTRAL_EMAIL')
TOOL4SELLER_PASSWORD = os.getenv('SELLER_CENTRAL_PASSWORD')
GOOGLE_SHEETS_ID = os.getenv('GOOGLE_SHEETS_ID')
CHATWORK_API_KEY = os.getenv('CHATWORK_API_KEY')
CHATWORK_ROOM_ID = os.getenv('CHATWORK_ROOM_ID')

required_vars = {
    'SELLER_CENTRAL_EMAIL': TOOL4SELLER_EMAIL,
    'SELLER_CENTRAL_PASSWORD': TOOL4SELLER_PASSWORD,
    'GOOGLE_SHEETS_ID': GOOGLE_SHEETS_ID,
    'CHATWORK_API_KEY': CHATWORK_API_KEY,
    'CHATWORK_ROOM_ID': CHATWORK_ROOM_ID,
}

missing_vars = [key for key, value in required_vars.items() if not value]
if missing_vars:
    print(f"❌ エラー: 以下の環境変数が設定されていません: {', '.join(missing_vars)}")
    exit(1)

def login_tool4seller():
    """Tool4Seller にログイン"""
    print("🔓 Tool4Seller ログイン中...")

    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    driver = webdriver.Chrome(service=service, options=options)

    try:
        driver.get('https://data.tool4seller.com/sales_analysis/stock?currentTab=0')
        time.sleep(3)

        email_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "login-email"))
        )
        email_field.send_keys(TOOL4SELLER_EMAIL)
        time.sleep(1)

        password_field = driver.find_element(By.ID, "login-password")
        password_field.send_keys(TOOL4SELLER_PASSWORD)
        time.sleep(1)

        submit_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        submit_button.click()

        time.sleep(5)
        print("✅ ログイン成功")
        return driver
    except Exception as e:
        print(f"❌ ログイン失敗: {e}")
        driver.quit()
        return None

def export_store_data(driver, store_name):
    """指定した店舗のデータをエクスポート"""
    print(f"📤 {store_name} のデータをエクスポート中...")

    try:
        # FBA在庫管理をクリック（左サイドバー）
        fba_menu = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'FBA在庫管理')]"))
        )
        fba_menu.click()
        time.sleep(2)

        # Japan ドロップダウンをクリック
        japan_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Japan')]"))
        )
        japan_button.click()
        time.sleep(2)

        # 店舗を選択
        store_link = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, f"//text()[contains(., '{store_name}')]"))
        )
        store_link.click()
        time.sleep(3)

        # エクスポートボタン（ダウンロードアイコン）をクリック
        export_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//button[.//svg][@title='ダウンロード'] | //button[.//svg][contains(@class, 'download')]"))
        )
        export_button.click()
        print(f"✅ {store_name} のエクスポートリクエスト完了")
        time.sleep(2)

    except Exception as e:
        print(f"❌ {store_name} のエクスポート失敗: {e}")
        return False

    return True

def download_csv_files(driver):
    """ダウンロードセンターから CSV ファイルをダウンロード"""
    print("📥 ダウンロードセンターにアクセス中...")

    try:
        # ダウンロードセンターアイコン（左下のダウンロードアイコン）をクリック
        download_center = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//svg[contains(@class, 'feather-download')]/parent::*"))
        )
        download_center.click()
        time.sleep(3)

        # 2つのダウンロードボタンをクリック
        download_buttons = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, "//button[contains(text(), 'ダウンロード')]"))
        )

        for idx, button in enumerate(download_buttons[:2]):  # 最初の2つだけ
            try:
                button.click()
                print(f"✅ CSV {idx + 1} ダウンロード開始")
                time.sleep(2)
            except:
                pass

        time.sleep(3)
        print("✅ CSV ダウンロード完了")
        return True

    except Exception as e:
        print(f"❌ ダウンロード失敗: {e}")
        return False

def get_latest_csvs(download_dir, count=2):
    """最新のCSVファイルを取得"""
    files = sorted(
        glob.glob(os.path.join(download_dir, '*.csv')),
        key=os.path.getctime,
        reverse=True
    )[:count]
    return files

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

        for idx, item in enumerate(inventory_data[:50], start=2):
            values = [[
                item.get('SKU', '') or item.get('商品', ''),
                item.get('ASIN', ''),
                item.get('在庫', '') or item.get('FBA在庫', ''),
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

    driver = login_tool4seller()

    if not driver:
        notify_chatwork(f"❌ Tool4Seller ログイン失敗 ({updated_at})")
        return

    try:
        # 2つの店舗のデータをエクスポート
        export_store_data(driver, "relief10")
        time.sleep(5)
        export_store_data(driver, "ReLaravel 公式ストア")
        time.sleep(10)  # CSV 準備待ち

        # CSV をダウンロード
        download_csv_files(driver)

        # ダウンロードした CSV を読み込み
        download_dir = os.path.expanduser('~\\Downloads')
        csv_files = get_latest_csvs(download_dir, count=2)

        all_inventory_data = []
        for csv_file in csv_files:
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        all_inventory_data.append(row)
                print(f"✓ {csv_file} 読み込み完了")
            except Exception as e:
                print(f"✗ {csv_file} 読み込み失敗: {e}")

        if all_inventory_data:
            update_google_sheets(all_inventory_data)

            message = f"""
[toall] 🔔 Amazon 在庫更新完了

更新時刻: {updated_at}
更新件数: {len(all_inventory_data)}

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
