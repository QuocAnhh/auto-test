#!/usr/bin/env python3
"""
Mock API Server for testing Prompt Suggestions functionality
"""

import json
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from busqa.prompt_doctor import analyze_prompt_suggestions
from busqa.brand_specs import get_available_brands


class MockAPIHandler(BaseHTTPRequestHandler):
    """Mock API handler for testing"""
    
    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/configs/brands':
            # Return available brands
            brands = get_available_brands()
            response = {"brands": brands}
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            
        elif parsed_path.path == '/health':
            # Health check
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy"}).encode())
            
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/analyze/prompt-suggestions':
            # Handle prompt suggestions analysis
            try:
                # Read request body
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                request_data = json.loads(post_data.decode('utf-8'))
                
                # Extract data
                brand_id = request_data.get('brand_id')
                evaluation_summary = request_data.get('evaluation_summary', {})
                
                if not brand_id:
                    raise ValueError("brand_id is required")
                
                # Load brand prompt
                brand_prompt_path = f"brands/{brand_id}/prompt.md"
                try:
                    with open(brand_prompt_path, 'r', encoding='utf-8') as f:
                        brand_prompt = f.read()
                except FileNotFoundError:
                    raise ValueError(f"Brand prompt not found: {brand_id}")
                
                # Run analysis
                result = asyncio.run(analyze_prompt_suggestions(
                    evaluation_summary=evaluation_summary,
                    current_prompt=brand_prompt,
                    brand_policy=""
                ))
                
                # Return response
                response = {
                    "brand_id": brand_id,
                    "analysis": result,
                    "timestamp": "2024-01-01T00:00:00Z"
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(response, ensure_ascii=False).encode())
                
            except Exception as e:
                # Return error response
                error_response = {
                    "error": str(e),
                    "message": "Analysis failed"
                }
                
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(error_response).encode())
                
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


def run_mock_server(port=8000):
    """Run the mock API server"""
    server_address = ('', port)
    httpd = HTTPServer(server_address, MockAPIHandler)
    print(f"🚀 Mock API Server running on http://localhost:{port}")
    print("📋 Available endpoints:")
    print("  - GET  /configs/brands")
    print("  - GET  /health")
    print("  - POST /analyze/prompt-suggestions")
    print("\nPress Ctrl+C to stop the server")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
        httpd.server_close()


if __name__ == "__main__":
    run_mock_server()
