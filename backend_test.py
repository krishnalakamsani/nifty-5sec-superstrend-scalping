#!/usr/bin/env python3
"""
NiftyAlgo Trading Bot - Backend API Testing
Tests all backend endpoints for the options trading bot
"""

import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any

class NiftyAlgoAPITester:
    def __init__(self, base_url="https://nifty-optionbot-2.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name: str, success: bool, details: str = "", response_data: Any = None):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
        
        result = {
            "test_name": name,
            "success": success,
            "details": details,
            "response_data": response_data,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")
        if details:
            print(f"    Details: {details}")
        if not success and response_data:
            print(f"    Response: {response_data}")
        print()

    def test_api_endpoint(self, method: str, endpoint: str, expected_status: int = 200, 
                         data: Dict = None, description: str = "") -> tuple:
        """Test a single API endpoint"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method.upper() == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            else:
                return False, f"Unsupported method: {method}", None

            success = response.status_code == expected_status
            
            if success:
                try:
                    response_data = response.json()
                except:
                    response_data = response.text
            else:
                response_data = {
                    "status_code": response.status_code,
                    "text": response.text[:200] + "..." if len(response.text) > 200 else response.text
                }
            
            details = f"Status: {response.status_code} (expected {expected_status})"
            if description:
                details = f"{description} - {details}"
                
            return success, details, response_data

        except requests.exceptions.RequestException as e:
            return False, f"Request failed: {str(e)}", None
        except Exception as e:
            return False, f"Unexpected error: {str(e)}", None

    def test_status_endpoint(self):
        """Test GET /api/status"""
        success, details, data = self.test_api_endpoint(
            'GET', 'status', 200, 
            description="Bot status endpoint"
        )
        
        if success and data:
            required_fields = ['is_running', 'mode', 'market_status', 'connection_status']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                success = False
                details += f" - Missing fields: {missing_fields}"
        
        self.log_test("GET /api/status", success, details, data)
        return success

    def test_config_endpoint(self):
        """Test GET /api/config"""
        success, details, data = self.test_api_endpoint(
            'GET', 'config', 200,
            description="Configuration endpoint"
        )
        
        if success and data:
            required_fields = ['order_qty', 'max_trades_per_day', 'daily_max_loss', 'has_credentials']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                success = False
                details += f" - Missing fields: {missing_fields}"
        
        self.log_test("GET /api/config", success, details, data)
        return success

    def test_config_update_endpoint(self):
        """Test POST /api/config/update"""
        test_config = {
            "order_qty": 50,
            "max_trades_per_day": 5,
            "daily_max_loss": 2000.0
        }
        
        success, details, data = self.test_api_endpoint(
            'POST', 'config/update', 200, test_config,
            description="Configuration update endpoint"
        )
        
        self.log_test("POST /api/config/update", success, details, data)
        return success

    def test_market_nifty_endpoint(self):
        """Test GET /api/market/nifty"""
        success, details, data = self.test_api_endpoint(
            'GET', 'market/nifty', 200,
            description="Nifty market data endpoint"
        )
        
        if success and data:
            required_fields = ['ltp', 'supertrend_signal', 'supertrend_value']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                success = False
                details += f" - Missing fields: {missing_fields}"
        
        self.log_test("GET /api/market/nifty", success, details, data)
        return success

    def test_position_endpoint(self):
        """Test GET /api/position"""
        success, details, data = self.test_api_endpoint(
            'GET', 'position', 200,
            description="Position endpoint"
        )
        
        if success and data:
            # Should have has_position field
            if 'has_position' not in data:
                success = False
                details += " - Missing 'has_position' field"
        
        self.log_test("GET /api/position", success, details, data)
        return success

    def test_trades_endpoint(self):
        """Test GET /api/trades"""
        success, details, data = self.test_api_endpoint(
            'GET', 'trades', 200,
            description="Trades endpoint"
        )
        
        if success and data:
            if not isinstance(data, list):
                success = False
                details += " - Response should be a list"
        
        self.log_test("GET /api/trades", success, details, data)
        return success

    def test_summary_endpoint(self):
        """Test GET /api/summary"""
        success, details, data = self.test_api_endpoint(
            'GET', 'summary', 200,
            description="Daily summary endpoint"
        )
        
        if success and data:
            required_fields = ['total_trades', 'total_pnl', 'max_drawdown', 'daily_stop_triggered']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                success = False
                details += f" - Missing fields: {missing_fields}"
        
        self.log_test("GET /api/summary", success, details, data)
        return success

    def test_logs_endpoint(self):
        """Test GET /api/logs"""
        success, details, data = self.test_api_endpoint(
            'GET', 'logs', 200,
            description="Logs endpoint"
        )
        
        if success and data:
            if not isinstance(data, list):
                success = False
                details += " - Response should be a list"
        
        self.log_test("GET /api/logs", success, details, data)
        return success

    def test_bot_control_endpoints(self):
        """Test bot control endpoints (start/stop/squareoff)"""
        # Test start bot
        success, details, data = self.test_api_endpoint(
            'POST', 'bot/start', 200,
            description="Start bot endpoint"
        )
        self.log_test("POST /api/bot/start", success, details, data)
        
        # Test stop bot
        success, details, data = self.test_api_endpoint(
            'POST', 'bot/stop', 200,
            description="Stop bot endpoint"
        )
        self.log_test("POST /api/bot/stop", success, details, data)
        
        # Test square off (might fail if no position)
        success, details, data = self.test_api_endpoint(
            'POST', 'bot/squareoff', 200,
            description="Square off endpoint"
        )
        # Don't fail the test if no position exists
        if not success and data and "No open position" in str(data):
            success = True
            details = "No position to square off (expected)"
        
        self.log_test("POST /api/bot/squareoff", success, details, data)

    def test_mode_endpoint(self):
        """Test POST /api/config/mode"""
        # Test paper mode
        success, details, data = self.test_api_endpoint(
            'POST', 'config/mode?mode=paper', 200,
            description="Set paper mode"
        )
        self.log_test("POST /api/config/mode (paper)", success, details, data)
        
        # Test live mode
        success, details, data = self.test_api_endpoint(
            'POST', 'config/mode?mode=live', 200,
            description="Set live mode"
        )
        self.log_test("POST /api/config/mode (live)", success, details, data)

    def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting NiftyAlgo Trading Bot API Tests")
        print(f"📡 Testing against: {self.base_url}")
        print("=" * 60)
        
        # Test all endpoints
        self.test_status_endpoint()
        self.test_config_endpoint()
        self.test_config_update_endpoint()
        self.test_market_nifty_endpoint()
        self.test_position_endpoint()
        self.test_trades_endpoint()
        self.test_summary_endpoint()
        self.test_logs_endpoint()
        self.test_bot_control_endpoints()
        self.test_mode_endpoint()
        
        # Print summary
        print("=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        print(f"📈 Success Rate: {success_rate:.1f}%")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return 0
        else:
            print("⚠️  Some tests failed. Check the details above.")
            return 1

def main():
    """Main test runner"""
    tester = NiftyAlgoAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())