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
  "is_confirmed": false,
}

// Факт авторизации подтвержден
{
  "url": "https://jira.test.redwerk.com",
  "readable_name": "Test Redwerk",
  "consumer_key": "OAuthKey",
  "is_confirmed": true,
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
