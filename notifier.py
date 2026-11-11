import html, json, os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

API = "https://flingtrainer.com/wp-json/wp/v2/posts"
STATE = Path("seen.json")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; trainer-notifier/1.0)"}
NEW_WINDOW = timedelta(days=7)  # опубликован не раньше 7 дней назад -> считаем новым


def parse(ts):
    return datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)


def fetch_posts():
    r = requests.get(
        API,
        params={"per_page": 30, "orderby": "modified", "order": "desc",
                "_fields": "id,link,title,date_gmt,modified_gmt"},
        headers=HEADERS, timeout=30,
    )
    r.raise_for_status()
    return r.json()


def send(text):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
        timeout=30,
    ).raise_for_status()


def main():
    posts = fetch_posts()
    first_run = not STATE.exists()
    state = {} if first_run else json.loads(STATE.read_text())  # {id: modified_gmt}
    now = datetime.now(timezone.utc)

    if not first_run:
        events = []
        for p in posts:
            old_modified = state.get(str(p["id"]))
            if old_modified is None:
                # раньше не видели: либо реально новый, либо старый, попавший в топ после правки
                is_new = now - parse(p["date_gmt"]) < NEW_WINDOW
                events.append(("new" if is_new else "upd", p))
            elif old_modified != p["modified_gmt"]:
                events.append(("upd", p))

        # от старых событий к новым
        for kind, p in sorted(events, key=lambda e: e[1]["modified_gmt"]):
            title = html.escape(html.unescape(p["title"]["rendered"]))
            label = "🆕 Новый трейнер" if kind == "new" else "🔄 Обновлён трейнер"
            send(f"{label}: <b>{title}</b>\n{p['link']}")

    for p in posts:
        state[str(p["id"])] = p["modified_gmt"]
    STATE.write_text(json.dumps(state))


if __name__ == "__main__":
    main()
