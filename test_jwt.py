#!/usr/bin/env python3
"""
Test script for JWT authentication system
"""
import requests
import json

BASE_URL = "http://127.0.0.1:5001"

def test_jwt_auth():
    print("🧪 Testing JWT Authentication System")
    print("=" * 50)
    
    # Test 1: Login
    print("\n1. Testing Login...")
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Login successful!")
            print(f"Access Token: {data['access_token'][:50]}...")
            print(f"User: {data['user']['username']} ({data['user']['role']})")
            
            # Store tokens for next tests
            access_token = data['access_token']
            refresh_token = data['refresh_token']
            
            # Test 2: Verify token
            print("\n2. Testing Token Verification...")
            headers = {"Authorization": f"Bearer {access_token}"}
            verify_response = requests.get(f"{BASE_URL}/api/auth/verify", headers=headers)
            print(f"Status Code: {verify_response.status_code}")
            
            if verify_response.status_code == 200:
                print("✅ Token verification successful!")
            else:
                print("❌ Token verification failed")
                print(verify_response.text)
            
            # Test 3: Access protected route (HR)
            print("\n3. Testing Protected Route Access...")
            hr_response = requests.get(f"{BASE_URL}/api/workers", headers=headers)
            print(f"Status Code: {hr_response.status_code}")
            
            if hr_response.status_code == 200:
                print("✅ Protected route access successful!")
            else:
                print("❌ Protected route access failed")
                print(hr_response.text)
            
            # Test 4: Refresh token
            print("\n4. Testing Token Refresh...")
            refresh_headers = {"Authorization": f"Bearer {refresh_token}"}
            refresh_response = requests.post(f"{BASE_URL}/api/auth/refresh", headers=refresh_headers)
            print(f"Status Code: {refresh_response.status_code}")
            
            if refresh_response.status_code == 200:
                print("✅ Token refresh successful!")
            else:
                print("❌ Token refresh failed")
                print(refresh_response.text)
                
        else:
            print("❌ Login failed")
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure Flask app is running on port 5001")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_jwt_auth()
