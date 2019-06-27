#### Prepare environment
- Create **keys**, **logs** directories
- Create **.env** fle, populate with **.env.example** data
* Generate RSA keys
```.env
cd keys
openssl genrsa -out jtb_privatekey.pem 1024
openssl req -newkey rsa:1024 -x509 -key jtb_privatekey.pem -out jtb_publickey.cer -days 365
openssl pkcs8 -topk8 -nocrypt -in jtb_privatekey.pem -out jtb_privatekey.pcks8
openssl x509 -pubkey -noout -in jtb_publickey.cer  > jtb_publickey.pem

```

#### Installation and configuration [Local]
1. Create a virtualenv: `python3.6 -m venv venv`
2. Install requirements `pip3 install -r requirements/local.txt`
3. Install and set up [MongoDB](creating-mongodb-dbs-for-local-development)
4. Install and set up [Redis](https://redis.io/topics/quickstart)

#### Prepare MongoDB database [Local]
- Create database and collections

Variables .env
```.env
DB_NAME=jtb_db
DB_USER_COLLECTION=users
DB_HOST_COLLECTION=hosts
DB_CACHE_COLLECTION=cache
```
Bash
```mongo
mongo
use jtb_db
db.createCollection("users")
db.createCollection("hosts")
db.cache.createIndex({ "createdAt": 1 }, { expireAfterSeconds: 3600 }) # запись удалится через час
```

- Create user/password in DB

Variables .env
```.env
DB_USER=user
DB_PASS=pwd
```
Bash
````
mongo
use jtb_db
db.createUser(
{
    user: "user",
    pwd: "pwd",
    roles: [{role: "readWrite" , db: "jtb_db"]
})
````

#### Get URL for Oauth 2.0 authorization
Locally
```.env
ngrok http 127.0.0.1:5000
```
Or if you prefer localtunnel over ngrok
```.env
lt --port 5000 --subdomain jtb_test
```
Received URL set in **OAUTH_SERVICE_URL** .env variable

via ngrok
```.env
OAUTH_SERVICE_URL=http://012345b7.ngrok.io
```
via localtunnel
```.env
jtb_test.localtunnel.me
```

#### Additional configuration
- [Setting up authorization via OAuth for JiraBot](https://telegra.ph/Setting-up-authorization-via-OAuth-for-JiraBot-11-29)
- [Creating the Webhook for JiraBot in Jira](https://telegra.ph/Creating-the-Webhook-for-JiraBot-in-Jira-12-22)


#### Running [Local]
Bash
```.env
python run.py bot
python run.py web
```

#### Running [Docker locally]
```.env
docker-compose up --build
```

#### Running [Docker staging]
```.env
docker-compose -f docker-compose.yml -f docker-compose.staging.yml up -d
```

#### Running tests [Local]
```text
In root folder
pytest -v
```
