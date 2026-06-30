"""
AITHIYA - Artefact Protection System Dashboard
AI-Integrated Edition (TriVision Tech / WRO)

Setup:
    pip install flask requests

Run:
    python aithiya_dashboard.py

Then open:
    http://localhost:5000
"""

from flask import Flask, render_template_string, jsonify, request
import random
import requests
import json
import re
import os
from datetime import datetime
from collections import deque

app = Flask(__name__)

# ── Paste your Gemini API key here ───────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("AQ.Ab8RN6KIBelb3WiiW7u-4vVUTw0oBFy9DuADLSTkzX2Lyt-0Ng")

# ── Shared state ──────────────────────────────────────────────────────────────
alert_log = deque(maxlen=60)

systems = {
    "APS-01": {
        "name": "Vault Alpha",
        "location": "Gallery West",
        "artifact": "Roman pottery collection",
        "humidity": 58.0,
        "target_humidity": 55.0,
        "vapor_slot": "closed",
        "proximity": 4,
        "danger": 3,
        "sensors": [
            {"name": "IR motion array",     "val": "Nominal",  "lvl": "ok",     "needs_recal": False},
            {"name": "Temp sensor T-1",     "val": "22.4 C",   "lvl": "ok",     "needs_recal": False},
            {"name": "UV filter monitor",   "val": "Degraded", "lvl": "warn",   "needs_recal": True},
            {"name": "Vibration probe V-1", "val": "Nominal",  "lvl": "ok",     "needs_recal": False},
        ],
        "humidity_history": [55, 56, 57, 57, 58],
    },
    "APS-02": {
        "name": "Vault Beta",
        "location": "Gallery East",
        "artifact": "18th century oil paintings",
        "humidity": 74.0,
        "target_humidity": 55.0,
        "vapor_slot": "open",
        "proximity": 11,
        "danger": 7,
        "sensors": [
            {"name": "IR motion array",     "val": "Nominal",    "lvl": "ok",     "needs_recal": False},
            {"name": "Temp sensor T-2",     "val": "26.1 C",     "lvl": "warn",   "needs_recal": True},
            {"name": "Humidity probe H-2",  "val": "High drift", "lvl": "danger", "needs_recal": True},
            {"name": "Vibration probe V-2", "val": "Nominal",    "lvl": "ok",     "needs_recal": False},
        ],
        "humidity_history": [60, 64, 68, 71, 74],
    },
    "APS-03": {
        "name": "Vault Gamma",
        "location": "Conservation Lab",
        "artifact": "Viking iron coins & textile fragments",
        "humidity": 45.0,
        "target_humidity": 50.0,
        "vapor_slot": "closed",
        "proximity": 2,
        "danger": 1,
        "sensors": [
            {"name": "IR motion array",     "val": "Nominal", "lvl": "ok", "needs_recal": False},
            {"name": "Temp sensor T-3",     "val": "20.0 C",  "lvl": "ok", "needs_recal": False},
            {"name": "UV filter monitor",   "val": "Nominal", "lvl": "ok", "needs_recal": False},
            {"name": "Gas sensor G-3",      "val": "Nominal", "lvl": "ok", "needs_recal": False},
        ],
        "humidity_history": [50, 49, 48, 46, 45],
    },
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def severity(humidity, proximity, danger):
    if danger >= 7 or humidity > 70 or proximity > 10:
        return "danger"
    if danger >= 4 or humidity > 60 or proximity > 6:
        return "warn"
    return "ok"

def add_alert(node_id, level, message):
    alert_log.appendleft({
        "time": datetime.now().strftime("%H:%M:%S"),
        "node": node_id,
        "level": level,
        "message": message,
    })

def tick():
    for nid, s in systems.items():
        prev_sev = severity(s["humidity"], s["proximity"], s["danger"])

        if s["vapor_slot"] == "open" and s["humidity"] > s["target_humidity"]:
            drift = random.uniform(-1.2, 0.2)
        elif s["vapor_slot"] == "open" and s["humidity"] < s["target_humidity"]:
            drift = random.uniform(-0.2, 1.2)
        else:
            drift = random.uniform(-0.5, 0.5)

        s["humidity"] = round(max(20.0, min(95.0, s["humidity"] + drift)), 1)
        s["humidity_history"].append(s["humidity"])
        if len(s["humidity_history"]) > 10:
            s["humidity_history"].pop(0)

        if random.random() > 0.75:
            s["proximity"] = max(0, min(15, s["proximity"] + random.choice([-1, 0, 0, 1])))
        if random.random() > 0.88:
            s["danger"] = max(0, min(10, s["danger"] + random.choice([-1, 0, 1])))

        new_sev = severity(s["humidity"], s["proximity"], s["danger"])
        if prev_sev != new_sev:
            label = {"danger": "ELEVATED RISK", "warn": "CAUTION", "ok": "ALL CLEAR"}[new_sev]
            add_alert(nid, new_sev, f"{s['name']}: status changed to {label}")

        if s["humidity"] > 72:
            add_alert(nid, "warn", f"{s['name']}: humidity {s['humidity']}% exceeds safe threshold")
        if s["proximity"] > 10:
            add_alert(nid, "danger", f"{s['name']}: {s['proximity']} people in proximity zone")
        if s["danger"] >= 8:
            add_alert(nid, "danger", f"{s['name']}: danger level critical ({s['danger']}/10)")

# ── AI Route (Gemini) ─────────────────────────────────────────────────────────

@app.route("/api/ai-analyse", methods=["POST"])
def ai_analyse():
    body     = request.get_json()
    node_id  = body.get("node_id")
    user_msg = body.get("message", "Analyse this vault.")
    history  = body.get("history", [])

    if node_id not in systems:
        return jsonify({"error": "Node not found"}), 404

    s = systems[node_id]

    system_prompt = f"""You are AITHIYA-AI, an intelligent preservation analyst for the Smart Adaptive Artifact Preservation System built by TriVision Tech.

You monitor artefact vaults and help museum staff protect irreplaceable items.

Current vault: {node_id} - {s['name']} ({s['location']})
Artefact: {s['artifact']}
Current humidity: {s['humidity']}%
Target humidity: {s['target_humidity']}%
Vapor slot: {s['vapor_slot']}
Proximity (people nearby): {s['proximity']}
Danger level: {s['danger']}/10
Humidity trend (last readings): {s['humidity_history']}
Sensors: {json.dumps([{'name': x['name'], 'status': x['lvl'], 'value': x['val']} for x in s['sensors']])}

You can apply real actions by including these exact tags in your response:
- To set humidity: <action>{{"type":"set_humidity","value":52.0}}</action>
- To open vapor slot: <action>{{"type":"set_vapor_slot","state":"open"}}</action>
- To close vapor slot: <action>{{"type":"set_vapor_slot","state":"closed"}}</action>

Safe humidity ranges by artifact type:
- Pottery/ceramics: 45-55%
- Oil paintings: 50-60%
- Metals/coins: 35-45%
- Textiles: 45-55%

Provide complete, well-structured responses. Never stop in the middle of a sentence. Explain your reasoning before applying any action. If recommending an action, explain the current conditions, why the action is needed, and the expected result. Only include <action> tags when an actual control change should be made.
Reference the ESP32/DHT22/SG90 servo system from the WRO project when relevant.
"""

    gemini_contents = []
    for m in history:
        role = "user" if m["role"] == "user" else "model"
        gemini_contents.append({"role": role, "parts": [{"text": m["content"]}]})
    gemini_contents.append({"role": "user", "parts": [{"text": user_msg}]})

    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "contents": gemini_contents,
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048, "topP": 0.95, "topK": 40},
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        print(json.dumps(data, indent=2))

        candidate = data["candidates"][0]
        print("Finish reason:", candidate.get("finishReason"))

        parts = candidate["content"].get("parts", [])
        ai_text = "".join(part.get("text","") for part in parts)

        if not ai_text.strip():
            ai_text = "Gemini returned an empty response."
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    actions_applied = []
    for match in re.finditer(r"<action>(.*?)</action>", ai_text, re.DOTALL):
        try:
            act = json.loads(match.group(1))
            if act["type"] == "set_humidity":
                new_val = float(act["value"])
                old_val = s["humidity"]
                s["humidity"] = round(max(20.0, min(95.0, new_val)), 1)
                s["humidity_history"].append(s["humidity"])
                add_alert(node_id, "ok", f"AITHIYA-AI adjusted {s['name']} humidity: {old_val}% to {s['humidity']}%")
                actions_applied.append(f"Humidity set to {s['humidity']}%")
            elif act["type"] == "set_vapor_slot":
                state = act["state"]
                s["vapor_slot"] = state
                add_alert(node_id, "ok", f"AITHIYA-AI set vapor slot to {state} on {s['name']}")
                actions_applied.append(f"Vapor slot {state}")
        except Exception:
            pass

    clean_text = re.sub(r"<action>.*?</action>", "", ai_text, flags=re.DOTALL).strip()

    return jsonify({
        "reply": clean_text,
        "actions_applied": actions_applied,
        "updated_humidity": s["humidity"],
        "updated_vapor_slot": s["vapor_slot"],
    })

