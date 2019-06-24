1. Get Administrator rights in JIRA
2. JIRA - Jira Administration - Applications - Application links
3. Put URL of application (**OAUTH_SERVICE_URL** in .env) -> Create new link
4. Step 1
    ```
    Application Name: JT-OAuth
    Application Type: Generic Application
    Service Provider Name: JT-OAuth
    Create incoming link [V]
    ```
    
5. Step 2
    ```.env
    Consumer Key: Consumer key (telegram)
    Consumer Name: Consumer name (telegram)
    Public key: Public key (telegram)
    ```
