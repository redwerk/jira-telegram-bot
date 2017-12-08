import falcon

from resources import Updates, DatabaseSessionManager

app = falcon.API(middleware=DatabaseSessionManager())
app.add_route('/webhook/{webhook_id:uuid}/{project_key}/{issue_key}', Updates())
