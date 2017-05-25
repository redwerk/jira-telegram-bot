## Telegram bot for integration with JIRA

### Technologies
- Python 3.5
- MongoDB
- PyMongo
- [jira](https://github.com/pycontribs/jira)
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)


### Deployment
1. Clone a repository: `git clone https://git.redwerk.com/redwerk/jira-telegram-bot.git`

2. Navigate into *jira-telegram-bot* folder

3. Create a virtualenv: `python3.5 -m venv .venv`

4. Install requirements: `pip install -r requirements.txt`

5. Install and setting up MongoDB (create DB and collection).

6. Create **.env** text file with following data:
```
BOT_TOKEN = <string.
SECRET_KEY = <string> # from cryptography.fernet import Fernet; Fernet.generate_key()
JIRA_HOST = <string>

DB_HOST = <string>
DB_PORT = <integer>
DB_NAME = <string>
DB_COLLECTION = <string>
```