# ── Standard Routes ───────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/systems")
def api_systems():
    tick()
    return jsonify(systems)

@app.route("/api/alerts")
def api_alerts():
    return jsonify(list(alert_log))

@app.route("/api/recalibrate/<node_id>/<int:sensor_idx>", methods=["POST"])
def recalibrate(node_id, sensor_idx):
    if node_id not in systems:
        return jsonify({"error": "Node not found"}), 404
    sensor = systems[node_id]["sensors"][sensor_idx]
    sensor["needs_recal"] = False
    sensor["lvl"]         = "ok"
    sensor["val"]         = "Recalibrated"
    add_alert(node_id, "ok", f"{systems[node_id]['name']}: {sensor['name']} recalibrated successfully")
    return jsonify({"status": "ok"})

@app.route("/api/set-humidity/<node_id>", methods=["POST"])
def set_humidity(node_id):
    if node_id not in systems:
        return jsonify({"error": "Node not found"}), 404
    val = float(request.get_json().get("value", systems[node_id]["humidity"]))
    systems[node_id]["humidity"] = round(max(20.0, min(95.0, val)), 1)
    add_alert(node_id, "ok", f"{systems[node_id]['name']}: humidity manually set to {systems[node_id]['humidity']}%")
    return jsonify({"status": "ok", "humidity": systems[node_id]["humidity"]})

