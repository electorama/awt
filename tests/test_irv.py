#!/usr/bin/env python3
"""
Test script for next choices feature in IRV analysis.
Uses Flask test client to simulate POST request with IRV data.
"""

from awt import app, cache
import json

def test_next_choices():
    """Test the next choices feature with a simple IRV example."""

    # Disable caching for clean test
    app.config['CACHE_TYPE'] = 'flask_caching.backends.NullCache'
    cache.init_app(app)

    client = app.test_client()

    # Simple test data with 3 candidates
    test_data = {
        'abifinput': '''{version: "0.1"}
{title: "Test Next Choices"}
Kiss:5
Montroll:4
Wright:3
Kiss:2
Montroll:5
Wright:1
Kiss:1
Montroll:2
Wright:6''',
        'include_IRV': 'yes',
        'include_irv_extra': 'yes'  # This enables next choices
    }

    print("Testing next choices with simple IRV data...")
    print("Input data:")
    print(test_data['abifinput'])
    print("\n" + "="*60 + "\n")

    # Make POST request
    response = client.post('/awt', data=test_data)

    if response.status_code == 200:
        html_content = response.data.decode('utf-8')

        # Extract just the IRV section for easier reading
        if 'Next choices if eliminated this round:' in html_content:
            print("✓ SUCCESS: Next choices feature is working!")

            # Find and display the IRV table section
            import re
            irv_match = re.search(r'<h2[^>]*>IRV.*?</table>', html_content, re.DOTALL | re.IGNORECASE)
            if irv_match:
                print("\nIRV Table with Next Choices:")
                print("-" * 50)
                # Clean up HTML for readable output
                irv_section = irv_match.group(0)
                irv_section = re.sub(r'<[^>]+>', ' ', irv_section)  # Remove HTML tags
                irv_section = re.sub(r'\s+', ' ', irv_section).strip()  # Normalize whitespace
                print(irv_section[:500] + "..." if len(irv_section) > 500 else irv_section)

        else:
            print("✗ FAILED: Next choices not found in output")
            print("Response preview:", html_content[:200] + "...")

    else:
        print(f"✗ FAILED: HTTP {response.status_code}")
        print("Response:", response.data.decode('utf-8')[:200])

if __name__ == "__main__":
    test_next_choices()
