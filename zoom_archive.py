"""Import cloud recordings using account-level Server-to-Server OAuth."""
import base64
import json
import os
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

def request_json(url, *, post=False, basic=None, bearer=None):
    headers = {"Accept": "application/json"}
    if basic:
        headers["Authorization"] = "Basic " + base64.b64encode(basic.encode()).decode()
    if bearer:
        headers["Authorization"] = "Bearer " + bearer
    request = Request(url, data=b"" if post else None, headers=headers, method="POST" if post else "GET")
    try:
        with urlopen(request, timeout=22) as response:
            return json.load(response)
    except HTTPError as exc:
        detail = exc.read(600).decode("utf-8", "replace")
        raise ValueError(f"Zoom API HTTP {exc.code}: {detail}") from None
    except (URLError, TimeoutError):
        raise ValueError("Не удалось связаться с Zoom API") from None

def fetch_recordings(day):
    account = os.getenv("ZOOM_ACCOUNT_ID")
    client = os.getenv("ZOOM_CLIENT_ID")
    secret = os.getenv("ZOOM_CLIENT_SECRET")
    email = os.getenv("ZOOM_USER_EMAIL")
    if not all((account, client, secret)):
        raise ValueError("Нужно заполнить ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET в Render.")
    if not email:
        raise ValueError("Добавьте ZOOM_USER_EMAIL: почту пользователя Zoom, чьи записи нужно получить.")
    token_url = "https://zoom.us/oauth/token?" + urlencode({"grant_type": "account_credentials", "account_id": account})
    token = request_json(token_url, post=True, basic=client + ":" + secret).get("access_token")
    if not token:
        raise ValueError("Zoom не выдал access_token.")
    items, page = [], ""
    for _ in range(20):
        params = {"from": day, "to": day, "page_size": 100}
        if page:
            params["next_page_token"] = page
        endpoint = "https://api.zoom.us/v2/users/" + quote(email, safe="") + "/recordings?" + urlencode(params)
        result = request_json(endpoint, bearer=token)
        items.extend(item for item in result.get("meetings", []) if isinstance(item, dict))
        page = result.get("next_page_token")
        if not page:
            break
    return items