@app.route("/api/set-vapor/<node_id>", methods=["POST"])
def set_vapor(node_id):
    if node_id not in systems:
        return jsonify({"error": "Node not found"}), 404
    state = request.get_json().get("state", "closed")
    systems[node_id]["vapor_slot"] = state
    add_alert(node_id, "ok", f"{systems[node_id]['name']}: vapor slot manually set to {state}")
    return jsonify({"status": "ok"})

# ── HTML Template ─────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AITHIYA - Artefact Protection System</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg:      #0d0e10;
    --surface: #14161a;
    --surface2:#1a1d22;
    --surface3:#21242b;
    --border:  rgba(255,255,255,0.07);
    --border-med: rgba(255,255,255,0.14);
    --text:    #e6e6e0;
    --text2:   #8a8a84;
    --text3:   #52524e;
    --green: #20d68a; --green-bg: rgba(32,214,138,0.1); --green-text: #20d68a;
    --amber: #f5a623; --amber-bg: rgba(245,166,35,0.1); --amber-text: #f5a623;
    --red:   #f04f4f; --red-bg:   rgba(240,79,79,0.1);  --red-text:   #f04f4f;
    --blue:  #5b9ef5; --blue-bg:  rgba(91,158,245,0.1); --blue-text:  #5b9ef5;
    --mono: 'DM Mono', monospace; --sans: 'DM Sans', sans-serif;
    --radius: 10px; --radius-sm: 6px;
  }
  body { font-family: var(--sans); background: var(--bg); color: var(--text); min-height: 100vh; }
  .wrap { max-width: 1120px; margin: 0 auto; padding: 2rem 1.5rem; }

  .header { display: flex; align-items: center; gap: 1rem; margin-bottom: 0.3rem; }
  .logo { font-family: var(--mono); font-size: 2rem; font-weight: 500; letter-spacing: 0.2em; color: var(--text); }
  .sub  { font-size: 11px; letter-spacing: 0.12em; color: var(--text3); text-transform: uppercase; }
  .ai-badge { margin-left: auto; font-size: 10px; padding: 3px 10px; border-radius: 99px; background: var(--blue-bg); color: var(--blue-text); font-weight: 500; border: 0.5px solid rgba(91,158,245,0.25); letter-spacing: 0.04em; }
  hr.divider { border: none; border-top: 0.5px solid var(--border); margin: 1rem 0 1.75rem; }

  .section-label { font-size: 11px; letter-spacing: 0.1em; color: var(--text3); text-transform: uppercase; margin-bottom: 0.75rem; font-weight: 500; }
  .node-row { display: flex; align-items: stretch; margin-bottom: 1.75rem; }
  .node-card { flex: 1; border: 0.5px solid var(--border); border-radius: var(--radius); padding: 1rem 1.1rem; cursor: pointer; background: var(--surface); transition: border-color 0.18s, background 0.18s; }
  .node-card:hover { border-color: var(--border-med); background: var(--surface2); }
  .node-card.active { border-color: rgba(255,255,255,0.25); background: var(--surface2); }
  .node-card.active .dot { background: var(--green); box-shadow: 0 0 7px var(--green); }
  .node-head { display: flex; align-items: center; gap: 7px; margin-bottom: 3px; }
  .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--text3); transition: background 0.3s, box-shadow 0.3s; }
  .node-id       { font-family: var(--mono); font-size: 11px; color: var(--text3); }
  .node-name     { font-size: 13px; font-weight: 500; color: var(--text); }
  .node-loc      { font-size: 11px; color: var(--text2); margin-top: 1px; }
  .node-artifact { font-size: 10px; color: var(--text3); margin-top: 3px; font-style: italic; }
  .connector { display: flex; align-items: center; padding: 0 6px; }
  .conn-line { height: 0.5px; width: 18px; background: var(--border); }
  .conn-dot  { width: 5px; height: 5px; border-radius: 50%; background: var(--text3); }

  .main-grid { display: grid; grid-template-columns: 1fr 1fr 290px; gap: 12px; }

  .panel { background: var(--surface); border: 0.5px solid var(--border); border-radius: var(--radius); padding: 1.2rem; }
  .panel-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; flex-wrap: wrap; gap: 6px; }
  .panel-title { font-family: var(--mono); font-size: 12px; font-weight: 500; letter-spacing: 0.06em; color: var(--text); }
  .badge { font-size: 11px; padding: 3px 11px; border-radius: 99px; font-weight: 500; }
  .badge-ok     { background: var(--green-bg); color: var(--green-text); }
  .badge-warn   { background: var(--amber-bg); color: var(--amber-text); }
  .badge-danger { background: var(--red-bg);   color: var(--red-text);   }

  .metrics-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 8px; margin-bottom: 1rem; }
  .metric { background: var(--surface2); border-radius: var(--radius-sm); padding: 0.75rem 0.8rem; border: 0.5px solid var(--border); }
  .m-label { font-size: 10px; color: var(--text3); text-transform: uppercase; letter-spacing: 0.07em; margin-bottom: 5px; }
  .m-val  { font-family: var(--mono); font-size: 19px; font-weight: 500; color: var(--text); }
  .m-unit { font-size: 10px; color: var(--text3); margin-left: 2px; }
  .m-bar  { height: 2px; border-radius: 2px; background: var(--surface3); margin-top: 8px; overflow: hidden; }
  .m-fill { height: 100%; border-radius: 2px; transition: width 0.5s ease, background 0.5s; }
  .fill-ok     { background: var(--green); }
  .fill-warn   { background: var(--amber); }
  .fill-danger { background: var(--red);   }

  .ctrl-section { border-top: 0.5px solid var(--border); padding-top: 0.9rem; margin-bottom: 0.9rem; }
  .ctrl-hdr { font-size: 10px; color: var(--text3); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.7rem; }
  .ctrl-row { display: flex; align-items: center; gap: 8px; margin-bottom: 9px; }
  .ctrl-label { font-size: 11px; color: var(--text2); flex-shrink: 0; width: 100px; }
  .hum-slider { flex: 1; accent-color: var(--green); cursor: pointer; }
  .hum-val-disp { font-family: var(--mono); font-size: 12px; color: var(--text); flex-shrink: 0; width: 46px; text-align: right; }
  .apply-btn { font-size: 11px; padding: 3px 12px; border-radius: 99px; border: 0.5px solid var(--border-med); background: var(--surface3); cursor: pointer; font-family: var(--sans); color: var(--text); transition: all 0.15s; }
  .apply-btn:hover { background: var(--text); color: var(--bg); }
  .vapor-btn { font-size: 11px; padding: 3px 12px; border-radius: 99px; border: 0.5px solid var(--border-med); background: transparent; cursor: pointer; font-family: var(--sans); color: var(--text2); transition: all 0.15s; }
  .vapor-btn.active-open   { background: var(--green-bg); color: var(--green-text); border-color: var(--green); }
  .vapor-btn.active-closed { background: var(--surface3); color: var(--text);       border-color: var(--border-med); }

  .sensor-section { border-top: 0.5px solid var(--border); padding-top: 0.85rem; }
  .sensor-hdr { font-size: 10px; color: var(--text3); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.55rem; }
  .sensor-row { display: flex; align-items: center; justify-content: space-between; padding: 4px 0; font-size: 12px; }
  .s-left { display: flex; align-items: center; gap: 7px; }
  .s-dot  { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
  .s-dot.ok     { background: var(--green); }
  .s-dot.warn   { background: var(--amber); }
  .s-dot.danger { background: var(--red);   }
  .s-name { color: var(--text2); }
  .s-right { display: flex; align-items: center; gap: 8px; }
  .s-val  { font-family: var(--mono); font-size: 11px; color: var(--text); }
  .recal-btn { font-size: 11px; padding: 2px 9px; border-radius: 99px; border: 0.5px solid var(--border-med); background: transparent; cursor: pointer; color: var(--text2); font-family: var(--sans); transition: all 0.15s; }
  .recal-btn:hover { background: var(--surface3); color: var(--text); }
  .recal-btn.done    { background: var(--green-bg); color: var(--green-text); border-color: var(--green); }
  .recal-btn.running { background: var(--amber-bg); color: var(--amber-text); border-color: var(--amber); pointer-events: none; }

  .vapor-ind { font-family: var(--mono); font-size: 10px; padding: 2px 9px; border-radius: 99px; }
  .vapor-ind.open   { background: var(--green-bg); color: var(--green-text); }
  .vapor-ind.closed { background: var(--surface3); color: var(--text3); }

  .ai-panel { background: var(--surface); border: 0.5px solid var(--border); border-radius: var(--radius); padding: 1.2rem; display: flex; flex-direction: column; }
  .ai-panel-hdr { display: flex; align-items: center; gap: 8px; margin-bottom: 0.9rem; }
  .ai-dot   { width: 6px; height: 6px; border-radius: 50%; background: var(--blue); box-shadow: 0 0 6px var(--blue); flex-shrink: 0; }
  .ai-title { font-size: 11px; font-weight: 500; color: var(--text2); text-transform: uppercase; letter-spacing: 0.07em; }
  .chat-history { overflow-y: auto; max-height: 290px; display: flex; flex-direction: column; gap: 7px; margin-bottom: 9px; }
  .chat-msg { padding: 8px 10px; border-radius: var(--radius-sm); font-size: 12px; line-height: 1.55; }
  .chat-msg.user    { background: var(--surface3); color: var(--text); align-self: flex-end; max-width: 90%; border: 0.5px solid var(--border); }
  .chat-msg.ai      { background: var(--blue-bg);  color: var(--text); border: 0.5px solid rgba(91,158,245,0.15); }
  .chat-msg.action-applied { background: var(--green-bg); color: var(--green-text); font-size: 11px; font-family: var(--mono); border: 0.5px solid rgba(32,214,138,0.2); }
  .chat-msg.thinking { color: var(--text3); font-style: italic; }
  .quick-btns { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 8px; }
  .quick-btn { font-size: 10px; padding: 3px 9px; border-radius: 99px; border: 0.5px solid var(--border-med); background: transparent; cursor: pointer; color: var(--text2); font-family: var(--sans); transition: all 0.12s; white-space: nowrap; }
  .quick-btn:hover { background: var(--surface3); color: var(--text); }
  .ai-input-row { display: flex; gap: 6px; }
  .ai-input { flex: 1; font-size: 12px; padding: 7px 10px; border: 0.5px solid var(--border-med); border-radius: var(--radius-sm); background: var(--surface2); font-family: var(--sans); color: var(--text); outline: none; }
  .ai-input:focus { border-color: var(--blue); }
  .ai-input::placeholder { color: var(--text3); }
  .ai-send-btn { font-size: 12px; padding: 7px 14px; border-radius: var(--radius-sm); border: none; background: var(--blue); color: #fff; cursor: pointer; font-family: var(--sans); transition: opacity 0.15s; flex-shrink: 0; }
  .ai-send-btn:hover { opacity: 0.85; }
  .ai-send-btn:disabled { opacity: 0.35; pointer-events: none; }
  .no-node-msg { text-align: center; padding: 2rem 1rem; color: var(--text3); font-size: 12px; }

  .alert-panel { background: var(--surface); border: 0.5px solid var(--border); border-radius: var(--radius); padding: 1.2rem; }
  .alert-panel-hdr { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.85rem; }
  .alert-title { font-size: 11px; font-weight: 500; color: var(--text2); text-transform: uppercase; letter-spacing: 0.07em; }
  .alert-count { font-family: var(--mono); font-size: 11px; background: var(--surface3); border-radius: 99px; padding: 2px 8px; color: var(--text3); }
  .alert-list  { overflow-y: auto; max-height: 300px; display: flex; flex-direction: column; gap: 5px; }
  .alert-item  { display: flex; gap: 8px; align-items: flex-start; font-size: 11px; padding: 6px 8px; border-radius: var(--radius-sm); }
  .alert-item.danger { background: var(--red-bg);   border: 0.5px solid rgba(240,79,79,0.15); }
  .alert-item.warn   { background: var(--amber-bg); border: 0.5px solid rgba(245,166,35,0.15); }
  .alert-item.ok     { background: var(--green-bg); border: 0.5px solid rgba(32,214,138,0.15); }
  .a-dot  { width: 5px; height: 5px; border-radius: 50%; flex-shrink: 0; margin-top: 3px; }
  .alert-item.danger .a-dot { background: var(--red);   }
  .alert-item.warn   .a-dot { background: var(--amber); }
  .alert-item.ok     .a-dot { background: var(--green); }
  .a-time { font-family: var(--mono); font-size: 10px; color: var(--text3); flex-shrink: 0; }
  .a-node { font-family: var(--mono); font-size: 10px; flex-shrink: 0; }
  .alert-item.danger .a-node { color: var(--red-text);   }
  .alert-item.warn   .a-node { color: var(--amber-text); }
  .alert-item.ok     .a-node { color: var(--green-text); }
  .a-msg { color: var(--text2); line-height: 1.4; }
  .empty { text-align: center; padding: 2.5rem 1rem; color: var(--text3); font-size: 12px; border: 0.5px dashed var(--border); border-radius: var(--radius); }
</style>
</head>
<body>
<div class="wrap">

  <div class="header">
    <span class="logo">AITHIYA</span>
    <span class="sub">Artefact Protection System</span>
    <span class="ai-badge">AI + Manual Control</span>
  </div>
  <hr class="divider">

  <div class="section-label">Protection nodes — select to inspect</div>
  <div class="node-row">
    <div class="node-card" id="card-0" onclick="selectNode('APS-01')">
      <div class="node-head"><span class="dot"></span><span class="node-id">APS-01</span></div>
      <div class="node-name">Vault Alpha</div>
      <div class="node-loc">Gallery West</div>
      <div class="node-artifact">Roman pottery collection</div>
    </div>
    <div class="connector"><div class="conn-line"></div><div class="conn-dot"></div><div class="conn-line"></div></div>
    <div class="node-card" id="card-1" onclick="selectNode('APS-02')">
      <div class="node-head"><span class="dot"></span><span class="node-id">APS-02</span></div>
      <div class="node-name">Vault Beta</div>
      <div class="node-loc">Gallery East</div>
      <div class="node-artifact">18th century oil paintings</div>
    </div>
    <div class="connector"><div class="conn-line"></div><div class="conn-dot"></div><div class="conn-line"></div></div>
    <div class="node-card" id="card-2" onclick="selectNode('APS-03')">
      <div class="node-head"><span class="dot"></span><span class="node-id">APS-03</span></div>
      <div class="node-name">Vault Gamma</div>
      <div class="node-loc">Conservation Lab</div>
      <div class="node-artifact">Viking coins & textiles</div>
    </div>
  </div>

  <div class="main-grid">

    <!-- Left: sensors + manual controls -->
    <div style="display:flex;flex-direction:column;gap:12px;">
      <div id="empty-hint" class="empty">Select a protection node above to begin</div>
      <div id="detail-panel" style="display:none;">
        <div class="panel">
          <div class="panel-top">
            <span class="panel-title" id="p-title">-</span>
            <span class="vapor-ind" id="vapor-ind">-</span>
            <span class="badge" id="p-badge">-</span>
          </div>
          <div class="metrics-grid">
            <div class="metric">
              <div class="m-label">Humidity</div>
              <div><span class="m-val" id="m-hum">-</span><span class="m-unit">%</span></div>
              <div class="m-bar"><div class="m-fill" id="b-hum"></div></div>
            </div>
            <div class="metric">
              <div class="m-label">Proximity</div>
              <div><span class="m-val" id="m-prox">-</span><span class="m-unit">ppl</span></div>
              <div class="m-bar"><div class="m-fill" id="b-prox"></div></div>
            </div>
            <div class="metric">
              <div class="m-label">Danger level</div>
              <div><span class="m-val" id="m-dang">-</span><span class="m-unit">/10</span></div>
              <div class="m-bar"><div class="m-fill" id="b-dang"></div></div>
            </div>
          </div>

          <div class="ctrl-section">
            <div class="ctrl-hdr">Manual controls</div>
            <div class="ctrl-row">
              <span class="ctrl-label">Set humidity</span>
              <input type="range" class="hum-slider" id="hum-slider" min="20" max="90" step="0.5"
                oninput="document.getElementById('hum-disp').textContent=parseFloat(this.value).toFixed(1)+'%'">
              <span class="hum-val-disp" id="hum-disp">-</span>
              <button class="apply-btn" onclick="applyHumidity()">Apply</button>
            </div>
            <div class="ctrl-row">
              <span class="ctrl-label">Vapor slot</span>
              <button class="vapor-btn" id="vbtn-open"   onclick="setVapor('open')">Open</button>
              <button class="vapor-btn" id="vbtn-closed" onclick="setVapor('closed')">Closed</button>
            </div>
          </div>

          <div class="sensor-section">
            <div class="sensor-hdr">Sensor diagnostics</div>
            <div id="sensor-list"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Middle: AI analyst -->
    <div class="ai-panel">
      <div class="ai-panel-hdr">
        <span class="ai-dot"></span>
        <span class="ai-title">AITHIYA-AI Analyst</span>
      </div>
      <div id="no-node-msg" class="no-node-msg">Select a node to activate the AI analyst</div>
      <div id="ai-chat-area" style="display:none;flex-direction:column;flex:1;">
        <div class="chat-history" id="chat-history"></div>
        <div class="quick-btns">
          <button class="quick-btn" onclick="quickAsk('Analyse current conditions')">Analyse</button>
          <button class="quick-btn" onclick="quickAsk('Is humidity safe for this artifact?')">Check humidity</button>
          <button class="quick-btn" onclick="quickAsk('Should the vapor slot be open or closed right now?')">Vapor slot?</button>
          <button class="quick-btn" onclick="quickAsk('Predict risk for the next 24 hours based on the current trend')">Predict risk</button>
          <button class="quick-btn" onclick="quickAsk('Apply the optimal humidity level for this artifact type now')">Auto-correct</button>
        </div>
        <div class="ai-input-row">
          <input class="ai-input" id="ai-input" type="text" placeholder="Ask about this vault..."
            onkeydown="if(event.key==='Enter') sendAI()">
          <button class="ai-send-btn" id="ai-send-btn" onclick="sendAI()">Send</button>
        </div>
      </div>
    </div>

    <!-- Right: Alert log -->
    <div class="alert-panel">
      <div class="alert-panel-hdr">
        <span class="alert-title">Alert log</span>
        <span class="alert-count" id="alert-count">0</span>
      </div>
      <div class="alert-list" id="alert-list">
        <div style="color:var(--text3);font-size:11px;text-align:center;padding:1rem 0;">No alerts yet</div>
      </div>
    </div>

  </div>
</div>

<script>
let activeNode  = null;
let chatHistory = [];

function cls(h, p, d) {
  if (d >= 7 || h > 70 || p > 10) return 'danger';
  if (d >= 4 || h > 60 || p > 6)  return 'warn';
  return 'ok';
}
function fillCls(c)  { return 'fill-' + c; }
function badgeTxt(c) { return c==='danger'?'Elevated risk':c==='warn'?'Caution':'All clear'; }

function renderPanel(id, data) {
  const s  = data[id];
  const hc = s.humidity > 70 ? 'danger' : s.humidity > 60 ? 'warn' : 'ok';
  const pc = s.proximity > 10 ? 'danger' : s.proximity > 6 ? 'warn' : 'ok';
  const dc = s.danger >= 7 ? 'danger' : s.danger >= 4 ? 'warn' : 'ok';
  const ov = cls(s.humidity, s.proximity, s.danger);

  document.getElementById('p-title').textContent = id + ' - ' + s.name;
  const badge = document.getElementById('p-badge');
  badge.textContent = badgeTxt(ov); badge.className = 'badge badge-' + ov;

  const vi = document.getElementById('vapor-ind');
  vi.textContent = 'Vapor: ' + s.vapor_slot;
  vi.className = 'vapor-ind ' + s.vapor_slot;

  document.getElementById('m-hum').textContent  = parseFloat(s.humidity).toFixed(1);
  document.getElementById('m-prox').textContent = s.proximity;
  document.getElementById('m-dang').textContent = s.danger;

  setBar('b-hum',  s.humidity, hc);
  setBar('b-prox', Math.min(100, s.proximity * 7), pc);
  setBar('b-dang', s.danger * 10, dc);

  document.getElementById('hum-slider').value = s.humidity;
  document.getElementById('hum-disp').textContent = parseFloat(s.humidity).toFixed(1) + '%';

  document.getElementById('vbtn-open').className   = 'vapor-btn' + (s.vapor_slot==='open'   ? ' active-open'   : '');
  document.getElementById('vbtn-closed').className = 'vapor-btn' + (s.vapor_slot==='closed' ? ' active-closed' : '');

  const list = document.getElementById('sensor-list');
  list.innerHTML = '';
  s.sensors.forEach((sen, i) => {
    const row = document.createElement('div');
    row.className = 'sensor-row';
    const rb = sen.needs_recal
      ? `<button class="recal-btn" onclick="recalibrate('${id}',${i},this)">Recalibrate</button>` : '';
    row.innerHTML = `
      <span class="s-left"><span class="s-dot ${sen.lvl}"></span><span class="s-name">${sen.name}</span></span>
      <span class="s-right"><span class="s-val">${sen.val}</span>${rb}</span>`;
    list.appendChild(row);
  });
}

function setBar(id, pct, colorCls) {
  const el = document.getElementById(id);
  el.style.width = Math.min(100, pct) + '%';
  el.className   = 'm-fill ' + fillCls(colorCls);
}

function renderAlerts(alerts) {
  const list = document.getElementById('alert-list');
  document.getElementById('alert-count').textContent = alerts.length;
  if (!alerts.length) {
    list.innerHTML = '<div style="color:var(--text3);font-size:11px;text-align:center;padding:1rem 0;">No alerts yet</div>';
    return;
  }
  list.innerHTML = alerts.map(a => `
    <div class="alert-item ${a.level}">
      <span class="a-dot"></span>
      <span class="a-time">${a.time}</span>
      <span class="a-node">${a.node}</span>
      <span class="a-msg">${a.message}</span>
    </div>`).join('');
}

function selectNode(id) {
  ['APS-01','APS-02','APS-03'].forEach((nid, i) =>
    document.getElementById('card-' + i).classList.toggle('active', nid === id));
  activeNode  = id;
  chatHistory = [];
  document.getElementById('empty-hint').style.display   = 'none';
  document.getElementById('detail-panel').style.display = 'block';
  document.getElementById('no-node-msg').style.display  = 'none';
  document.getElementById('ai-chat-area').style.display = 'flex';
  document.getElementById('chat-history').innerHTML     = '';
  addBubble('ai', 'Vault selected. Ask me anything, or use the quick buttons above.');
  fetchAll();
}

function applyHumidity() {
  if (!activeNode) return;
  const val = document.getElementById('hum-slider').value;
  fetch('/api/set-humidity/' + activeNode, {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({value: parseFloat(val)})
  }).then(() => fetchAll());
}

function setVapor(state) {
  if (!activeNode) return;
  fetch('/api/set-vapor/' + activeNode, {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({state})
  }).then(() => fetchAll());
}

function recalibrate(nodeId, idx, btn) {
  btn.textContent = 'Recalibrating...'; btn.className = 'recal-btn running';
  fetch('/api/recalibrate/' + nodeId + '/' + idx, {method:'POST'})
    .then(() => { btn.textContent = 'Done'; btn.className = 'recal-btn done'; fetchAll(); });
}

function addBubble(role, text, extra) {
  const div = document.createElement('div');
  div.className = 'chat-msg ' + role + (extra ? ' ' + extra : '');
  div.textContent = text;
  const hist = document.getElementById('chat-history');
  hist.appendChild(div);
  hist.scrollTop = hist.scrollHeight;
  return div;
}

function quickAsk(q) {
  document.getElementById('ai-input').value = q;
  sendAI();
}

function sendAI() {
  if (!activeNode) return;
  const input = document.getElementById('ai-input');
  const msg   = input.value.trim();
  if (!msg) return;
  input.value = '';

  addBubble('user', msg);
  chatHistory.push({role:'user', content: msg});

  const btn      = document.getElementById('ai-send-btn');
  btn.disabled   = true;
  const thinking = addBubble('ai', 'Analysing...', 'thinking');

  fetch('/api/ai-analyse', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({node_id: activeNode, message: msg, history: chatHistory.slice(0,-1)})
  })
  .then(r => r.json())
  .then(data => {
    thinking.remove();
    if (data.error) {
      addBubble('ai', 'Error: ' + data.error);
    } else {
      addBubble('ai', data.reply);
      chatHistory.push({role:'assistant', content: data.reply});
      if (data.actions_applied && data.actions_applied.length)
        data.actions_applied.forEach(a => addBubble('ai', 'Applied: ' + a, 'action-applied'));
      fetchAll();
    }
    btn.disabled = false;
  })
  .catch(() => {
    thinking.remove();
    addBubble('ai', 'Connection error. Check your Gemini API key in the Python file.');
    btn.disabled = false;
  });
}

function fetchAll() {
  fetch('/api/systems').then(r => r.json()).then(data => {
    if (activeNode) renderPanel(activeNode, data);
  });
  fetch('/api/alerts').then(r => r.json()).then(renderAlerts);
}

setInterval(fetchAll, 3000);
fetchAll();
</script>
</body>
</html>
"""

# ── Seed startup alerts ───────────────────────────────────────────────────────
add_alert("APS-02", "danger", "Vault Beta: humidity probe H-2 high drift - recalibration needed")
add_alert("APS-02", "warn",   "Vault Beta: temp sensor T-2 above threshold (26.1 C)")
add_alert("APS-01", "warn",   "Vault Alpha: UV filter monitor degraded")
add_alert("APS-02", "danger", "Vault Beta: danger level elevated (7/10)")

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n  AITHIYA - Artefact Protection System")
    print("  ----------------------------------------")

    if not GEMINI_API_KEY:
        print("  ! GEMINI_API_KEY environment variable is not set.")
        print("    Add it in Render under:")
        print("    Environment -> GEMINI_API_KEY")

    print("  Server: http://localhost:5000")
    print("  Press Ctrl+C to stop.\n")

    app.run(host="0.0.0.0", port=5000, debug=False)