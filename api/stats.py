import json
from http.server import BaseHTTPRequestHandler
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.aggregator import SolarAggregator
from src.utils.logger import logger

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            logger.info("Fetching stats for dashboard.")
            aggregator = SolarAggregator()
            aggregator.login_all()
            result = aggregator.fetch_all()
            
            combined_data = result.get("combined", {})
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 's-maxage=60, stale-while-revalidate')
            self.end_headers()
            self.wfile.write(json.dumps(combined_data).encode('utf-8'))
            
        except Exception as e:
            logger.exception("Error fetching stats")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
