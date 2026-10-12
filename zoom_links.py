"""Safely attach Zoom's playback passcode to a cloud recording share URL."""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def playback_url(recording):
    url = recording.get("share_url") or ""
    if not isinstance(url, str) or not url.startswith("https://"):
        return ""
    code = recording.get("recording_play_passcode")
    if not isinstance(code, str) or not code:
        return url
    try:
        parts = urlsplit(url)
        if not (parts.hostname == "zoom.us" or (parts.hostname or "").endswith(".zoom.us")):
            return url
        params = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "pwd"]
        params.append(("pwd", code))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), parts.fragment))
    except ValueError:
        return url
