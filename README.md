nginx-discord-role-auth
---
Sooo... it's a simple server that validates that user have specified role on server from environment.\
For using this, you need clone repo or maybe add it to your's docker/portainer with specified ENV:
```
# discord oauth client parametrs!
CLIENT_ID=
CLIENT_SECRET=
CLIENT_REDIRECT_URI=

# some jwt secret
JWT_SECRET=
# your's guild
GUILD_ID=
# your's role id on server
ROLE_ID=

# host parameters for FASTAPI
HOST=127.0.0.1
PORT=8080
```
For nginx you need use `auth_request` that points to `/_oauth2/check`, and you need to proxy `/_oauth2` to that server\
Maybe I will push simple config later, ¯\_(ツ)_/¯ idk