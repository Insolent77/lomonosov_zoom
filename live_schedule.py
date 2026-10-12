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
