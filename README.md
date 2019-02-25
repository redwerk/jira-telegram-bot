## Telegram bot for integration with JIRA

### Technologies
- Python 3.6
- MongoDB
- PyMongo
- [jira](https://github.com/pycontribs/jira)
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)


### Local deployment
1. Git wiki [link](https://git.redwerk.com/redwerk/jira-telegram-bot/wikis/home)
2. Instructions [link](docs/instruction.md)
3. Docs [link](docs)

### Running project tests

`DB_NAME` must be a database administrator (with rights to create collections)

Run command in root folder of project: `pytest -v`

### Code style and contribution guide
- Install the [editorconfig](http://editorconfig.org/) plugin for your code editor.
- Used Flake8 or PEP8 plugins in your console or code editor.
- Do not copypaste, do not hack, always look for easiest solutions.
- Write tests for your code.
- For every task create a branch from current `master`, when ready create a merge request back to dev.
- Prefer small commits and branches.
- Read this [docs]
