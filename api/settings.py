import json
import os
import sys
from http.server import BaseHTTPRequestHandler

import jwt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db import get_db
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
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def do_GET(self):
        user = self.get_user_from_token()
        if not user:
            self.send_error_response(401, "Unauthorized")
            return
            
        try:
            db = get_db()
            user_data = db.users.find_one({"_id": ObjectId(user['user_id'])})
            
            if not user_data:
                self.send_error_response(404, "User not found")
                return
                
            result = {
                "receive_emails": user_data.get('receive_emails', False),
                "providers": user_data.get('providers', {
                    "renac": {},
                    "shinemonitor": {}
                })
            }
            self.send_success_response(result)
                    
        except Exception as e:
            logger.exception("Error fetching settings")
            self.send_error_response(500, str(e))

    def do_POST(self):
        user = self.get_user_from_token()
        if not user:
            self.send_error_response(401, "Unauthorized")
            return
            
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            receive_emails = data.get('receive_emails')
            providers = data.get('providers', {})
            
            db = get_db()
            update_fields = {}
            if receive_emails is not None:
                update_fields['receive_emails'] = receive_emails
            
            for provider in ["renac", "shinemonitor"]:
                if provider in providers:
                    update_fields[f'providers.{provider}'] = providers[provider]
                    
            if update_fields:
                db.users.update_one(
                    {"_id": ObjectId(user['user_id'])},
                    {"$set": update_fields}
                )
                
            self.send_success_response({"message": "Settings updated successfully"})
                
        except Exception as e:
            logger.exception("Error saving settings")
            self.send_error_response(500, str(e))

    def send_success_response(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "success", "data": data}).encode('utf-8'))

    def send_error_response(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "error", "message": message}).encode('utf-8'))
