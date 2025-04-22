# Boğaziçi University Announcements Telegram Bot

A Telegram bot that monitors and notifies users about new announcements from:
- Boğaziçi University Main Page (Ana Sayfa)
- YADYOK (School of Foreign Languages)
- MIS (Management Information Systems)

## Try the Bot

You can start using the bot right now by clicking here:  
👉 [https://t.me/BounAnnouncementsBot](https://t.me/BounAnnouncementsBot) 👈

## Features

- Real-time monitoring of university announcement pages
- Customizable subscriptions (subscribe/unsubscribe to specific announcement types)
- Latest announcements retrieval via `/latest` command
- Markdown-formatted notifications
- Persistent user preferences with SQLite database
- Error handling and automatic removal of inactive users

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot and subscribe to notifications |
| `/stop` | Unsubscribe from all notifications |
| `/status` | View current subscription status |
| `/latest` | Get the 5 most recent announcements |
| `/subscribe_main` | Subscribe to main page announcements |
| `/unsubscribe_main` | Unsubscribe from main page announcements |
| `/subscribe_yadyok` | Subscribe to YADYOK announcements |
| `/unsubscribe_yadyok` | Unsubscribe from YADYOK announcements |
| `/subscribe_mis` | Subscribe to MIS announcements |
| `/unsubscribe_mis` | Unsubscribe from MIS announcements |


## Technical Details

### Requirements
- Python 3.7+
- Required packages:
  - `python-telegram-bot==13.15`
  - `beautifulsoup4`
  - `requests`
  - `pandas`
  - `python-dotenv`
  - `urllib3`

### Database Schema
The bot uses SQLite with the following tables:
- `chat_ids`: Stores user subscriptions
- `main_announcements`: Stores main page announcements
- `yadyok_announcements`: Stores YADYOK announcements
- `mis_announcements`: Stores MIS announcements

### Scraping Logic
The bot periodically checks:
- https://bogazici.edu.tr/tr-TR/Content/Duyurular/Duyurular (Main Page)
- https://yadyok.bogazici.edu.tr/tr/duyurular (YADYOK)
- https://mis.bogazici.edu.tr/tr/latest-news (MIS)

### Notification System
- Checks for new announcements every hour
- Maintains order of announcements (newest first)
- Handles various Telegram API errors gracefully
- Automatically removes unauthorized users

