from flask import Flask, render_template, request, jsonify, redirect, url_for
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import time
import matplotlib.dates as mdates
import numpy as np
from datetime import datetime, timedelta
import threading
from pytz import timezone
import plotly.graph_objects as go
import plotly.express as px
from collections import OrderedDict

# Add a lock for matplotlib operations
matplotlib_lock = threading.Lock()

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
GRAPH_FOLDER = "static/graphs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GRAPH_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["GRAPH_FOLDER"] = GRAPH_FOLDER

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/reset", methods=["GET"])
def reset_app():
    for folder in [UPLOAD_FOLDER, GRAPH_FOLDER]:
        for f in os.listdir(folder):
            file_path = os.path.join(folder, f)
            if os.path.isfile(file_path):
                os.remove(file_path)
    return redirect("/")

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "message": "No selected file"}), 400

    file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(file_path)

    try:
        process_file_and_generate_graphs(file_path)
        return jsonify({"success": True, "message": "File processed successfully."}), 200
    except Exception as e:
        print(f"Exception occurred: {e}")
        return jsonify({"success": False, "message": f"Error processing file: {str(e)}"}), 500

@app.route("/graphs")
def show_graphs():
    try:
        graph_files = sorted(
            [f for f in os.listdir(GRAPH_FOLDER) if f.endswith(".png")]
        )
        graph_urls = [url_for('static', filename=f'graphs/{f}') for f in graph_files]
        print("Graph Files:", graph_files)  # Debug
        print("Graph URLs:", graph_urls)  # Debug
        return render_template("graphs.html", graph_urls=graph_urls)
    except Exception as e:
        print(f"Error in /graphs route: {e}")
        return jsonify({"success": False, "message": str(e)})

