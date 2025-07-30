# Scoreholder Scraper
# Recieves a scoreholder url, and returns a json item

import cloudscraper
import requests
import json

def get_json_from_url(url):
    #create api-call url
    event_id = url.split('/')[-1] # get event id from url  
    https://public.scoreholder.com/events/cache/687c90444311e737811c0fd2.json
  
    api_url = f"https://public.scoreholder.com/events/cache/{event_id}?scope=PUBLIC"
    print(f"Calling Scoreholder API with cloudscraper: {api_url}")

    # cloudscraper instance
    scraper = cloudscraper.create_scraper(
        browser={ # You can try to mimic your browser
            'browser': 'chrome',
            'platform': 'windows', # or 'darwin' for macOS, 'linux'
            'mobile': False
        }
    )

    response_text_for_debugging = ""

    try:
        response = scraper.get(api_url, timeout=30)
        response_text_for_debugging = response.text

        print(f"API Response Status Code: {response.status_code}")
        response.raise_for_status()

        if response.status_code == 204:
            print("API returned status 204 No Content. Cannot parse JSON.")
            return None
        if not response.text.strip():
            print("API response text is empty or whitespace. Cannot parse JSON.")
            return None

        api_data = response.json()
        print("Successfully decoded JSON from Scoreholder API (via cloudscraper).")
        return api_data

    except requests.exceptions.HTTPError as http_err: # cloudscraper uses requests exceptions
        print(f"HTTP error occurred with API call: {http_err} from {api_url}")
        if http_err.response is not None:
            print(f"    Response Status Code: {http_err.response.status_code}")
            print(f"    Response Text: {http_err.response.text[:500]}")
    except requests.exceptions.Timeout:
        print(f"Request to API {api_url} timed out.")
    except requests.exceptions.RequestException as req_err:
        print(f"Error during API request to {api_url}: {req_err}")
    except json.JSONDecodeError as json_err:
        print(f"JSON decoding error from API response {api_url}: {json_err}")
        print(f"    Content that failed to decode (first 500 chars): {response_text_for_debugging[:500]}")
    except Exception as e: # Catch other potential cloudscraper-specific errors
        print(f"An unexpected error occurred with cloudscraper: {e}")
        print(f"    Content that may have caused it (first 500 chars): {response_text_for_debugging[:500]}")

    return None

if __name__ == "__main__":
    test_url = "https://scoreholder.com/en/events/6861cf0caa24a209c30a3e99"
    get_json_from_url(test_url)
