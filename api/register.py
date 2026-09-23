import json
import os
import sys
from http.server import BaseHTTPRequestHandler


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db import get_db
from src.utils.logger import logger
from passlib.hash import bcrypt
import pymongo
from datetime import datetime

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
                
            password_hash = bcrypt.hash(password)
            db = get_db()
            
            try:
                new_user = {
                    "email": email,
                    "password_hash": password_hash,
                    "receive_emails": False,
                    "providers": {
                        "renac": {},
                        "shinemonitor": {}
                    },
                    "created_at": datetime.utcnow()
                }
                result = db.users.insert_one(new_user)
                user_id = str(result.inserted_id)
                
                self.send_success_response({"message": "User registered successfully", "user_id": user_id})
            except pymongo.errors.DuplicateKeyError:
                self.send_error_response(409, "Email already exists")
                        
        except Exception as e:
            logger.exception("Error during registration")
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
