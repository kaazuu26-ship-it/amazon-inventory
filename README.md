# Amazon Inventory Automation

Automated system to retrieve Amazon inventory data daily and update Google Sheets with notifications via Chatwork.

## Features

- Daily automated Amazon Seller Central login and inventory report retrieval
- Automatic Google Sheets update with inventory data
- Chatwork notifications for job completion or errors
- Selenium-based browser automation for reliable data collection

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/kaazuu26-ship-it/amazon-inventory.git
cd amazon-inventory
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy `.env.example` to `.env` and fill in your values:
```bash
cp .env.example .env
```

Edit `.env` with your actual credentials:
- **Amazon Seller Central**: Email and password for your seller account
- **Google Sheets**: Your Google Sheets ID and OAuth credentials
- **Chatwork**: API key and room ID for notifications

### 4. Set up Google OAuth credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google Sheets API
4. Create OAuth 2.0 Desktop Application credentials
5. Download as `credentials.json` and save to this directory

On first run, the script will prompt you to authorize the application via browser.

### 5. Run the script

```bash
python amazon_inventory.py
```

## Scheduling with Claude Code

To schedule daily execution at 9 AM Japan time using Claude Code:

```
/schedule daily-amazon-inventory 9am Asia/Tokyo "python amazon_inventory.py"
```

## Notes

- The script uses Selenium for Amazon Seller Central automation
- Google OAuth token is cached in `token.json` for subsequent runs
- Never commit `.env` or `credentials.json` files (they're in `.gitignore`)
- Chatwork notifications show job status and item count updated