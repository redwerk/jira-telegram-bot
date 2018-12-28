#!/bin/bash
set -e

mongo <<EOF
use ${MONGO_INITDB_DATABASE}
db.createUser({
  user:  '${MONGO_INITDB_ROOT_USERNAME}',
  pwd: '${MONGO_INITDB_ROOT_PASSWORD}',
  roles: [{
    role: 'readWrite',
    db: 'jtb_db'
  }]
});
db.createCollection("users");
db.createCollection("hosts");
db.cache.createIndex({ "createdAt": 1 }, { expireAfterSeconds: 3600 });
EOF
