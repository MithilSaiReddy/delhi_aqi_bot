import requests
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import os
import tweepy
from dotenv import load_dotenv

load_dotenv()


# =========================
# CONFIG
# =========================
API_KEY = os.getenv("DATA_API_KEY")
#RESOURCE_ID = os.getenv("DATA_RESOURCE_ID")
FONT = "OpenSans-VariableFont_wdth,wght.ttf"
IMG_SIZE = (800, 800)
BG_COLOR = "#020617"  # dark slate
TEXT_LIGHT = "#e5e7eb"

# =========================
# AQI COLOR LOGIC
# =========================
def aqi_style(aqi):
    """Return color and status based on AQI value"""
    if aqi <= 50:
        return ("#10b981", "GOOD")
    elif aqi <= 100:
        return ("#84cc16", "SATISFACTORY")
    elif aqi <= 200:
        return ("#f59e0b", "MODERATE")
    elif aqi <= 300:
        return ("#f97316", "POOR")
    elif aqi <= 400:
        return ("#ef4444", "VERY POOR")
    else:
        return ("#dc2626", "SEVERE")
def fetch_delhi_aqi():
    headers = {
        "accept": "application/json",
    }

    params = {
        "api-key": API_KEY,
        "format": "json",
        "limit": 200,
        #"filters[state]": "Karnataka"
        "filters[state]": "Delhi",
    }

    response = requests.get(
        "https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69",
        params=params,
        headers=headers,
        timeout=10
    )
    response.raise_for_status()

    records = response.json().get("records", [])
    if not records:
        raise ValueError("No records returned")

    stations = {}

    for r in records:
        station = r.get("station")
        pollutant = r.get("pollutant_id")
        avg = r.get("max_value")

        if not station or avg in (None, "NA"):
            continue

        try:
            avg = float(avg)
        except ValueError:
            continue

        if station not in stations or avg > stations[station]["aqi"]:
            stations[station] = {
                "aqi": avg,
                "pollutant": pollutant,
            }

    if not stations:
        raise ValueError("No valid station AQI data")

    # Delhi average AQI
    avg_aqi = round(sum(s["aqi"] for s in stations.values()) / len(stations))

    # Top 5 worst stations
    top5 = sorted(
        stations.items(),
        key=lambda x: x[1]["aqi"],
        reverse=True
    )[:5]

    return avg_aqi, top5