@app.route("/delete_uploads", methods=["POST"])
def delete_uploads():
    try:
        for folder in [UPLOAD_FOLDER, GRAPH_FOLDER]:
            for file in os.listdir(folder):
                file_path = os.path.join(folder, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
        return jsonify({"success": True, "message": "Uploads and graphs deleted successfully"})
    except Exception as e:
        print(f"Error deleting files: {str(e)}")
        return jsonify({"success": False, "message": f"Error deleting files: {str(e)}"})

@app.route("/api/graph-data", methods=["GET"])
def get_graph_data():
    try:
        # Load the processed data from the latest uploaded file
        file_path = None
        for file in os.listdir(UPLOAD_FOLDER):
            file_path = os.path.join(UPLOAD_FOLDER, file)
            break

        if not file_path or not os.path.exists(file_path):
            return jsonify({"success": False, "message": "No uploaded file found."}), 404

        # Process the file to extract data
        adjusted_times, tokens, order_quantities, actions = [], [], [], []

        with open(file_path, "r", encoding="utf-8", errors="replace") as file:
            for line_num, line in enumerate(file, 1):
                print(f"Line {line_num}: {line.strip()}")  # Debug: Print each line
                columns = line.strip().split(",")
                if len(columns) < 8:
                    print(f"Skipping line {line_num}: Not enough columns")
                    continue
                try:
                    raw_epoch_time = int(columns[5])  # 7th value (index 6)
                    print(f"Raw Epoch Time: {raw_epoch_time}")  # Debug: Print raw epoch time
                    if raw_epoch_time > 1e18:
                        epoch_time = (raw_epoch_time + 315532800000000000) / 1e9
                    elif raw_epoch_time > 1e15:
                        epoch_time = (raw_epoch_time + 315532800000000) / 1e6
                    elif raw_epoch_time > 1e12:
                        epoch_time = (raw_epoch_time + 315532800000) / 1e3
                    else:
                        epoch_time = raw_epoch_time + 315532800

                    adjusted_time = pd.to_datetime(epoch_time, unit="s", origin="unix", utc=True)
                    adjusted_time = adjusted_time.tz_convert("Asia/Calcutta")
                    print(f"Adjusted Time: {adjusted_time}")  # Debug: Print adjusted time
                except (ValueError, IndexError) as e:
                    print(f"Error processing epoch time: {e}")  # Debug: Print error
                    continue

                token = columns[1].strip()  # Token (2nd value, index 1)
                order_quantity = float(columns[-1])  # Quantity (last value)
                action = columns[0].strip()  # Action (1st value, index 0)

                adjusted_times.append(adjusted_time)
                tokens.append(token)
                order_quantities.append(order_quantity)
                actions.append(action)

        # Create a DataFrame from the extracted data
        df = pd.DataFrame({
            "adjusted_time": adjusted_times,
            "token": tokens,
            "order_quantity": order_quantities,
            "action": actions
        })

        print("DataFrame Before Filtering:\n", df.head())  # Debug: Print the first few rows

        # Convert adjusted_time to datetime
        df["adjusted_time"] = pd.to_datetime(df["adjusted_time"], errors="coerce")
        print("Adjusted Time Conversion:\n", df["adjusted_time"].head())  # Debug: Check adjusted_time column
        df.dropna(subset=["adjusted_time"], inplace=True)
        print("DataFrame After Adjusted Time Filtering:\n", df.head())  # Debug: Check DataFrame after filtering

        # Convert order_quantity to numeric
        df["order_quantity"] = pd.to_numeric(df["order_quantity"], errors="coerce")
        print("Order Quantity Conversion:\n", df["order_quantity"].head())  # Debug: Check order_quantity column
        df.dropna(subset=["order_quantity"], inplace=True)
        print("DataFrame After Order Quantity Filtering:\n", df.head())  # Debug: Check DataFrame after filtering

        # Add an "hour" column for grouping by hour
        df["hour"] = df["adjusted_time"].dt.floor("H")

        # Prepare data for JSON response
        entries_per_hour = (
            df.groupby(df["adjusted_time"].dt.floor("H"))
            .size()
            .sort_index()  # Sort by time (left side)
            .to_dict()
        )
        quantity_per_hour = (
            df.groupby(df["adjusted_time"].dt.floor("H"))["order_quantity"]
            .sum()
            .sort_values(ascending=False)  # Sort by quantity (right side)
            .to_dict()
        )
        top_tokens_by_quantity = dict(
            df.groupby("token")["order_quantity"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )
        print("Top Tokens by Quantity Output:", top_tokens_by_quantity)  # Debug

        quantity_per_token = (
            df.groupby("token")["order_quantity"]
            .sum()
            .sort_values(ascending=False)  # Sort by quantity (right side)
            .to_dict()
        )

        graph_data = {
            "entries_per_hour": {str(k): v for k, v in entries_per_hour.items()},
            "quantity_per_hour": {str(k): v for k, v in quantity_per_hour.items()},
            "top_tokens_by_quantity": top_tokens_by_quantity,
            "quantity_per_token": quantity_per_token,
        }

        return jsonify({"success": True, "data": graph_data}), 200
    except Exception as e:
        print(f"Error in /api/graph-data: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

def create_plot(df, x_data, y_data, title, xlabel, ylabel, filename, color='#1f77b4', marker='o', 
                linewidth=2, label=None, legend_needed=False, more_series=None):
    """Thread-safe function to create a single plot and save it to disk with exact time labels"""
    with matplotlib_lock:
        # Always create a new figure for each plot
        plt.figure(figsize=(12, 6))
        
        # Plot main series
        plt.plot(x_data, y_data, marker=marker, color=color, linewidth=linewidth, label=label)
        
        # Annotate each point with its value
        for i, (x, y) in enumerate(zip(x_data, y_data)):
            plt.annotate(f"{y:.2f}", (x, y), textcoords="offset points", xytext=(0, 5), ha='center', fontsize=9)
        
        # Plot additional series if provided
        if more_series:
            for series in more_series:
                plt.plot(series['x'], series['y'], marker=series['marker'], color=series['color'], 
                        linewidth=series['linewidth'], label=series['label'])
                # Annotate additional series points
                for x, y in zip(series['x'], series['y']):
                    plt.annotate(f"{y:.2f}", (x, y), textcoords="offset points", xytext=(0, 5), ha='center', fontsize=9)
        
        # Add titles and labels
        plt.title(title, fontsize=14, fontweight='bold')
        plt.xlabel(xlabel, fontsize=12)
        plt.ylabel(ylabel, fontsize=12)
        
        # Get the actual x-axis values (datetime objects)
        ax = plt.gca()
        
        # Ensure x_data is localized to IST
        x_data = pd.to_datetime(x_data).tz_convert("Asia/Calcutta")
        
        # Debug: Print the x-axis data after localization
        print("X-Axis Data (Localized to IST):")
        print(x_data)
        
        # Set x-ticks to the actual time values from the data
        unique_hours = sorted(x_data.unique())
        
        # Debug: Print the unique hours
        print("Unique hours (x-axis tick values):")
        print(unique_hours)
        
        ax.set_xticks(unique_hours)  # Set the x-ticks to unique_hours
        ax.set_xticklabels([hour.strftime('%H:%M') for hour in unique_hours])  # Use unique_hours as labels
        
        # Ensure the DateFormatter aligns with the timezone
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M', tz=timezone('Asia/Calcutta')))
        
        # Set consistent x-axis limits with a small buffer
        if len(unique_hours) > 1:
            time_delta = (unique_hours[-1] - unique_hours[0]) * 0.05  # 5% buffer
            plt.xlim(unique_hours[0] - time_delta, unique_hours[-1] + time_delta)
        
        # Add grid
        plt.grid(True, linestyle="--", alpha=0.6)
        
        # Rotate labels slightly for better readability
        plt.setp(ax.get_xticklabels(), rotation=30, ha='right')
        
        # Add legend if needed
        if legend_needed:
            plt.legend(loc='best')
        
        # Adjust layout
        plt.tight_layout()
        
        # Save the figure and close it immediately
        plt.savefig(os.path.join(GRAPH_FOLDER, filename), dpi=100)
        plt.close()  # Important: close plot to free memory

def process_file_and_generate_graphs(file_path):
    start_time = time.time()
    adjusted_times, tokens, order_quantities, actions = [], [], [], []

    with open(file_path, "r", encoding="utf-8", errors="replace") as file:
        for line_num, line in enumerate(file, 1):
            print(f"Line {line_num}: {line.strip()}")  # Debug: Print each line
            columns = line.strip().split(",")
            if len(columns) < 8:
                print(f"Skipping line {line_num}: Not enough columns")
                continue
            try:
                raw_epoch_time = int(columns[5])
                token = columns[1].strip()
                order_quantity = float(columns[-1].strip())
                action = columns[0].strip()
            except (ValueError, IndexError) as e:
                print(f"Skipping line {line_num}: {e}")
                continue
            try:
                print(f"Columns: {columns}")  # Debug: Print split columns
                print(f"Raw Epoch Time: {raw_epoch_time}")  # Debug: Print raw epoch time
                if raw_epoch_time > 1e18:
                    epoch_time = (raw_epoch_time + 315532800000000000) / 1e9
                elif raw_epoch_time > 1e15:
                    epoch_time = (raw_epoch_time + 315532800000000) / 1e6
                elif raw_epoch_time > 1e12:
                    epoch_time = (raw_epoch_time + 315532800000) / 1e3
                else:
                    epoch_time = raw_epoch_time + 315532800

                adjusted_time = pd.to_datetime(epoch_time, unit="s", origin="unix", utc=True)
                adjusted_time = adjusted_time.tz_convert("Asia/Calcutta")
                print(f"Adjusted Time: {adjusted_time}")  # Debug: Print adjusted time

                print(f"Token: {token}")  # Debug

                print(f"Order Quantity: {order_quantity}")  # Debug

                print(f"Action: {action}")  # Debug

                adjusted_times.append(adjusted_time)
                tokens.append(token)
                order_quantities.append(order_quantity)
                actions.append(action)
            except (ValueError, IndexError) as e:
                print(f"Error processing line: {e}")  # Debug
                continue

    if not adjusted_times:
        print("Adjusted Times list is empty!")
    if not tokens:
        print("Tokens list is empty!")
    if not order_quantities:
        print("Order Quantities list is empty!")
    if not actions:
        print("Actions list is empty!")

    print("Adjusted Times:", adjusted_times[:10])  # Print the first 10 entries
    print("Tokens:", tokens[:10])  # Print the first 10 entries
    print("Order Quantities:", order_quantities[:10])  # Print the first 10 entries
    print("Actions:", actions[:10])  # Print the first 10 entries

    df = pd.DataFrame({
        "adjusted_time": adjusted_times,
        "token": tokens,
        "order_quantity": order_quantities,
        "action": actions
    })

    df["token"] = df["token"].astype(str).str.strip()
    df["order_quantity"] = pd.to_numeric(df["order_quantity"], errors="coerce")
    print("Order Quantity Conversion:\n", df["order_quantity"].head())  # Debug: Check order_quantity column
    df.dropna(subset=["order_quantity"], inplace=True)
    print("DataFrame After Order Quantity Filtering:\n", df.head())  # Debug: Check DataFrame after filtering
    df["adjusted_time"] = pd.to_datetime(df["adjusted_time"], errors="coerce")
    print("Adjusted Time Conversion:\n", df["adjusted_time"].head())  # Debug: Check adjusted_time column
    df.dropna(subset=["adjusted_time"], inplace=True)
    print("DataFrame After Adjusted Time Filtering:\n", df.head())  # Debug: Check DataFrame after filtering
    df["hour"] = df["adjusted_time"].dt.floor("H")

    entries_per_hour = df.groupby("hour").size()
    print("Entries Per Hour:\n", entries_per_hour)  # Debug: Print entries per hour

    quantity_per_hour = df.groupby("hour")["order_quantity"].sum()
    print("Quantity Per Hour:\n", quantity_per_hour)  # Debug: Print quantity per hour

    # Graph 1: Number of Entries per Hour
    entries_per_hour = df.groupby("hour").size()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=entries_per_hour.index, y=entries_per_hour.values, mode='lines+markers', name='Entries'))
    fig.update_layout(title="Number of Entries per Hour", xaxis_title="Time", yaxis_title="Number of Entries")
    fig.write_html(os.path.join(GRAPH_FOLDER, "entries_per_hour.html"))
    fig.write_image(os.path.join(GRAPH_FOLDER, "entries_per_hour.png"))

    # Graph 2: Total Order Quantity per Hour
    quantity_per_hour = df.groupby("hour")["order_quantity"].sum()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=quantity_per_hour.index, y=quantity_per_hour.values, mode='lines+markers', name='Quantity'))
    fig.update_layout(title="Total Order Quantity per Hour", xaxis_title="Time", yaxis_title="Total Order Quantity")
    fig.write_html(os.path.join(GRAPH_FOLDER, "order_quantity_per_hour.html"))
    fig.write_image(os.path.join(GRAPH_FOLDER, "order_quantity_per_hour.png"))

    # Graph 3: T to N/M Combination Count per Hour
    combo_hours = []
    for i in range(len(df) - 1):
        if df.iloc[i]["action"] == "T" and df.iloc[i + 1]["action"] in ["N", "M"]:
            combo_hours.append(df.iloc[i]["hour"])
    if combo_hours:
        combo_series = pd.Series(combo_hours).value_counts().sort_index()
        fig = go.Figure()
        fig.add_trace(go.Bar(x=combo_series.index, y=combo_series.values, name='T to N/M Combinations'))
        fig.update_layout(title="T to N/M Combination Count per Hour", xaxis_title="Time", yaxis_title="T to N/M Combinations")
        fig.write_html(os.path.join(GRAPH_FOLDER, "t_nm_combo_count_per_hour.html"))
        fig.write_image(os.path.join(GRAPH_FOLDER, "t_nm_combo_count_per_hour.png"))

    # Graph 4: Top 5 Tokens by Number of Orders Per Hour
    top_5_tokens = df["token"].value_counts().head(5).index.tolist()
    df_top_tokens = df[df["token"].isin(top_5_tokens)]
    if not df_top_tokens.empty:
        orders_per_hour = df_top_tokens.groupby(["hour", "token"]).size().unstack(fill_value=0).sort_index()
        fig = px.line(orders_per_hour, x=orders_per_hour.index, y=orders_per_hour.columns, title="Top 5 Tokens by Number of Orders Per Hour")
        fig.update_layout(xaxis_title="Time", yaxis_title="Number of Orders")
        fig.write_html(os.path.join(GRAPH_FOLDER, "top_5_tokens_orders_per_hour.html"))
        fig.write_image(os.path.join(GRAPH_FOLDER, "top_5_tokens_orders_per_hour.png"))

    # Graph 5: Top 5 Tokens by Quantity Traded per Hour
    top_5_qty_tokens = df.groupby("token")["order_quantity"].sum().nlargest(5).index.tolist()
    print("Top 5 Tokens by Quantity:", top_5_qty_tokens)  # Debug: Check top 5 tokens

    df_top_qty = df[df["token"].isin(top_5_qty_tokens)]
    print("DataFrame for Top 5 Tokens by Quantity:\n", df_top_qty.head())  # Debug: Check filtered DataFrame

    if not df_top_qty.empty:
        qty_per_hour = df_top_qty.groupby(["hour", "token"])["order_quantity"].sum().unstack(fill_value=0).sort_index()
        fig = px.line(qty_per_hour, x=qty_per_hour.index, y=qty_per_hour.columns, title="Top 5 Tokens by Total Quantity Per Hour")
        fig.update_layout(xaxis_title="Time", yaxis_title="Total Quantity")
        fig.write_html(os.path.join(GRAPH_FOLDER, "top_5_tokens_quantity_per_hour.html"))
        fig.write_image(os.path.join(GRAPH_FOLDER, "top_5_tokens_quantity_per_hour.png"))

    # Graph 6: Pie Chart of Number of Entries for Each Unique Token
    entries_per_token = df["token"].value_counts()
    print("Entries Per Token Before Grouping:\n", entries_per_token)  # Debug: Check raw data

    # Calculate the total number of entries
    total_entries = entries_per_token.sum()

    # Calculate percentages
    percentages = (entries_per_token / total_entries) * 100
    print("Percentages Per Token:\n", percentages)  # Debug: Check percentages

    # Separate tokens below 1% into "Others"
    above_threshold = percentages[percentages >= 1]
    below_threshold = percentages[percentages < 1]

    # Combine "Others" category
    if not below_threshold.empty:
        others_total = below_threshold.sum()
        above_threshold["Others"] = others_total

    # Prepare data for the pie chart
    final_values = above_threshold.values
    final_names = above_threshold.index

    # Debug: Check final values and names
    print("Final Values for Pie Chart:\n", final_values)
    print("Final Names for Pie Chart:\n", final_names)

    # Create the pie chart
    fig = px.pie(values=final_values, names=final_names, title="Number of Entries for Each Unique Token (with Others)")
    fig.write_html(os.path.join(GRAPH_FOLDER, "entries_per_token_pie.html"))
    fig.write_image(os.path.join(GRAPH_FOLDER, "entries_per_token_pie.png"))

    # Graph 7: Pie Chart of Total Quantity Traded for Each Unique Token
    quantity_per_token = df.groupby("token")["order_quantity"].sum().sort_values(ascending=False)

    # Calculate the total quantity
    total_quantity = quantity_per_token.sum()

    # Calculate percentages
    percentages = (quantity_per_token / total_quantity) * 100
    print("Percentages:\n", percentages)  # Debug: Check percentages

    # Separate tokens below 1% into "Others"
    above_threshold = percentages[percentages >= 1]
    below_threshold = percentages[percentages < 1]

    # Combine "Others" category
    if not below_threshold.empty:
        others_total = below_threshold.sum()
        above_threshold["Others"] = others_total

    # Prepare data for the pie chart
    final_values = above_threshold.values
    final_names = above_threshold.index

    # Debug: Check final values and names
    print("Final Values for Pie Chart:\n", final_values)
    print("Final Names for Pie Chart:\n", final_names)

    # Create the pie chart
    fig = px.pie(values=final_values, names=final_names, title="Total Quantity Traded for Each Unique Token (with Others)")
    fig.write_html(os.path.join(GRAPH_FOLDER, "total_quantity_per_token_pie.html"))
    fig.write_image(os.path.join(GRAPH_FOLDER, "total_quantity_per_token_pie.png"))

    print(f"\n✅ File processing completed in {time.time() - start_time:.2f} seconds.")

if __name__ == "__main__":
    app.run(debug=True)