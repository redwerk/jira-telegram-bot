### jira_users collection
```json
// Создание нового пользователя
{
  "_id": ObjectId("59bfbe69a47e654c39355f9d"),
  "telegram_id": 208810129,
  "host_url": none,
  "username": none,
  "auth_method": none,
  "auth": {
    "oauth": {
      "access_token": none,
      "access_token_secret": none
    },
    "basic": {
      "password": none
    }
  }
}

// Пользователь авторизован c помощью username/password
{
  "_id": ObjectId("59bfbe69a47e654c39355f9d"),
  "telegram_id": 208810129,
  "host_url": "https://jira.redwerk.com",
  "username": "iperesunko",
  "auth_method": "basic",
  "auth": {
    "oauth": {
      "access_token": none,
      "access_token_secret": none
    },
    "basic": {
      "password": BinData(0,
      "Z0FBQUFBQlp2ODFpS1BEZ0pRbjl1ekZzS0JlZFcySDFNa0gzTV9VRE5zU2doZG5FMDY3RC1DSnpsc1U0ZDRMbDhMaDNaSUJKSk9tdzlMX1pBRGlaZ0VGZE93Y1hFdDRTbXc9PQ==")
    }
  }
}

// Пользователь авторизован c помощью OAuth
{
  "_id": ObjectId("59bfbe69a47e654c39355f9d"),
  "telegram_id": 208810129,
  "host_url": "https://jira.redwerk.com",
  "username": "iperesunko",
  "auth_method": "oauth",
  "auth": {
    "oauth": {
      "access_token": "SMdbQck9e65GPSB8zn8FHdGAeRHQrZ2M",
      "access_token_secret": "S4FyvCi01cSHV9KDlBLgwX6oZ0s1UU3c"
    },
    "basic": {
      "password": none
    }
  }
}

// При выполнении команды logout
{
  "_id": ObjectId("59bfbe69a47e654c39355f9d"),
  "telegram_id": 208810129,
  "host_url": none,
  "username": none,
  "auth_method": none,
  "auth": {
    "oauth": {
      "access_token": none,
      "access_token_secret": none
    },
    "basic": {
      "password": none
    }
  }
}
```

### jira_hosts collection
```json
{
  "url": "https://jira.redwerk.com",
  "is_confirmed": true,
  "consumer_key": "OAuthKey",
}
```


### cache collection
```json
{
  "_id": ObjectId("5967855ee138233323e1ff61"),
  "createdAt": ISODate("2017-07-13T14:36:14.473Z"),
  "content": [
    [
      "<a href=\"https://jira.test.redwerk.com/browse/JTB-11\">JTB-11</a> Test 12",
      "<a href=\"https://jira.test.redwerk.com/browse/JTB-10\">JTB-10</a> Test 10",
      "<a href=\"https://jira.test.redwerk.com/browse/JTB-9\">JTB-9</a> Test 9",
      "<a href=\"https://jira.test.redwerk.com/browse/JTB-8\">JTB-8</a> Test 8",
      "<a href=\"https://jira.test.redwerk.com/browse/JTB-7\">JTB-7</a> Test 7",
      "<a href=\"https://jira.test.redwerk.com/browse/JTB-6\">JTB-6</a> Test 6",
      "<a href=\"https://jira.test.redwerk.com/browse/JTB-5\">JTB-5</a> Test 5",
      "<a href=\"https://jira.test.redwerk.com/browse/JTB-4\">JTB-4</a> Test 4",
      "<a href=\"https://jira.test.redwerk.com/browse/JTB-3\">JTB-3</a> Test 4",
      "<a href=\"https://jira.test.redwerk.com/browse/JTB-2\">JTB-2</a> Календарь листается только в пределах текущего года"
    ],
    [
      "<a href=\"https://jira.test.redwerk.com/browse/JTB-1\">JTB-1</a> Вывод данных в 3 сообщения"
    ]
  ],
  "key": "208810129:JTB:Backlog",
  "page_count": 2
}
```

### webhooks collection
```json
{
  "_id": ObjectId("5a437e5ff595b26337c08ddf"),
  "host_url": "https://jira.test.redwerk.com",
  "is_confirmed": false
}
```

### subscriptions collection
```json
{
  "_id": ObjectId("5a437f5af595b2646b46a3c2"),
  "chat_id": 208810129,
  "user_id": ObjectId("5a3b8e6df595b219a7906fc3"),
  "webhook_id": ObjectId("5a437e5ff595b26337c08ddf"),
  "topic": "issue",
  "name": "JTB-99"
},
{
  "_id": ObjectId("5a437f68f595b2646b46a3c3"),
  "chat_id": 208810129,
  "user_id": ObjectId("5a3b8e6df595b219a7906fc3"),
  "webhook_id": ObjectId("5a437e5ff595b26337c08ddf"),
  "topic": "project",
  "name": "JTB"
}
```