# =========================
# IMAGE GENERATION
# =========================
def generate_image(avg_aqi, top5):
    color, status = aqi_style(avg_aqi)
    
    # Image dimensions - 1024x512 LANDSCAPE FORMAT
    IMG_SIZE = (1024, 512)
    PADDING = 40
    
    # Create base image
    img = Image.new("RGB", IMG_SIZE, "#3d2f28")
    draw = ImageDraw.Draw(img)
    
    # ... [Gradient and Border code remains the same as your original] ...

    # Load fonts (keeping your existing font logic)
    try:
        font_title = ImageFont.truetype(FONT, 34)
        font_aqi_num = ImageFont.truetype(FONT, 140)
        font_label = ImageFont.truetype(FONT, 22)
        font_status = ImageFont.truetype(FONT, 28)
        font_section = ImageFont.truetype(FONT, 22)
        font_list = ImageFont.truetype(FONT, 20)
        font_footer = ImageFont.truetype(FONT, 16)
    except:
        font_title = ImageFont.load_default()
        font_aqi_num = ImageFont.load_default()
        font_label = ImageFont.load_default()
        font_status = ImageFont.load_default()
        font_section = ImageFont.load_default()
        font_list = ImageFont.load_default()
        font_footer = ImageFont.load_default()

    # ===== LEFT SECTION: MAIN AQI =====
    left_x = PADDING + 10
    draw.text((left_x, 45), "DELHI AIR QUALITY", fill="#f1f5f9", font=font_title)

    # NEW LOGIC: Main AQI Text (Checks if value is 500 or more)
    aqi_text = f"{int(avg_aqi)}+" if avg_aqi >= 500 else str(int(avg_aqi))

    aqi_y = 120
    # Draw shadow/glow and main number using aqi_text
    for offset in range(2, 0, -1):
        glow_color = tuple(int(c * 0.3) for c in bytes.fromhex(color.lstrip('#')))
        draw.text((left_x+offset, aqi_y+offset), aqi_text, fill=glow_color, font=font_aqi_num)
    draw.text((left_x, aqi_y), aqi_text, fill=color, font=font_aqi_num)

    # Labels and Footer (same as before)
    draw.text((left_x, 290), "Average AQI", fill="#f1f5f9", font=font_label)
    draw.text((left_x, 325), status, fill=color, font=font_status)
    date = datetime.now().strftime("%d %b %Y").upper()
    draw.text((left_x, IMG_SIZE[1] - 50), f"{date} • CPCB", fill="#94a3b8", font=font_footer)

    # ===== RIGHT SECTION: TOP 5 WORST AREAS =====
    right_x = 570
    section_y = 160
    draw.text((right_x, section_y), "WORST AREAS TODAY", fill="#f1f5f9", font=font_section)

    list_y = section_y + 45
    line_height = 48

    for i, (station, data) in enumerate(top5, start=1):
        y_pos = list_y + i * line_height
        
        # Station Name
        draw.text((right_x, y_pos), f"{i}.", fill="#f59e0b", font=font_list)
        draw.text((right_x + 30, y_pos), station[:14], fill="#f1f5f9", font=font_list)

        # NEW LOGIC: Individual Station AQI Text
        station_val = data['aqi']
        display_val = f"{int(station_val)}+" if station_val >= 500 else f"{int(station_val)}"
        
        # Emoji logic
        indicator = "😷" if station_val >= 450 else " 🚗" if station_val > 400 else ""
        
        draw.text((right_x + 250, y_pos), f"{display_val}{indicator}", fill=color, font=font_list)

        # Pollutant
        pollutant = f"({data['pollutant']})" if 'pollutant' in data else ""
        draw.text((right_x + 340, y_pos), pollutant, fill="#94a3b8", font=font_list)

    # Save image
    filename = f"delhi_aqi_{datetime.now().strftime('%Y%m%d_%H%M')}.png"
    img.save(filename)
    return filename

def post_to_twitter(image_path, avg_aqi):
    # Load 4 Keys from Environment Variables
    consumer_key = os.getenv("X_API_KEY")          # API Key
    consumer_secret = os.getenv("X_API_SECRET")    # API Key Secret
    access_token = os.getenv("X_ACCESS_TOKEN")     # Access Token
    access_secret = os.getenv("X_ACCESS_TOKEN_SECRET") # Access Token Secret

    try:
        # 1. Authenticate to v1.1 (For Image Upload)
        auth = tweepy.OAuth1UserHandler(
            consumer_key, consumer_secret, access_token, access_secret
        )
        api = tweepy.API(auth)

        # 2. Authenticate to v2 (For Posting Tweet)
        client = tweepy.Client(
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            access_token=access_token,
            access_token_secret=access_secret
        )

        # 3. Upload Image (v1.1)
        print(f"Uploading {image_path}...")
        media = api.media_upload(filename=image_path)
        print(f"Media ID: {media.media_id}")

        # 4. Post Tweet (v2)
        print("Posting tweet...")
        tweet_text = f"Delhi AQI Update: {avg_aqi} 😷\n#DelhiPollution #AirQuality"
        
        response = client.create_tweet(
            text=tweet_text, 
            media_ids=[media.media_id]
        )
        
        print(f"Success! Tweet ID: {response.data['id']}")

    except Exception as e:
        print(f"Error Posting: {e}")
# =========================
# MAIN
# =========================
if __name__ == "__main__":
    try:
        # 1. Get Data
        print("Fetching AQI data...")
        avg_aqi, top5 = fetch_delhi_aqi()
        
        # 2. Generate Image
        print("Generating image...")
        img_file = generate_image(avg_aqi, top5)
        
        # 3. Post to Twitter
        post_to_twitter(img_file, avg_aqi)
        
    except Exception as e:
        print(f"Bot Failed: {e}")