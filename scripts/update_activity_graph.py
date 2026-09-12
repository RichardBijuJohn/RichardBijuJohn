import json
import os
from datetime import datetime, timedelta, timezone
from html import escape
from urllib.request import Request, urlopen

USERNAME = os.environ.get("GITHUB_USERNAME", "RichardBijuJohn")
OUTPUT = "activity-graph.svg"
LANGUAGE_OUTPUT = "language-stats.svg"
DAYS = 31
EVENTS_URL = f"https://api.github.com/users/{USERNAME}/events/public"
REPOS_URL = f"https://api.github.com/users/{USERNAME}/repos"


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


def get_language_stats():
    totals = {}
    for page in range(1, 4):
        request = Request(
            f"{REPOS_URL}?per_page=100&page={page}&type=owner&sort=updated",
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "github-language-stats-updater",
            },
        )
        with urlopen(request, timeout=30) as response:
            repositories = json.load(response)
        if not repositories:
            break
        for repository in repositories:
            language_url = repository.get("languages_url")
            if not language_url:
                continue
            language_request = Request(
                language_url,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "github-language-stats-updater",
                },
            )
            with urlopen(language_request, timeout=30) as response:
                languages = json.load(response)
            for language, bytes_count in languages.items():
                totals[language] = totals.get(language, 0) + bytes_count
    return sorted(totals.items(), key=lambda item: item[1], reverse=True)[:6]


def make_language_svg(languages):
    palette = ["#38bdf8", "#f2cc60", "#a78bfa", "#34d399", "#fb7185", "#94a3b8"]
    total = sum(value for _, value in languages) or 1
    rows = []
    for index, (language, value) in enumerate(languages):
        percentage = value / total * 100
        y = 76 + index * 34
        rows.append(
            f'<text x="56" y="{y}" fill="#e2e8f0" font-family="Arial, sans-serif" font-size="14">{escape(language)}</text>'
            f'<rect x="190" y="{y - 13}" width="510" height="10" rx="5" fill="#273449"/>'
            f'<rect x="190" y="{y - 13}" width="{max(8, percentage * 5.1):.1f}" height="10" rx="5" fill="{palette[index]}"/>'
            f'<text x="742" y="{y}" fill="#94a3b8" font-family="Arial, sans-serif" font-size="13" text-anchor="end">{percentage:.1f}%</text>'
        )
    if not rows:
        rows.append('<text x="56" y="86" fill="#94a3b8" font-family="Arial, sans-serif" font-size="14">No public language data available</text>')

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 300" role="img" aria-labelledby="title desc">
  <title id="title">Programming language usage</title>
  <desc id="desc">A ranked view of programming languages used across public repositories.</desc>
  <rect width="800" height="300" rx="16" fill="#111827"/>
  <text x="56" y="32" fill="#f8fafc" font-family="Arial, sans-serif" font-size="15" font-weight="700" letter-spacing="1.5">PROGRAMMING LANGUAGES</text>
  <text x="56" y="52" fill="#64748b" font-family="Arial, sans-serif" font-size="11">PUBLIC REPOSITORIES / CODE DISTRIBUTION</text>
  {''.join(rows)}
  <path d="M56 275H744" stroke="#273449"/>
  <text x="56" y="290" fill="#64748b" font-family="Arial, sans-serif" font-size="10">Updated daily from GitHub repository data</text>
</svg>
'''


def make_svg(dates, values):
    maximum = max(values) or 1
    left, right, top, baseline = 56, 860, 42, 230
    step = (right - left) / (len(values) - 1)
    points = [
        (left + index * step, baseline - value / maximum * (baseline - top))
        for index, value in enumerate(values)
    ]
    line_parts = [f"M{points[0][0]:.1f} {points[0][1]:.1f}"]
    for index in range(len(points) - 1):
        previous = points[max(0, index - 1)]
        current = points[index]
        following = points[index + 1]
        next_following = points[min(len(points) - 1, index + 2)]
        control_one = (
            current[0] + (following[0] - previous[0]) / 6,
            current[1] + (following[1] - previous[1]) / 6,
        )
        control_two = (
            following[0] - (next_following[0] - current[0]) / 6,
            following[1] - (next_following[1] - current[1]) / 6,
        )
        line_parts.append(
            f"C{control_one[0]:.1f} {control_one[1]:.1f} "
            f"{control_two[0]:.1f} {control_two[1]:.1f} "
            f"{following[0]:.1f} {following[1]:.1f}"
        )
    line = " ".join(line_parts)
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
        <desc id="desc">A smooth area graph of daily GitHub activity from {escape(dates[0])} through {escape(dates[-1])}.</desc>
  <defs>
                <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0" stop-color="#fbbf24" stop-opacity=".88"/>
                        <stop offset="1" stop-color="#f97316" stop-opacity=".18"/>
    </linearGradient>
  </defs>
    <rect width="900" height="280" rx="16" fill="#1d2021"/>
        <text x="56" y="24" fill="#fbbf24" font-family="Arial, sans-serif" font-size="11" letter-spacing="1.5">ACTIVITY / LAST 31 DAYS</text>
    <g stroke="#3c3836" stroke-width="1">
        <path d="M56 42H860M56 89H860M56 136H860M56 183H860M56 230H860"/>
  </g>
        <path d="{area}" fill="url(#fill)"/>
        <path d="{line}" fill="none" stroke="#fbbf24" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
        <g fill="#fbbf24" stroke="#1d2021" stroke-width="2">{markers}</g>
    <g fill="#a89984" font-family="Arial, sans-serif" font-size="12">
    {''.join(date_labels)}
    {y_labels}
  </g>
</svg>
'''


if __name__ == "__main__":
    dates, values = get_activity()
    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as graph_file:
        graph_file.write(make_svg(dates, values))
    with open(LANGUAGE_OUTPUT, "w", encoding="utf-8", newline="\n") as language_file:
        language_file.write(make_language_svg(get_language_stats()))
