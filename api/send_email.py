import json
from http.server import BaseHTTPRequestHandler
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.aggregator import SolarAggregator
from src.services.notifier import default_notifier
from src.utils.logger import logger

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            logger.info("Manual Email Trigger from Dashboard.")
            aggregator = SolarAggregator()
            aggregator.login_all()
            result = aggregator.fetch_all()
            
            notifier = default_notifier()
            alerts = notifier.evaluate(result)
            
            response_data = {
                "status": "success",
                "alerts_triggered": len(alerts),
                "message": "Email sent successfully"
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
            
        except Exception as e:
            logger.exception("Error sending email")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
