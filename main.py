import os
import time
from typing import Union
from dotenv import load_dotenv

import uvicorn

from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse, PlainTextResponse, HTMLResponse
from fastapi.requests import Request
from fastapi_discord import DiscordOAuthClient, RateLimited, Unauthorized, User, Guild
from fastapi_discord.exceptions import ClientSessionNotInitialized
import jwt

app = FastAPI()

load_dotenv()

config = {
    "CLIENT_ID": os.environ.get("CLIENT_ID", ""),
    "CLIENT_SECRET": os.environ.get("CLIENT_SECRET", ""),
    "CLIENT_REDIRECT_URI": os.environ.get("CLIENT_REDIRECT_URI", ""),
    "JWT_SECRET": os.environ.get("JWT_SECRET", ""),
    "GUILD_ID": os.environ.get("GUILD_ID", ""),
    "ROLE_ID": os.environ.get("ROLE_ID", ""),
    "HOST": os.environ.get("HOST", "127.0.0.1"),
    "PORT": int(os.environ.get("PORT", "8080"))
}

discord = DiscordOAuthClient(
    config["CLIENT_ID"], 
    config["CLIENT_SECRET"], 
    config["CLIENT_REDIRECT_URI"], 
    ("identify", "guilds", "guilds.members.read", "email")
)  # scopes

# авторизуем чувака
# ставим jwt token с access_token дискорда и expire 86400 (1 день)
# на каждом реквесте, убеждаемся, что чел имеет роль с TTL 10 минут, иначе 401 и на авторизацию

def signJWT(user_id: int, discord_token: str) -> dict[str, str]:
    payload = {
        "user_id": user_id,
        "discord_token": discord_token,
        "expires": time.time() + 86400
    }
    return jwt.encode(payload, config['JWT_SECRET'], algorithm="HS256")


def decodeJWT(token: str) -> Union[dict, None]:
    try:
        decoded_token = jwt.decode(token, config['JWT_SECRET'], algorithms=["HS256"])
        return decoded_token if decoded_token["expires"] >= time.time() else None
    except:
        return None


async def discord_user(token: str):
    return User(**(await discord.request("/users/@me", token)))

async def discord_guilds(token: str):
    return [Guild(**guild) for guild in await discord.request("/users/@me/guilds", token)]

async def discord_full_guild_info(token: str):
    return await discord.request(f"/users/@me/guilds/{config['GUILD_ID']}/member", token)

def simple_http_content(title: str, redirect_url: str):
    return f"""
    <html>
        <head>
            <title>{title}</title>
            <meta http-equiv="refresh" content="0; url={redirect_url}" />
        </head>
        <body>
            <p>You'll be redirect in few seconds</p>
        </body>
    </html>"""

@app.on_event("startup")
async def on_startup():
    await discord.init()


async def validate_user(token: str):
    data = decodeJWT(token)
    if not data:
        return False

    user_guilds = await discord_guilds(data["discord_token"])
    needed_guild = None
    for guild in user_guilds:
        if guild.id == config["GUILD_ID"]:
            needed_guild = guild
            break

    if not needed_guild:
        return False
    
    full_guild_member_info = await discord_full_guild_info(data["discord_token"])
    if "roles" in full_guild_member_info and config["ROLE_ID"] not in full_guild_member_info["roles"]:
        return False

    return True

@app.get("/_oauth2/check")
async def login(request: Request):
    if '_auth_token' in request.cookies:
        validated = await validate_user(request.cookies.get("_auth_token", ""))
        if validated:
            return HTMLResponse(simple_http_content("ok", "/"), status_code=200)
        else:
            err_resp = PlainTextResponse("you dont have access, ask for permission!", status_code=401)
            err_resp.delete_cookie("_auth_token")
            return err_resp

    return PlainTextResponse("you dont have permission to be located here!", status_code=401)


@app.get("/_oauth2/login")
async def login_redirect(request: Request):
    return HTMLResponse(content=simple_http_content("discord authorization", discord.oauth_login_url), status_code=200)


@app.get("/_oauth2/callback")
async def callback(code: str):
    token, _ = await discord.get_access_token(code)
    user = await discord_user(token)
    jwt_token = signJWT(user_id=user.id, discord_token=token)

    response = RedirectResponse("/_oauth2/check")
    response.set_cookie(key="_auth_token", value=jwt_token, max_age=86400)
    return response


@app.exception_handler(Unauthorized)
async def unauthorized_error_handler(_, __):
    return JSONResponse({"error": "Unauthorized"}, status_code=401)


@app.exception_handler(RateLimited)
async def rate_limit_error_handler(_, e: RateLimited):
    return JSONResponse(
        {"error": "RateLimited", "retry": e.retry_after, "message": e.message},
        status_code=429,
    )


@app.exception_handler(ClientSessionNotInitialized)
async def client_session_error_handler(_, e: ClientSessionNotInitialized):
    print(e)
    return JSONResponse({"error": "Internal Error"}, status_code=500)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=config["PORT"], log_level="info")