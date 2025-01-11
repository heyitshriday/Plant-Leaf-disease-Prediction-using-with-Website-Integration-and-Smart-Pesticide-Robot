from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_mysqldb import MySQL
from flask_mail import Mail, Message
import requests
import re  # Import regex for parsing latitude and longitude
import json

app = Flask(__name__)

# Database configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'plant_disease_detection'


mysql = MySQL(app)


app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = '26.hridz@gmail.com'
app.config['MAIL_PASSWORD'] = 'hbad nffk ucym wfax'  # Use a secure method for production
app.config['MAIL_DEFAULT_SENDER'] = '26.hridz@gmail.com'


mail = Mail(app)


GOOGLE_API_KEY = 'AIzaSyCctAWoHT22LHoioefjMN6VPKa39xOHTeM'


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/server')
def server():

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, name, disease, google_maps_link FROM predictions")
    data = cursor.fetchall()
    cursor.close()
    return render_template('server.html', predictions=data)


@app.route('/view_stats')
def view_stats():

    stats = {
        "Early Blight": 0,
        "Late Blight": 0,
        "Healthy": 0
    }


    cursor = mysql.connection.cursor()
    cursor.execute("SELECT disease FROM predictions")  # Assuming the disease column contains the disease names
    diseases = cursor.fetchall()


    for disease in diseases:
        if disease[0] == "Early Blight":
            stats["Early Blight"] += 1
        elif disease[0] == "Late Blight":
            stats["Late Blight"] += 1
        elif disease[0] == "Healthy":
            stats["Healthy"] += 1

    cursor.close()


    return render_template('view_stats.html', stats=stats)


@app.route('/mapview')
def map_view():
    cursor = mysql.connection.cursor()

    cursor.execute("SELECT disease, google_maps_link FROM predictions")
    locations = cursor.fetchall()
    cursor.close()

    markers = []
    for location in locations:
        lat_lng = extract_lat_lng(location[1])
        if lat_lng:
            marker = {
                'lat': lat_lng['lat'],
                'lng': lat_lng['lng'],
                'disease': location[0]
            }
            markers.append(marker)


    return render_template('mapview.html', markers=json.dumps(markers))



@app.route('/send_email/<int:id>', methods=['POST'])
def send_email(id):
    # Fetch data for the selected row based on the ID
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT name, disease, google_maps_link FROM predictions WHERE id = %s", (id,))
    result = cursor.fetchone()
    cursor.close()

    email = result[0]  # This is the email (from `name` column)
    disease = result[1]
    google_maps_link = result[2]


    lat_lng = extract_lat_lng(google_maps_link)

    if lat_lng:

        shops = find_nearest_fertilizer_shops(lat_lng)

        if not shops:
            return "No fertilizer shops found."


        fertilizers = []
        if disease == "Early Blight":
            fertilizers = [
                "NPK Fertilizer (20:20:20)",
                "Calcium Nitrate",
                "Muriate of Potash (MOP)"
            ]
        elif disease == "Late Blight":
            fertilizers = [
                "Borax",
                "Di-ammonium Phosphate (DAP)",
                "Elemental Sulfur"
            ]
        elif disease == "Healthy":
            fertilizers = [
                "Vermicompost",
                "Chelated Micronutrient Mix",
                "Composted Cow Dung Manure"
            ]


        message_body = f"""Dear Farmer,

Your crops have been diagnosed with {disease}. I recommend using the following fertilizers:
{', '.join(fertilizers)}

Here are the nearest locations where you can purchase the recommended fertilizers:

{shops[0]['name']} - {shops[0]['google_maps_link']}
{shops[1]['name']} - {shops[1]['google_maps_link']}
{shops[2]['name']} - {shops[2]['google_maps_link']}

Best regards,
Plant Pixel Team
"""


        msg = Message('Fertilizer Recommendation', recipients=[email])
        msg.body = message_body

        try:
            mail.send(msg)
            return "Email sent successfully!"
        except Exception as e:
            return f"Failed to send email: {str(e)}"
    else:
        return "Failed to extract latitude and longitude."


def extract_lat_lng(google_maps_link):
    """Extract latitude and longitude from Google Maps link."""

    match = re.search(r"q=(-?\d+\.\d+),(-?\d+\.\d+)", google_maps_link)
    if match:
        return {
            'lat': float(match.group(1)),
            'lng': float(match.group(2))
        }
    else:
        print("Invalid Google Maps Link")
        return None


def find_nearest_fertilizer_shops(lat_lng):
    """Fetch fertilizer shops using the Google Places API."""
    places = fetch_fertilizer_shops_from_google_places_api(lat_lng)


    if 'results' not in places or not places['results']:
        print("No shops found in the API response")
        return []  # Return an empty list if no results are found

    shops = []
    try:

        for i in range(min(3, len(places['results']))):
            shop = places['results'][i]
            shop_name = shop.get('name', 'Unknown Shop')
            shop_location = shop.get('geometry', {}).get('location', {})
            lat = shop_location.get('lat', None)
            lng = shop_location.get('lng', None)
            google_maps_link = f"https://maps.google.com/?q={lat},{lng}" if lat and lng else "Location not available"


            shops.append({
                'name': shop_name,
                'google_maps_link': google_maps_link
            })

    except KeyError as e:
        print(f"Error accessing shop data: {e}")

    return shops


def fetch_fertilizer_shops_from_google_places_api(lat_lng):
    """Fetch fertilizer shops from Google Places API."""
    api_key = GOOGLE_API_KEY
    base_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"


    location = f"{lat_lng['lat']},{lat_lng['lng']}"
    radius = 20000
    keyword = "fertilizer shop"
    url = f"{base_url}?location={location}&radius={radius}&keyword={keyword}&key={api_key}"


    response = requests.get(url)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching shops: {response.status_code}")
        return {}


if __name__ == '__main__':
    app.run(debug=True)
