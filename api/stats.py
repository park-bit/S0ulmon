import json
from http.server import BaseHTTPRequestHandler
import os
import sys
import jwt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db import get_db
from src.services.aggregator import SolarAggregator
from src.utils.logger import logger
from bson.objectid import ObjectId

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
                self.send_response(401)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": "Unauthorized"}).encode('utf-8'))
                return
                
            logger.info(f"Fetching stats for user {user['email']}.")
            
            # Fetch credentials
            renac_creds = {}
            shinemonitor_creds = {}
            
            db = get_db()
            user_data = db.users.find_one({"_id": ObjectId(user['user_id'])})
            if user_data and 'providers' in user_data:
                renac_creds = user_data['providers'].get('renac', {})
                shinemonitor_creds = user_data['providers'].get('shinemonitor', {})
            
            aggregator = SolarAggregator(
                renac_credentials=renac_creds,
                shinemonitor_credentials=shinemonitor_creds
            )
            aggregator.login_all()
            result = aggregator.fetch_all()
            
            # We want to return the full result (renac, shinemonitor, combined, errors)
            # instead of just "combined", so the frontend can render the grouped bar chart
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 's-maxage=60, stale-while-revalidate')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode('utf-8'))
            
        except Exception as e:
            logger.exception("Error fetching stats")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
