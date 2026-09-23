import json
import os
import sys
import datetime
from http.server import BaseHTTPRequestHandler

import jwt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db import get_db
from src.utils.logger import logger
from src.utils.security import verify_password

JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-solar-key-change-me")

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            email = data.get('email')
            password = data.get('password')
            
            if not email or not password:
                self.send_error_response(400, "Email and password are required")
                return
                
            db = get_db()
            user = db.users.find_one({"email": email})
            
            if not user or not verify_password(password, user['password_hash']):
                self.send_error_response(401, "Invalid email or password")
                return
                
            # Generate JWT token
            payload = {
                "user_id": str(user['_id']),
                "email": email,
                "receive_emails": user.get('receive_emails', False),
                "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)
            }
            token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
            
            self.send_success_response({
                "message": "Login successful", 
                "token": token,
                "user": {
                    "id": str(user['_id']),
                    "email": email,
                    "receive_emails": user.get('receive_emails', False)
                }
            })
                        
        except Exception as e:
            logger.exception("Error during login")
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
