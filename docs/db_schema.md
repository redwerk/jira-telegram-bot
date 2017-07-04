### jira_users collection
```json
{
  "telegram_id" : "208810921",
  "host_url": "https://jira.test.redwerk.com",
  "username": "iperesunko",
  "access_token": "3223f32f23f23ff",
  "access_token_secret": "12313lkj1kl2jlkjk1j24"
}
```

### jira_hosts collection
```json
{
  "url": "https://jira.redwerk.com",
  "readable_name": "Redwerk",
  "settings": {
    "consumer_key": "OAuthKey",
    "key_sert": "jira_redwerk_privatekey.pem"
  }
},
{
  "url": "https://jira.test.redwerk.com",
  "readable_name": "Test Redwerk",
  "settings": {
    "consumer_key": "OAuthKey",
    "key_sert": "jira_redwerk_privatekey.pem"
  }
}
```

### user_permissions collections
```json
{
  "telegram_id" : "208810921",
  "allowed_hosts": ["https://jira.test.redwerk.com", "https://jira.redwerk.com"]
}
```
