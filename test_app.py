#!/usr/bin/env python3
"""
Simple test script to verify the application components
"""

import sys
import os

def test_imports():
    """Test that all required modules can be imported"""
    try:
        import flask
        print("✅ Flask imported successfully")
        
        import selenium
        print("✅ Selenium imported successfully")
        
        import pandas
        print("✅ Pandas imported successfully")
        
        import openpyxl
        print("✅ OpenPyXL imported successfully")
        
        from utils.scraper import stream_analysis
        print("✅ Scraper module imported successfully")
        
        from utils.excel_export import create_excel_report
        print("✅ Excel export module imported successfully")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_file_structure():
    """Test that all required files exist"""
    required_files = [
        'app.py',
        'requirements.txt',
        'Procfile',
        'static/css/styles.css',
        'static/js/app.js',
        'templates/base.html',
        'templates/index.html',
        'utils/__init__.py',
        'utils/scraper.py',
        'utils/excel_export.py'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
        else:
            print(f"✅ {file_path} exists")
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False
    
    return True

def test_app_creation():
    """Test that Flask app can be created"""
    try:
        from app import app
        print("✅ Flask app created successfully")
        
        # Test health endpoint
        with app.test_client() as client:
            response = client.get('/health')
            if response.status_code == 200:
                print("✅ Health endpoint working")
            else:
                print(f"❌ Health endpoint returned status {response.status_code}")
                return False
        
        return True
    except Exception as e:
        print(f"❌ App creation error: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Running application tests...\n")
    
    tests = [
        ("File Structure", test_file_structure),
        ("Module Imports", test_imports),
        ("App Creation", test_app_creation)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 Testing {test_name}...")
        if test_func():
            print(f"✅ {test_name} passed")
            passed += 1
        else:
            print(f"❌ {test_name} failed")
    
    print(f"\n🎯 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Application is ready for deployment.")
        return 0
    else:
        print("💥 Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
