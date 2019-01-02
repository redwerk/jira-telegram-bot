#### Prepare environment
- Create directories

keys
* Generate RSA keys
```.env
cd keys
openssl genrsa -out jtb_privatekey.pem 1024
openssl req -newkey rsa:1024 -x509 -key jtb_privatekey.pem -out jtb_publickey.cer -days 365
openssl pkcs8 -topk8 -nocrypt -in jtb_privatekey.pem -out jtb_privatekey.pcks8
openssl x509 -pubkey -noout -in jtb_publickey.cer  > jtb_publickey.pem

```

#### Prepare MongoDB database
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

#### Prepare public and private keys
```
openssl genrsa -out jtb_privatekey.pem 1024
openssl req -newkey rsa:1024 -x509 -key jtb_privatekey.pem -out jtb_publickey.cer -days 365
openssl pkcs8 -topk8 -nocrypt -in jtb_privatekey.pem -out jtb_privatekey.pcks8
openssl x509 -pubkey -noout -in jtb_publickey.cer  > jtb_publickey.pem
```
Put keys in the folder. Absolute path set in  **PRIVATE_KEY_PATH** и **PUBLIC_KEY_PATH** .env variables

E. g.
```.env
PRIVATE_KEY_PATH=/home/user/.keys/jtb_privatekey.pem
PUBLIC_KEY_PATH=/home/user/.keys/jtb_publickey.pem
```

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
Production (later)

#### Running (locally)
Bash
```.env
python run.py bot
python run.py web
```

#### Running (Docker)
