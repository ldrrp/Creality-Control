#!/usr/bin/env python3
"""
Simple test to verify the endpoint is working
"""

import asyncio
import aiohttp
import json

ENDPOINT_URL = "https://faas-nyc1-2ef2e6cc.doserverless.co/api/v1/web/fn-21a02825-e6a2-4937-96fc-5aa2163df723/v1/creality-control"

async def test_endpoint():
    """Test the endpoint with simple data."""
    print("Testing endpoint...")
    
    test_data = {
        "data": {
            "test": "data",
            "timestamp": 1234567890
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                ENDPOINT_URL,
                json=test_data,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                print(f"Status: {response.status}")
                text = await response.text()
                print(f"Response: {text}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_endpoint())
