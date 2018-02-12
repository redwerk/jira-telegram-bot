import os

from fabric.api import run, env, cd, task, require


@task
def prod():
    """
    Apply settings for prod
    """
    env.name = 'prod'
    env.hosts = ['jirabot@165.227.153.227']
    env.user = 'jirabot'
    env.project_path = '/home/jirabot/jira-telegram-bot'
    env.venv_path = os.path.join(env.project_path, 'venv')
    env.reload_file = os.path.join(env.project_path, 'bin', "reload_prod.sh")


@task
def stage():
    """
    Apply settings for staging
    """
    env.name = 'stage'
    env.hosts = ['botelegram@46.28.194.157']
    env.user = 'botelegram'
    env.port = "22378"
    env.project_path = '/home/botelegram/jira-telegram-bot'
    env.venv_path = os.path.join(env.project_path, 'env')
    env.reload_file = os.path.join(env.project_path, 'bin', "reload_stage.sh")


@task
def pull():
    require('name')
    with cd(env.project_path):
        run('git pull')


@task
def reload_server():
    """
    Execute a specific file to force server restart.
    """
    require('name')
    with cd(env.project_path):
        run(env.reload_file)


@task
def deploy():
    """
    Performs full stack deployment
    """
    pull()
    reload_server()
