import json
from http.server import BaseHTTPRequestHandler
import os
import sys
import datetime
import jwt
from bson.objectid import ObjectId

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db import get_db
from src.clients.renac import RenacClient
from src.clients.shinemonitor import ShineMonitorClient
from src.utils.logger import logger

JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-solar-key-change-me")

class handler(BaseHTTPRequestHandler):
    def get_user_from_token(self):
        auth_header = self.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        token = auth_header.split(' ')[1]
        try:
            return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None

    def do_GET(self):
        try:
            user = self.get_user_from_token()
            if not user:
                self.send_error_response(401, "Unauthorized")
                return

            db = get_db()
            user_data = db.users.find_one({"_id": ObjectId(user['user_id'])})
            providers = user_data.get('providers', {}) if user_data else {}
            
            renac_creds = providers.get('renac', {})
            sm_creds = providers.get('shinemonitor', {})

            today = datetime.datetime.now()
            # We fetch current month and previous 2 months (approx ~90 days)
            months_to_fetch = []
            for m_offset in range(3):
                # Calculate year and month
                y = today.year
                m = today.month - m_offset
                while m <= 0:
                    m += 12
                    y -= 1
                months_to_fetch.append((y, m))

            renac_history = {}
            if renac_creds.get('username') and renac_creds.get('password'):
                try:
                    r_client = RenacClient(
                        username=renac_creds.get('username'),
                        password=renac_creds.get('password'),
                        station_id=renac_creds.get('station_id')
                    )
                    r_client.login()
                    for y, m in months_to_fetch:
                        date_str = f"{y:04d}-{m:02d}-01"
                        m_hist = r_client.get_daily_yield_history(date_str)
                        renac_history.update(m_hist)
                    r_client.close()
                except Exception as e:
                    logger.warning(f"Heatmap Renac fetch failed: {e}")

            sm_history = {}
            if sm_creds.get('username') and sm_creds.get('password'):
                try:
                    sm_client = ShineMonitorClient(
                        username=sm_creds.get('username'),
                        password=sm_creds.get('password'),
                        company_key=sm_creds.get('company_key'),
                        plant_id=sm_creds.get('plant_id')
                    )
                    sm_client.login()
                    for y, m in months_to_fetch:
                        points = sm_client.queryPlantEnergyMonthPerDay(year=y, month=m)
                        for p in points:
                            d_str = p.date or (p.ts[:10] if p.ts else None)
                            val = p.energy if p.energy is not None else (float(p.val) if p.val is not None else 0.0)
                            if d_str:
                                sm_history[d_str] = float(val)
                    sm_client.close()
                except Exception as e:
                    logger.warning(f"Heatmap ShineMonitor fetch failed: {e}")

            # Merge days
            all_dates = set(renac_history.keys()) | set(sm_history.keys())
            
            # Filter up to past 90 days up to today
            start_date = (today - datetime.timedelta(days=90)).strftime('%Y-%m-%d')
            today_str = today.strftime('%Y-%m-%d')
            
            days_data = {}
            max_val = 0.0
            
            # Fill all days from start_date to today so the grid has no holes
            curr = today - datetime.timedelta(days=90)
            while curr <= today:
                d_key = curr.strftime('%Y-%m-%d')
                r_val = round(renac_history.get(d_key, 0.0), 2)
                s_val = round(sm_history.get(d_key, 0.0), 2)
                total = round(r_val + s_val, 2)
                if total > max_val:
                    max_val = total
                days_data[d_key] = {
                    "total": total,
                    "renac": r_val,
                    "shinemonitor": s_val
                }
                curr += datetime.timedelta(days=1)

            response_data = {
                "days": days_data,
                "max_kwh": max_val,
                "start_date": start_date,
                "end_date": today_str
            }

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 's-maxage=120, stale-while-revalidate')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "data": response_data}).encode('utf-8'))

        except Exception as e:
            logger.exception("Error in heatmap API")
            self.send_error_response(500, str(e))

    def send_error_response(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "error", "message": message}).encode('utf-8'))
