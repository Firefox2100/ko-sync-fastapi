# KoReader Sync Server FastAPI

A FastAPI implementation for KoReader Sync Server.

## About the project

This is a simple yet production-ready implementation of KoReader Sync server (originally written in Lua [here](https://github.com/koreader/koreader-sync-server)). It is written in Python using FastAPI and SQLite as the database. The original implementation is fully working, but it has some lack of functions that I need. Hence, I made this implementation, targeting self-hosting services for a smaller number of users with more control.

This project is in no way affiliated or sponsored by any of the original KoReader developers or teams. There may be unintentional problems within this codebase, so please report them if you find any. KoReader may also change the API for the upstream implementation and the plugin, which may break compatibility with this project. I would need some time to update this project to fit the latest development of KoReader. Please back up your database in case of any accidental data loss.

### What's different from the original implementation?

The main differences between this implementation and the original service are:

- Using Python and FastAPI.
- Using SQLite instead of Redis, allowing for a single container when deployed with docker, and suitable for a smaller scaled deployment.
- Added support to enable/disable user registration. This is the main addition I wanted in the original function, allowing self-hosting users to disable registration once all users are in place.

### Known issues

To keep compatibility with the KoReader Sync plugin, the APIs of the service is left unchanged. However, the original API was designed to be hosted on a public server with minimal data logging, so the functionality is minimal, while the security is basic. Specifically:

- The user key, which is the MD5 of the user password, is transmitted in headers in plain text. This is a major security risk, as stronger hashing algorithms should be used, and the key should be transmitted in the body of the request, encrypted with HTTPS.
- The user key is stored in the database in plain text. The original implementation does this, so I didn't bother to fix it, since the key is insecurely transmitted anyway. In future, if I have time, I may rectify this.
- Document names are MD5 digests of the original file name. This is suitable when storing all the information on a public server, as the file names should remain confidential. However this brought difficulties when trying to integrate this function into other services, for example calibre-web, because the original file name is unknown.

### Future plans

The current version is a proof-of-concept prototype, on which I intend to add more features. The roadmap includes:

- [ ] Token/API key-based authentication.
- [ ] Credential encryption.
- [ ] A basic interface/management API for user and document progress management.
- [ ] A way of integrating with calibre-web so that hosting this server separately is not necessary.

## Installation

### From source

The service will automatically bootstrap, so all it needs is to be served by an ASGI server. For example:

```shell
git clone https://github.com/Firefox2100/ko-sync-fastapi.git
cd ko-sync-fastapi
pip install -r requirements.txt
uvicorn src.app:app --host 0.0.0.0 --port 8000
```

The database file will be created at `./data/app.db`.

### Docker

The service has only one container, so either docker command or docker compose would do. The example docker compose file is:

```yaml
services:
  koreader-sync:
    image: firefox2100/ko-sync-fastapi:latest
    # environment:
    #   - ALLOW_REGISTRATION=true   # Uncomment this line to allow registration
    ports:
      - "8000:8000"
    volumes:
      - ko-sync-data:/data
    restart: unless-stopped

volumes:
  ko-sync-data:     # This is for database persistence. Not necessary, because the volume will be created by the container
```
