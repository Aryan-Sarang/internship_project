import requests
import csv
import time

# Your API token
API_TOKEN = "b2f6eaa1d42b60cca22dff743a370685b22085b9"

# List of cities
cities = ['Ahmedabad', 'Aizawl', 'Amritsar', 'Bengaluru', 'Bhopal',
          'Brajrajnagar', 'Chandigarh', 'Chennai', 'Coimbatore', 'Delhi',
          'Guwahati', 'Hyderabad', 'Jaipur', 'Kolkata',
          'Lucknow', 'Mumbai', 'Patna', 'Shillong', 'Talcher', 'Thiruvananthapuram']

# Function to fetch and append air quality data for a given city
def fetch_and_append_data(city):
    url = f"https://api.waqi.info/feed/{city}/?token={API_TOKEN}"
    response = requests.get(url)
    data = response.json()

    if data["status"] == "ok":
        city_name = data["data"]["city"]["name"]
        iaqi = data["data"]["iaqi"]

        print(f"Air Quality Data for {city_name}:\n")

        pollutants = [pollutant.upper() for pollutant in iaqi.keys()]
        values = [value["v"] for value in iaqi.values()]

        with open("air_quality_data.csv", mode="a", newline="") as file:
            writer = csv.writer(file)
            if file.tell() == 0:
                writer.writerow(["City"] + pollutants)
            writer.writerow([city_name] + values)
    else:
        print(f"Error fetching data for {city}:", data.get("data", "Unknown error"))

# Run the function for each city every hour
while True:
    for city in cities:
        fetch_and_append_data(city)
    print("Data for all cities appended. Waiting for the next hour...")
    time.sleep(3600)  # Wait for 1 hour (3600 seconds) before fetching data again