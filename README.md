## Telegram bot for integration with JIRA

### Technologies
- Python 3.6
- MongoDB
- PyMongo
- [jira](https://github.com/pycontribs/jira)
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)


### Deployment
1. Clone a repository: `git clone https://git.redwerk.com/redwerk/jira-telegram-bot.git`

2. Navigate into *jira-telegram-bot* folder

3. Create a virtualenv: `python3.6 -m venv .venv`

4. Install requirements: `pip install -r requirements.txt`

5. Install and setting up MongoDB (create DB and collection).

6. Create **.env** text file with following data:

```
BOT_TOKEN = <string>
SECRET_KEY = <string> # from cryptography.fernet import Fernet; Fernet.generate_key()

DB_HOST = <string>
DB_PORT = <string>

DB_USER = <string>
DB_PASS = <string>
DB_NAME = <string>

DB_USER_COLLECTION = <string>
DB_HOST_COLLECTION = <string>
DB_CACHE_COLLECTION = <string>

BOT_URL = https://t.me/<bot_name>
OAUTH_SERVICE_URL = http://url.to.flask.service

DOCS_PATH = /absolute/path/path/to/jira-telegram-bot/docs
PRIVATE_KEY_PATH = /absolute/path/jira_privatekey.pem
PUBLIC_KEY_PATH = /absolute/path/jira_publickey.pem

FEEDBACK_RECIPIENT = feedback@email.com
DEV_EMAILS = user1@email.com, user2@email.com
```

For further deployment see [/docs](docs) folder

### Running via Docker Compose

1. Set value `DB_HOST = mongo` to **.env** and file And fill in the remaining fields.

2. Run:
```
docker-compose build
docker-compose up
```


### Code style and contribution guide
- Install the [editorconfig](http://editorconfig.org/) plugin for your code editor.
- Used Flake8 or PEP8 plugins in your console or code editor.
- Do not copypaste, do not hack, always look for easiest solutions.
- Write tests for your code.
- For every task create a branch from current `master`.
- Prefer small commits and branches.
- Read this [docs]



### Deploy changes
- Add ssh key to server.
- Run `fab deploy`.
