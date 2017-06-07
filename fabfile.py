import os

from fabric.api import run, env, cd, task


# Server configurations
env.name = 'stage'
env.hosts = ['botelegram@kiev2.redwerk.com']
env.port = "22378"
env.user = 'botelegram'
env.path = '/home/botelegram/jira-telegram-bot'
env.venv = os.path.join(env.path, 'env')


@task
def reload_bot():
    # Touch a specific file to force bot restart.
    with cd(env.path):
        run('./reload.sh')


@task
def pull():
    # Make git pull command
    with cd(env.path):
        run('git pull')


@task
def deploy():
    # Performs full stack deployment
    pull()
    reload_bot()
