import json
import os
import sys
import datetime
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db import get_db
from src.utils.logger import logger
from passlib.hash import bcrypt

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            db = get_db()
            
            email = "parthbhuskade1@gmail.com"
            password_hash = bcrypt.hash("P4rth#V4l")
            
            providers = {
                "renac": {
                    "username": "parthbhuskadeofficial@gmail.com",
                    "password": "P4rthV4l",
                    "station_id": "149199"
                },
                "shinemonitor": {
                    "username": "PravinBhuskade",
                    "password": "Parth#135",
                    "company_key": "bnrl_frRFjEz8Mkn",
                    "plant_id": "1301951"
                }
            }
            
            user = db.users.find_one({"email": email})
            
            if user:
                db.users.update_one(
                    {"email": email},
                    {"$set": {
                        "password_hash": password_hash,
                        "providers": providers
                    }}
                )
                msg = "Admin account updated successfully."
            else:
                db.users.insert_one({
                    "email": email,
                    "password_hash": password_hash,
                    "receive_emails": True,
                    "providers": providers,
                    "created_at": datetime.datetime.utcnow()
                })
                msg = "Admin account created successfully."
                
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "message": msg}).encode('utf-8'))
                        
        except Exception as e:
            logger.exception("Error during admin setup")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
