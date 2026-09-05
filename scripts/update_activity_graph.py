import json
import os
from datetime import datetime, timedelta, timezone
from html import escape
from urllib.request import Request, urlopen

USERNAME = os.environ.get("GITHUB_USERNAME", "RichardBijuJohn")
OUTPUT = "activity-graph.svg"
DAYS = 31
EVENTS_URL = f"https://api.github.com/users/{USERNAME}/events/public"


def get_activity():
    counts = {}
    for page in range(1, 4):
        request = Request(
            f"{EVENTS_URL}?per_page=100&page={page}",
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "github-activity-graph-updater",
            },
        )
        with urlopen(request, timeout=30) as response:
            events = json.load(response)
        if not events:
            break
        for event in events:
            timestamp = event.get("created_at")
            if not timestamp:
                continue
            day = timestamp[:10]
            if event.get("type") == "PushEvent":
                value = len(event.get("payload", {}).get("commits") or []) or 1
            else:
                value = 1
            counts[day] = counts.get(day, 0) + value

    today = datetime.now(timezone.utc).date()
    dates = [
        (today - timedelta(days=offset)).isoformat()
        for offset in range(DAYS - 1, -1, -1)
    ]
    return dates, [counts.get(day, 0) for day in dates]


def make_svg(dates, values):
    maximum = max(values) or 1
    left, right, top, baseline = 56, 860, 42, 230
    step = (right - left) / (len(values) - 1)
    points = [
        (left + index * step, baseline - value / maximum * (baseline - top))
        for index, value in enumerate(values)
    ]
    line = " ".join(
        f"{'M' if index == 0 else 'L'}{x:.1f} {y:.1f}"
        for index, (x, y) in enumerate(points)
    )
    area = f"{line} L{right} {baseline} L{left} {baseline} Z"
    markers = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5"/>'
        for (x, y), value in zip(points, values)
        if value > 0
    )
    date_labels = []
    for index in range(0, len(dates), 5):
        x = left + index * step
        date_labels.append(f'<text x="{x:.1f}" y="260">{escape(dates[index][5:])}</text>')
    if (len(dates) - 1) % 5:
        date_labels.append(f'<text x="{right:.1f}" y="260">{escape(dates[-1][5:])}</text>')
    y_labels = "".join(
        f'<text x="18" y="{baseline - index * 47 - 4}">{round(maximum * index / 4)}</text>'
        for index in range(5)
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 280" role="img" aria-labelledby="title desc">
  <title id="title">Daily GitHub activity</title>
  <desc id="desc">An area graph of daily GitHub activity from {escape(dates[0])} through {escape(dates[-1])}.</desc>
  <defs>
    <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#38bdf8" stop-opacity=".78"/>
            <stop offset="1" stop-color="#38bdf8" stop-opacity=".12"/>
    </linearGradient>
  </defs>
    <rect width="900" height="280" rx="8" fill="#0d1117"/>
    <g stroke="#30363d" stroke-width="1">
    <path d="M56 42H860M56 89H860M56 136H860M56 183H860M56 230H860"/>
  </g>
  <path d="{area}" fill="url(#fill)"/>
    <path d="{line}" fill="none" stroke="#38bdf8" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
    <g fill="#38bdf8" stroke="#0d1117" stroke-width="2">{markers}</g>
    <g fill="#8b949e" font-family="Arial, sans-serif" font-size="12">
    {''.join(date_labels)}
    {y_labels}
  </g>
</svg>
'''


if __name__ == "__main__":
    dates, values = get_activity()
    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as graph_file:
        graph_file.write(make_svg(dates, values))
