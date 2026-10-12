"""Read-only live schedule from Lomonosov PostgreSQL. Credentials via Render environment."""
import os
from datetime import date, timedelta
from zoneinfo import ZoneInfo

def get_lessons(date_from, date_to):
    try:
        import psycopg
    except ImportError:
        raise RuntimeError("psycopg is not installed")
    d1, d2 = date.fromisoformat(date_from), date.fromisoformat(date_to)
    if d2 < d1 or (d2-d1).days > 8:
        raise ValueError("Date range must be between 1 and 9 days")
    dsn = os.getenv("LOMONOSOV_READONLY_DATABASE_URL", "")
    if not dsn:
        raise RuntimeError("Set LOMONOSOV_READONLY_DATABASE_URL in Render Environment")
    tz = ZoneInfo("Europe/Moscow")
    from datetime import datetime, time
    start = datetime.combine(d1, time.min, tzinfo=tz)
    finish = datetime.combine(d2+timedelta(days=1), time.min, tzinfo=tz)
    sql = """
    SELECT l.id, g.name, loc.name, l.start_dt, l.start_dt+l.duration,
           l.status, COALESCE(t.surname, ''), COALESCE(t.name, '')
    FROM public.group_lesson l
    JOIN public.group_group g ON g.id=l.group_id
    LEFT JOIN public.group_location loc ON loc.id=COALESCE(l.location_id,g.location_id)
    LEFT JOIN public.teacher_teacher t ON t.id=l.teacher_id
    WHERE l.start_dt >= %s AND l.start_dt < %s
    ORDER BY l.start_dt, l.id
    LIMIT 1500
    """
    with psycopg.connect(dsn, connect_timeout=6, options="-c default_transaction_read_only=on", autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (start,finish))
            rows=cur.fetchall()
    return [
        {"id":r[0], "group":r[1], "room":r[2] or "Без локации",
         "start":r[3].astimezone(tz).isoformat(),
         "end":r[4].astimezone(tz).isoformat(),
         "status":r[5], "teacher":(r[6]+" "+r[7]).strip()}
        for r in rows
    ]

def recording_match_context(lesson_id):
    """Return internal matching metadata only; Zoom meeting URL is never sent to a client."""
    import re
    from datetime import datetime, timedelta, timezone
    import psycopg
    dsn = os.getenv("LOMONOSOV_READONLY_DATABASE_URL", "")
    if not dsn:
        raise RuntimeError("Database is not configured")
    with psycopg.connect(dsn, connect_timeout=6, options="-c default_transaction_read_only=on", autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT l.id, l.start_dt, l.duration, loc.meeting_url, loc.name
                FROM public.group_lesson l
                JOIN public.group_group g ON g.id=l.group_id
                LEFT JOIN public.group_location loc ON loc.id=COALESCE(l.location_id,g.location_id)
                WHERE l.id=%s
            """, (lesson_id,))
            row=cur.fetchone()
            if not row:
                return None
            _, starts, duration, meeting_url, location_name=row
            # Only standard numeric Zoom meeting IDs allow strong matching.
            match=re.search(r"(?:zoom\\.us)/(?:j|wc/j)/(\\d{9,12})(?:[/?#]|$)", meeting_url or "", re.I)
            meeting_id=match.group(1) if match else ""
            if not meeting_id:
                number=re.fullmatch(r"Zoom ([1-9]|1[0-2])", location_name or "")
                if number:
                    meeting_id=os.getenv("ZOOM_MEETING_ID_"+number.group(1), "").replace(" ", "")
            if not re.fullmatch(r"\d{9,12}", meeting_id):
                return {"state":"unmapped"}
            # If the same persistent Zoom meeting has multiple lessons in the time window,
            # do not attach a recording to either one.
            cur.execute("""
                SELECT COUNT(*)
                FROM public.group_lesson l
                JOIN public.group_group g ON g.id=l.group_id
                LEFT JOIN public.group_location loc ON loc.id=COALESCE(l.location_id,g.location_id)
                WHERE l.start_dt BETWEEN %s AND %s
                  AND loc.id = (
                    SELECT COALESCE(x.location_id, y.location_id)
                    FROM public.group_lesson x JOIN public.group_group y ON y.id=x.group_id
                    WHERE x.id=%s
                  )
            """, (starts-timedelta(minutes=15), starts+timedelta(minutes=15), lesson_id))
            if cur.fetchone()[0] != 1:
                return {"state":"ambiguous"}
            return {"state":"ok","meeting_id":meeting_id,
                    "starts":starts.astimezone(timezone.utc).isoformat(),
                    "ends":(starts+duration).astimezone(timezone.utc).isoformat()}
