"""Lomonosov Zoom webhook test stand. Python 3.10+, standard library only."""
import hashlib
import hmac
import html
import json
import os
import sqlite3
import time
from datetime import date
from urllib.parse import parse_qs
from zoom_archive import fetch_recordings
from zoom_links import playback_url
from demo_workflow import PAGE as DEMO_WORKFLOW_PAGE
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

DB = os.environ.get("DATABASE_PATH", "demo.sqlite3")
SECRET = os.environ.get("ZOOM_WEBHOOK_SECRET_TOKEN", "")
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
DEMO = os.environ.get("DEMO_MODE", "0") == "1"


def connect():
    conn = sqlite3.connect(DB, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY, name TEXT NOT NULL, subject TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS lessons (
            id INTEGER PRIMARY KEY, group_id INTEGER NOT NULL, topic TEXT NOT NULL,
            teacher TEXT NOT NULL, starts TEXT NOT NULL, meeting_id TEXT NOT NULL,
            meeting_uuid TEXT NOT NULL UNIQUE);
        CREATE TABLE IF NOT EXISTS recordings (
          meeting_uuid TEXT PRIMARY KEY, meeting_id TEXT NOT NULL, topic TEXT,
          start_time TEXT, recording_url TEXT, received_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER NOT NULL,
            lesson_id INTEGER NOT NULL, meeting_uuid TEXT NOT NULL UNIQUE,
            recording_url TEXT NOT NULL, created_at TEXT NOT NULL);
        """)
        if not db.execute("SELECT 1 FROM groups").fetchone():
            db.executemany("INSERT INTO groups VALUES (?, ?, ?)", [
                (1, "7 класс · Группа А", "Математика"),
                (2, "8 класс · Группа Б", "Физика"),
            ])
            db.executemany("INSERT INTO lessons VALUES (?, ?, ?, ?, ?, ?, ?)", [
                (101, 1, "Линейные уравнения", "Иван Иванович", "12.10.2026 · 16:00", "12345678901", "test-uuid-math-101"),
                (102, 2, "Законы Ньютона", "Елена Сергеевна", "12.10.2026 · 18:00", "12345678901", "test-uuid-physics-102"),
            ])


def publish(obj):
    uuid = obj.get("uuid")
    meeting_id = obj.get("id")
    url = obj.get("share_url")
    if not isinstance(uuid, str) or not uuid or not isinstance(url, str) or not url.startswith("https://"):
        return "invalid", None
    with connect() as db:
        lesson = db.execute("SELECT * FROM lessons WHERE meeting_uuid=?", (uuid,)).fetchone()
        if lesson is None or str(meeting_id) != lesson["meeting_id"]:
            return "unmatched", None
        try:
            db.execute(
                "INSERT INTO messages(group_id, lesson_id, meeting_uuid, recording_url, created_at) VALUES (?, ?, ?, ?, ?)",
                (lesson["group_id"], lesson["id"], uuid, url, datetime.now(timezone.utc).isoformat()),
            )
        except sqlite3.IntegrityError:
            return "duplicate", lesson["group_id"]
        return "sent", lesson["group_id"]



def save_recording(obj):
    uuid, meeting_id = obj.get("uuid"), obj.get("id")
    if not isinstance(uuid, str) or not uuid or meeting_id is None:
        return "invalid"
    url = playback_url(obj)
    if not isinstance(url, str) or (url and not url.startswith("https://")):
        return "invalid"
    topic = str(obj.get("topic") or "")[:300]
    start = str(obj.get("start_time") or "")[:100]
    with connect() as db:
        old = db.execute("SELECT 1 FROM recordings WHERE meeting_uuid=?", (uuid,)).fetchone()
        db.execute("""INSERT INTO recordings (meeting_uuid, meeting_id, topic, start_time, recording_url, received_at)
          VALUES (?, ?, ?, ?, ?, ?)
          ON CONFLICT(meeting_uuid) DO UPDATE SET
            meeting_id=excluded.meeting_id, topic=excluded.topic,
            start_time=excluded.start_time,
            recording_url=CASE WHEN excluded.recording_url <> '' THEN excluded.recording_url ELSE recordings.recording_url END""",
          (uuid, str(meeting_id), topic, start, url, datetime.now(timezone.utc).isoformat()))
    return "updated" if old else "received"


def render_recordings(day='2026-10-11', sync=False):
    esc = lambda x: html.escape(str(x or ""), quote=True)
    try:
        date.fromisoformat(day)
        error = ""
    except ValueError:
        day, error = "2026-10-11", "Неверная дата."
    status = ""
    if sync and not error:
        try:
            items = fetch_recordings(day)
            for meeting in items:
                save_recording(meeting)
            status = f"Zoom вернул конференций: {len(items)}."
        except (ValueError, KeyError) as exc:
            error = str(exc)
    with connect() as db:
        rows = db.execute("SELECT * FROM recordings WHERE substr(start_time,1,10)=? ORDER BY start_time DESC LIMIT 200", (day,)).fetchall()
    items = []
    for row in rows:
        link = ('<a href="' + esc(row["recording_url"]) + '" target="_blank" rel="noopener noreferrer">Открыть запись ↗</a>'
                if row["recording_url"] else '<span>Ссылка на запись не передана Zoom</span>')
        items.append('<article><b>' + esc(row["topic"] or "Конференция Zoom") +
          '</b><p>Начало: ' + esc(row["start_time"] or "не указано") +
          ' · Получено: ' + esc(row["received_at"]) + '</p>' +
          '<p>Meeting ID: ' + esc(row["meeting_id"]) + ' · UUID: ' + esc(row["meeting_uuid"]) +
          '</p>' + link + '</article>')
    return ("""<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="noindex,nofollow"><title>Полученные записи Zoom</title>
    <style>body{font:15px/1.5 system-ui;background:#f4f6fb;color:#17223c;max-width:960px;margin:35px auto;padding:0 20px}
    article{background:#fff;border:1px solid #dce4ef;border-radius:14px;padding:20px;margin:14px 0;overflow-wrap:anywhere}
    p{color:#70809a;font-size:13px}a{color:#3167e8}small{color:#8392a9}</style></head><body>
    <p><a href="/">← Главная</a></p><h1>Полученные записи Zoom</h1>
    <p>Сюда поступают события recording.completed, даже если занятие пока не привязано к группе.</p>
    <p><b>Внимание:</b> этот тестовый раздел доступен всем по ссылке.</p>
    <form action="/recordings" method="GET">
    <label>Дата: <input type="date" name="date" value='""" + esc(day) + """' required></label>
    <button type="submit" name="sync" value="1">Загрузить из Zoom</button>
    </form><p>""" + esc(error or status) + """</p>""" +
    (''.join(items) if items else '<article>Пока записей нет. После завершения облачной записи Zoom пришлёт событие.</article>') +
    '<small>Бесплатный Render: данные могут исчезнуть при перезапуске сервиса.</small></body></html>')


def render_page():
    with connect() as db:
        groups = db.execute("SELECT * FROM groups ORDER BY id").fetchall()
        lessons = db.execute("SELECT * FROM lessons ORDER BY id").fetchall()
        messages = db.execute("SELECT * FROM messages ORDER BY id").fetchall()
    esc = lambda value: html.escape(str(value), quote=True)
    cards = []
    for group in groups:
        lesson_html = "".join(
            '<article class="lesson"><b>' + esc(lesson["topic"]) + '</b>'
            + '<small>' + esc(lesson["starts"]) + " · " + esc(lesson["teacher"]) + '</small>'
            + '<code>Meeting ID: ' + esc(lesson["meeting_id"]) + '<br>Session UUID: ' + esc(lesson["meeting_uuid"]) + '</code>'
            + ('<button data-uuid="' + esc(lesson["meeting_uuid"]) + '" data-meeting="' + esc(lesson["meeting_id"]) + '">Сымитировать запись ↗</button>' if DEMO else "")
            + '</article>'
            for lesson in lessons if lesson["group_id"] == group["id"]
        )
        msg_html = "".join(
            '<div class="chat"><span class="avatar">Л</span><div class="bubble"><b>Мой Ломоносов · бот</b><p>🎬 Запись занятия готова!</p>'
            + '<a target="_blank" rel="noopener noreferrer" href="' + esc(msg["recording_url"]) + '">Открыть запись занятия ↗</a>'
            + '<small>Урок №' + esc(msg["lesson_id"]) + '</small></div></div>'
            for msg in messages if msg["group_id"] == group["id"]
        ) or '<div class="empty">Записей пока нет</div>'
        cards.append(
            '<section class="group"><h2>' + esc(group["name"]) + '</h2><p class="sub">' + esc(group["subject"]) + ' · учебный чат</p>'
            + '<h3>Занятия</h3>' + lesson_html + '<h3>Сообщения в чате</h3><div class="messages">' + msg_html + '</div></section>'
        )
    notice = ('Демонстрационный режим: кнопки создают тестовые записи.' if DEMO
              else 'Внешний стенд: демо-кнопки отключены. <a href="/recordings">Полученные записи Zoom ↗</a>. Приём webhook: POST /webhooks/zoom.')
    return """<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Мой Ломоносов · Zoom</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f5f7fb;color:#15213b;font:15px/1.5 system-ui,'Segoe UI',sans-serif}
header{background:#fff;border-bottom:1px solid #e1e8f2;padding:16px 30px;font-weight:800;font-size:20px}
main{max-width:1120px;margin:35px auto;padding:0 24px}h1{font-size:30px;margin:0 0 6px}.lead,.sub{color:#8290a5}
.notice{background:#fff7e8;border:1px solid #ffe2ac;border-radius:12px;padding:14px;margin:24px 0}
.layout{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.group{border:1px solid #e1e7f2;border-radius:18px;background:#fff;padding:22px;min-width:0;box-shadow:0 5px 24px #0f223908}
h2{font-size:20px;margin:0}.sub{margin:3px 0 16px;font-size:13px}h3{font-size:12px;text-transform:uppercase;letter-spacing:1px;color:#8c98ad;margin-top:23px}
.lesson{border:1px solid #e2e8f2;border-radius:12px;padding:13px}small{display:block;color:#8d9ab0;margin:5px 0;font-size:12px}
code{display:block;color:#6d7e96;font-size:11px;overflow-wrap:anywhere;margin:11px 0}
button{border:0;border-radius:10px;background:#396dea;color:#fff;padding:11px;width:100%;font-weight:700;cursor:pointer}
.messages{min-height:145px;border-radius:12px;padding:13px;background:#f7f9fe}.chat{display:flex;gap:9px;margin-bottom:9px}
.avatar{background:#ffebdb;color:#c76b29;border-radius:9px;padding:9px;align-self:flex-start}
.bubble{background:white;padding:12px 15px;border-radius:12px;overflow-wrap:anywhere;box-shadow:0 1px 6px #13223812}
.bubble b{font-size:13px}.bubble p{margin:9px 0}.bubble a{color:#3069df;font-weight:700;text-decoration:none}
.empty{text-align:center;color:#9ba7b7;padding:42px 0}.footer{font-size:13px;color:#8392a6;margin-top:20px}
@media(max-width:760px){.layout{grid-template-columns:1fr}h1{font-size:25px}}
</style></head><body><header>🟠 Мой Ломоносов · тестовый стенд</header><main><h1>Записи Zoom → учебные чаты</h1>
<p class="lead">Распределение записей по UUID конкретного сеанса конференции</p><div class="notice">""" + notice + """</div>
<p><a href="/teacher">Кабинет преподавателя ↗</a> · <a href="/chats">Учебные чаты ↗</a></p><div class="layout">""" + "".join(cards) + """</div><p class="footer">Пример: один Meeting ID, но два разных Session UUID.</p></main>
<script>document.querySelectorAll('button[data-uuid]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{
let r=await fetch('/api/demo/complete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({uuid:b.dataset.uuid,id:b.dataset.meeting})});
let v=await r.json();if(v.status==='sent'||v.status==='duplicate')location.reload();else throw Error(v.status);
}catch(e){alert(e.message);b.disabled=false}})</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def respond(self, code, payload, content_type="application/json; charset=utf-8"):
        raw = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/teacher", "/chats"):
            return self.respond(200, DEMO_WORKFLOW_PAGE.encode(), "text/html; charset=utf-8")
        if path == "/":
            return self.respond(200, render_page().encode(), "text/html; charset=utf-8")
        if path == "/recordings":
            return self.respond(200, render_recordings(day=parse_qs(parsed.query).get("date", ["2026-10-11"])[0], sync=parse_qs(parsed.query).get("sync", ["0"])[0] == "1").encode(), "text/html; charset=utf-8")
        if path == "/health":
            return self.respond(200, {"ok": True})
        return self.respond(404, {"error": "Not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ("/api/demo/complete", "/webhooks/zoom"):
            return self.respond(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 1048576:
                return self.respond(413, {"error": "Invalid body size"})
            raw = self.rfile.read(length)
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError()
        except (ValueError, UnicodeDecodeError):
            return self.respond(400, {"error": "Invalid JSON"})

        if path == "/api/demo/complete":
            if not DEMO or self.client_address[0] not in ("127.0.0.1", "::1"):
                return self.respond(403, {"error": "Demo endpoint disabled"})
            if not isinstance(data.get("uuid"), str) or not isinstance(data.get("id"), str):
                return self.respond(400, {"error": "Invalid IDs"})
            state, group = publish({"uuid": data["uuid"], "id": data["id"],
                                    "share_url": "https://example.com/demo-recording/" + data["uuid"]})
            return self.respond(200, {"status": state, "group_id": group})

        if not SECRET:
            return self.respond(503, {"error": "Set ZOOM_WEBHOOK_SECRET_TOKEN"})

        # Zoom challenge-response validation; verify the header signature if present.
        if data.get("event") == "endpoint.url_validation":
            token = data.get("payload", {}).get("plainToken")
            if not isinstance(token, str) or not token:
                return self.respond(400, {"error": "Invalid challenge"})
            encrypted = hmac.new(SECRET.encode(), token.encode(), hashlib.sha256).hexdigest()
            return self.respond(200, {"plainToken": token, "encryptedToken": encrypted})

        timestamp = self.headers.get("x-zm-request-timestamp", "")
        try:
            if abs(time.time() - int(timestamp)) > 300:
                raise ValueError()
        except ValueError:
            return self.respond(401, {"error": "Invalid timestamp"})
        message = b"v0:" + timestamp.encode() + b":" + raw
        expected = "v0=" + hmac.new(SECRET.encode(), message, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, self.headers.get("x-zm-signature", "")):
            return self.respond(401, {"error": "Invalid signature"})
        if data.get("event") != "recording.completed":
            return self.respond(200, {"status": "ignored"})
        obj = data.get("payload", {}).get("object")
        if not isinstance(obj, dict):
            return self.respond(400, {"error": "Invalid payload"})
        save_state = save_recording(obj)
        state, group = publish(obj)
        print(f"Zoom recording: saved={save_state} routing={state} meeting_id={obj.get('id')}", flush=True)
        return self.respond(200, {"status": state, "stored": save_state, "group_id": group})


if __name__ == "__main__":
    init_db()
    print(f"Listening on {HOST}:{PORT} (DEMO_MODE={DEMO})", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
