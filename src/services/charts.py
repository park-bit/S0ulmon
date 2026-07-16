import urllib.parse
from typing import Any

def generate_daily_yield_chart_url(renac_yield: float, shine_yield: float) -> str:
    """Generates a QuickChart.io URL for a beautiful daily yield bar chart."""
    total = renac_yield + shine_yield
    
    chart_config = {
        "type": "bar",
        "data": {
            "labels": ["Renac", "ShineMonitor"],
            "datasets": [
                {
                    "label": "Daily Yield (kWh)",
                    "data": [renac_yield, shine_yield],
                    "backgroundColor": ["rgba(54, 162, 235, 0.8)", "rgba(255, 159, 64, 0.8)"],
                    "borderColor": ["rgb(54, 162, 235)", "rgb(255, 159, 64)"],
                    "borderWidth": 1
                }
            ]
        },
        "options": {
            "plugins": {
                "title": {
                    "display": True,
                    "text": f"Today's Total Solar Generation: {total:.2f} kWh",
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
    
    # Convert dict to JSON string and URL encode it
    import json
    chart_json = json.dumps(chart_config)
    encoded_chart = urllib.parse.quote(chart_json)
    
    return f"https://quickchart.io/chart?w=600&h=400&c={encoded_chart}"
