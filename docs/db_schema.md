### jira_users collection
```json
// Создание нового пользователя
{
  "telegram_id" : 208810129,
  "host_url": null,
  "username": null,
  "access_token": null,
  "access_token_secret": null,
  "allowed_hosts": []
}

// Пользователь полностью авторизован
{
  "telegram_id" : 208810129,
  "host_url": "https://jira.test.redwerk.com",
  "username": "iperesunko",
  "access_token": "3223f32f23f23ff",
  "access_token_secret": "12313lkj1kl2jlkjk1j24",
  "allowed_hosts": [ObjectId("595b971db645d6240f1fd1be"), ObjectId("595b971db645d6240f1fd1be")]
}

// При выполнении команды logout
{
  "telegram_id" : 208810129,
  "host_url": null,
  "username": null,
  "access_token": null,
  "access_token_secret": null,
  "allowed_hosts": [ObjectId("595b971db645d6240f1fd1be"), ObjectId("595b971db645d6240f1fd1be")]
}
```

### jira_hosts collection
```json
// Ключи сгенерированны, но ни один пользователь не авторизован
{
  "url": "https://jira.redwerk.com",
  "readable_name": "Redwerk",
  "consumer_key": "OAuthKey",
  "key_sert": "jira_redwerk_privatekey.pem",
  "is_confirmed": false,
}

// Факт авторизации подтвержден
{
  "url": "https://jira.test.redwerk.com",
  "readable_name": "Test Redwerk",
  "consumer_key": "OAuthKey",
  "key_sert": "jira_redwerk_privatekey.pem",
  "is_confirmed": true,
}
```
