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
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            email = data.get('email')
            otp = data.get('otp')
            new_password = data.get('new_password')
            
            if not email or not otp or not new_password:
                self.send_error_response(400, "Email, OTP, and new password are required")
                return
                
            db = get_db()
            user = db.users.find_one({"email": email})
            
            if not user:
                self.send_error_response(400, "Invalid or expired OTP")
                return
                
            # Check expiration
            exp = user.get('reset_otp_exp')
            if not exp or exp < datetime.datetime.utcnow():
                self.send_error_response(400, "Invalid or expired OTP")
                return
                
            # Verify OTP
            otp_hash = user.get('reset_otp_hash')
            if not otp_hash or not bcrypt.verify(otp, otp_hash):
                self.send_error_response(400, "Invalid or expired OTP")
                return
                
            # Reset password and clear OTP fields
            new_password_hash = bcrypt.hash(new_password)
            
            db.users.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {"password_hash": new_password_hash},
                    "$unset": {"reset_otp_hash": "", "reset_otp_exp": ""}
                }
            )
            
            self.send_success_response({"message": "Password reset successfully"})
                        
        except Exception as e:
            logger.exception("Error during password reset")
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
