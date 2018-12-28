1. Get Administrator rights in JIRA
2. JIRA - Jira Administration - Applications - Application links
3. Put URL of application (**OAUTH_SERVICE_URL** in .env) -> Create new link
4. Step 1
    ```
    Application Name: JT-OAuth
    Application Type: Generic Application
    Service Provider Name: JT-OAuth
    Consumer key: whatever
    Shared secret: whatever
    Request Token URL: jira.host/plugins/servlet/oauth/request-token
    Access token URL: jira.host/plugins/servlet/oauth/access-token
    Authorize URL: jira.host/plugins/servlet/oauth/authorize
    Create incoming link [V]
    ```
    
5. Step 2
    ```.env
    Consumer Key: Consumer key (telegram)
    Consumer Name: Consumer name (telegram)
    Public key: Public key (telegram)
    ```
