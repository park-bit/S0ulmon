import urllib.parse
from typing import Any

def generate_weekly_trend_chart_url(history: dict[str, float]) -> str:
    """Generates a QuickChart.io URL for a 7-day weekly trend bar chart.
    history is a dict mapping 'YYYY-MM-DD' to kWh yield.
    """
    # Sort history chronologically
    sorted_dates = sorted(history.keys())
    labels = []
    data = []
    for d in sorted_dates:
        # Just show "Mon 15", "Tue 16"
        import datetime
        dt = datetime.datetime.strptime(d, "%Y-%m-%d")
        labels.append(dt.strftime("%a %d"))
        data.append(round(history[d], 2))

    chart_config = {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Total Yield (kWh)",
                    "data": data,
                    "backgroundColor": "rgba(54, 162, 235, 0.8)",
                    "borderColor": "rgb(54, 162, 235)",
                    "borderWidth": 1
                }
            ]
        },
        "options": {
            "plugins": {
                "title": {
                    "display": True,
                    "text": "7-Day Generation Trend",
                    "font": {"size": 18}
                },
                "datalabels": {
                    "anchor": "end",
                    "align": "top",
                    "font": {"size": 14, "weight": "bold"}
                }
            },
            "scales": {
                "y": {
                    "beginAtZero": True,
                    "title": {"display": True, "text": "kWh"}
                }
            }
        }
    }
    
    import json
    chart_json = json.dumps(chart_config)
    encoded_chart = urllib.parse.quote(chart_json)
    
    return f"https://quickchart.io/chart?w=600&h=400&c={encoded_chart}"
