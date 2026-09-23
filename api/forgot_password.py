import json
import os
import sys
import datetime
import random
import smtplib
from http.server import BaseHTTPRequestHandler
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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
            
            if not email:
                self.send_error_response(400, "Email is required")
                return
                
            db = get_db()
            user = db.users.find_one({"email": email})
            
            if not user:
                # To prevent email enumeration, return success even if user not found
                self.send_success_response({"message": "If the email is registered, an OTP has been sent."})
                return
                
            # Generate 6-digit OTP
            otp = f"{random.SystemRandom().randrange(100000, 999999)}"
            otp_hash = bcrypt.hash(otp)
            exp_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
            
            # Store in DB
            db.users.update_one(
                {"_id": user["_id"]},
                {"$set": {
                    "reset_otp_hash": otp_hash,
                    "reset_otp_exp": exp_time
                }}
            )
            
            # Send Email
            self.send_otp_email(email, otp)
            
            self.send_success_response({"message": "If the email is registered, an OTP has been sent."})
                        
        except Exception as e:
            logger.exception("Error during forgot password")
            self.send_error_response(500, str(e))

    def send_otp_email(self, to_email, otp):
        smtp_host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
        smtp_port = int(os.environ.get('SMTP_PORT', 587))
        smtp_user = os.environ.get('SMTP_USERNAME')
        smtp_pass = os.environ.get('SMTP_PASSWORD')
        
        if not smtp_user or not smtp_pass:
            logger.warning("SMTP credentials not configured. OTP generated but not sent.")
            return

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Password Reset OTP - Solar Monitor"
        msg["From"] = smtp_user
        msg["To"] = to_email

        text = f"Your password reset OTP is: {otp}\n\nThis code will expire in 10 minutes."
        html = f"""
        <html>
          <body>
            <h2>Password Reset</h2>
            <p>Your OTP is: <strong>{otp}</strong></p>
            <p>This code will expire in 10 minutes. If you did not request this, please ignore this email.</p>
          </body>
        </html>
        """
        
        msg.attach(MIMEText(text, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.sendmail(msg["From"], [to_email], msg.as_string())
            
        logger.info(f"OTP sent to {to_email}")

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
