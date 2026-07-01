#!/usr/bin/env python3
"""
Extract odds for FB0121
"""
import json, os, sys
match_id = "FB0121"
# Odds data extracted above for FB0121:

odds_closing = {
    "主客和": [
        {"selection": "哥倫比亞 (主隊勝)", "odds": 4.05},
        {"selection": "和", "odds": 3.55},
        {"selection": "葡萄牙 (客隊勝)", "odds": 1.65}
    ],
    "半場主客和": [
        {"selection": "哥倫比亞 (主隊勝)", "odds": 4.5},
        {"selection": "和", "odds": 2.32},
        {"selection": "葡萄牙 (客隊勝)", "odds": 2.1}
    ],
    "讓球": [
        {"line": "[+0.5/+1]", "odds": 1.84},
        {"line": "[-0.5/-1]", "odds": 1.96},
        {"line": "[0/+0.5]", "odds": 2.42},
        {"line": "[0/-0.5]", "odds": 1.55}
    ],
    "半場讓球": [
        {"line": "[0/+0.5]", "odds": 1.91},
        {"line": "[0/-0.5]", "odds": 1.81},
        {"line": "[0]", "odds": 2.88},
        {"line": "[0]", "odds": 1.37}
    ],
    "入球大細": [
        {"line": "[2.5]", "over_odds": 1.6, "under_odds": 2.19},
        {"line": "[2.5/3]", "over_odds": 1.76, "under_odds": 1.94},
        {"line": "[3/3.5]", "over_odds": 2.3, "under_odds": 1.54},
        {"line": "[3.5]", "over_odds": 2.6, "under_odds": 1.43},
        {"line": "[4.5]", "over_odds": 4.4, "under_odds": 1.15}
    ],
    "半場入球大細": [
        {"line": "[0.5/1]", "over_odds": 1.42, "under_odds": 2.62},
        {"line": "[1/1.5]", "over_odds": 2.0, "under_odds": 1.72},
        {"line": "[1.5]", "over_odds": 2.4, "under_odds": 1.5},
        {"line": "[1.5/2]", "over_odds": 3.05, "under_odds": 1.32}
    ],
    "開出角球大細": [
        {"line": "[8.5]", "over_odds": 1.71, "under_odds": 2.01},
        {"line": "[9.5]", "over_odds": 2.1, "under_odds": 1.65},
        {"line": "[10.5]", "over_odds": 2.58, "under_odds": 1.44},
        {"line": "[11.5]", "over_odds": 3.25, "under_odds": 1.28},
        {"line": "[12.5]", "over_odds": 4.3, "under_odds": 1.16}
    ],
    "半場開出角球大細": [
        {"line": "[4.5]", "over_odds": 2.1, "under_odds": 1.65},
        {"line": "[5.5]", "over_odds": 3.05, "under_odds": 1.32},
        {"line": "[6.5]", "over_odds": 4.3, "under_odds": 1.16},
        {"line": "[7.5]", "over_odds": 6.25, "under_odds": 1.07}
    ]
}

OUTPUT = "/mnt/d/openclaw/hkjc-football-agent/output/june-full-records.json"
from datetime import datetime as dt

# For now just print as JSON string
print(json.dumps({"match_id": match_id, "odds_closing": odds_closing}, ensure_ascii=False))
