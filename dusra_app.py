from flask import Flask, render_template, request, jsonify, redirect
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
        graph_files = [f for f in os.listdir(GRAPH_FOLDER) if f.endswith(".png")]
        graph_urls = [os.path.join("static/graphs", f) for f in graph_files]
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

def create_plot(df, x_data, y_data, title, xlabel, ylabel, filename, color='#1f77b4', marker='o', 
                linewidth=2, label=None, legend_needed=False, more_series=None):
    """Thread-safe function to create a single plot and save it to disk with exact time labels"""
    with matplotlib_lock:
        # Always create a new figure for each plot
        plt.figure(figsize=(12, 6))
        
        # Plot main series
        plt.plot(x_data, y_data, marker=marker, color=color, linewidth=linewidth, label=label)
        
        # Plot additional series if provided
        if more_series:
            for series in more_series:
                plt.plot(series['x'], series['y'], marker=series['marker'], color=series['color'], 
                        linewidth=series['linewidth'], label=series['label'])
        
        # Add titles and labels
        plt.title(title, fontsize=14, fontweight='bold')
        plt.xlabel(xlabel, fontsize=12)
        plt.ylabel(ylabel, fontsize=12)
        
        # Get the actual x-axis values (datetime objects)
        ax = plt.gca()
        
        # Set x-ticks to the actual time values from the data
        # Get unique hour values that exist in the dataset
        unique_hours = sorted(pd.to_datetime(x_data).unique())
        
        # Set these exact times as x-ticks
        ax.set_xticks(unique_hours)
        
        # Format the x-tick labels to show the exact time
        # Use a format that clearly shows hours and minutes
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        
        # Set consistent x-axis limits with a small buffer
        if len(unique_hours) > 1:
            # If we have multiple timepoints, add buffer
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
    
    # Print debug message
    print(f"Processing file: {file_path}")

    adjusted_times, tokens, order_quantities, actions = [], [], [], []
    
    # Debug counters
    lines_processed = 0
    lines_parsed = 0
    
    # Read and process the file
    with open(file_path, "r") as file:
        for line_num, line in enumerate(file, 1):
            lines_processed += 1
            columns = line.strip().split(",")
            if len(columns) >= 8:
                try:
                    raw_epoch_time = int(columns[6])
                    
                    # For debugging, print some of the first epoch times
                    if lines_processed <= 5:
                        print(f"Line {line_num}: Raw epoch time: {raw_epoch_time}")

                    if raw_epoch_time > 1e18:
                        epoch_time = (raw_epoch_time + 315532800000000000) / 1e9
                    elif raw_epoch_time > 1e15:
                        epoch_time = (raw_epoch_time + 315532800000000) / 1e6
                    elif raw_epoch_time > 1e12:
                        epoch_time = (raw_epoch_time + 315532800000) / 1e3
                    else:
                        epoch_time = raw_epoch_time + 315532800

                    # Debug the actual conversion for the first few entries
                    if lines_processed <= 5:
                        readable_time = datetime.fromtimestamp(epoch_time).strftime('%Y-%m-%d %H:%M:%S')
                        print(f"Line {line_num}: Converted time: {readable_time}")
                    
                    adjusted_time = pd.to_datetime(epoch_time, unit="s", origin="unix")
                    adjusted_time = adjusted_time.tz_localize("UTC").tz_convert("Asia/Kolkata")

                    token = columns[1].strip()
                    order_quantity = float(columns[-1])
                    action = columns[0].strip()

                    adjusted_times.append(adjusted_time)
                    tokens.append(token)
                    order_quantities.append(order_quantity)
                    actions.append(action)
                    lines_parsed += 1
                    
                except (ValueError, IndexError) as e:
                    if lines_processed <= 10:
                        print(f"Error parsing line {line_num}: {str(e)}")
                    continue

    print(f"Total lines processed: {lines_processed}")
    print(f"Valid lines parsed: {lines_parsed}")

    # Create DataFrame from the collected data
    df = pd.DataFrame({
        "adjusted_time": adjusted_times,
        "token": tokens,
        "order_quantity": order_quantities,
        "action": actions
    })

    # Debug the DataFrame
    print(f"DataFrame shape: {df.shape}")
    print("First few rows of DataFrame:")
    print(df.head())
    
    df.dropna(subset=["adjusted_time"], inplace=True)
    
    # Explicitly set the hour using the actual times (not floor)
    # This preserves the exact hour values in the original data
    df["hour"] = df["adjusted_time"].dt.floor("H")
    
    # Debug the hour values
    print("Hour values in dataset:")
    print(df["hour"].unique())

    # Graph 1: Number of Entries per Hour
    entries_per_hour = df.groupby("hour").size()
    
    # Debug the entries_per_hour
    print("Entries per hour:")
    for hour, count in entries_per_hour.items():
        print(f"{hour}: {count}")
    
    create_plot(
        df=df,
        x_data=entries_per_hour.index, 
        y_data=entries_per_hour.values,
        title="Number of Entries per Hour", 
        xlabel="Time", 
        ylabel="Number of Entries",
        filename="entries_per_hour.png"
    )

    # Graph 2: Total Order Quantity per Hour
    order_quantity_per_hour = df.groupby("hour")["order_quantity"].sum()
    create_plot(
        df=df,
        x_data=order_quantity_per_hour.index, 
        y_data=order_quantity_per_hour.values,
        title="Total Order Quantity per Hour", 
        xlabel="Time", 
        ylabel="Total Order Quantity",
        filename="order_quantity_per_hour.png",
        color="green"
    )

    # Graph 3: T to N/M Combination Count per Hour
    combo_hours = []
    for i in range(len(df) - 1):
        if df.iloc[i]["action"] == "T" and df.iloc[i + 1]["action"] in ["N", "M"]:
            combo_hours.append(df.iloc[i]["hour"])
    
    if combo_hours:  # Only create this graph if we have data
        combo_hours_series = pd.Series(combo_hours)
        t_nm_combo_count_per_hour = combo_hours_series.value_counts().sort_index()
        create_plot(
            df=df,
            x_data=t_nm_combo_count_per_hour.index, 
            y_data=t_nm_combo_count_per_hour.values,
            title="T to N/M Combination Count per Hour", 
            xlabel="Time", 
            ylabel="T to N/M Combinations",
            filename="t_nm_combo_count_per_hour.png",
            color="red"
        )

    # Graph 4: Top 5 Tokens by Number of Orders Per Hour
    top_5_tokens = df["token"].value_counts().head(5).index.tolist()
    if top_5_tokens:
        df_top_tokens = df[df["token"].isin(top_5_tokens)]
        
        if not df_top_tokens.empty:
            orders_per_hour = df_top_tokens.groupby(["hour", "token"]).size().unstack(fill_value=0)
            
            # Create additional series data for multi-line plot
            colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
            additional_series = []
            
            # Start with the first token in the main plot call
            first_token = top_5_tokens[0]
            
            # Add remaining tokens as additional series
            for i, token in enumerate(top_5_tokens[1:], 1):
                if token in orders_per_hour.columns:
                    additional_series.append({
                        'x': orders_per_hour.index,
                        'y': orders_per_hour[token],
                        'marker': 'o',
                        'color': colors[i % len(colors)],
                        'linewidth': 2,
                        'label': f"Token {token}"
                    })
            
            create_plot(
                df=df,
                x_data=orders_per_hour.index, 
                y_data=orders_per_hour[first_token] if first_token in orders_per_hour.columns else [],
                title="Top 5 Tokens by Number of Orders Per Hour", 
                xlabel="Time", 
                ylabel="Number of Orders",
                filename="top_5_tokens_orders_per_hour.png",
                label=f"Token {first_token}",
                legend_needed=True,
                more_series=additional_series
            )

    # Graph 5: Top 5 Tokens by Total Quantity Per Hour
    top_5_tokens_quantity = df.groupby("token")["order_quantity"].sum().nlargest(5).index.tolist()
    if top_5_tokens_quantity:
        df_top_tokens_quantity = df[df["token"].isin(top_5_tokens_quantity)]
        
        if not df_top_tokens_quantity.empty:
            quantities_per_hour = df_top_tokens_quantity.groupby(["hour", "token"])["order_quantity"].sum().unstack(fill_value=0)
            
            # Create additional series data for multi-line plot
            colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
            additional_series = []
            
            # Start with the first token in the main plot call
            first_token = top_5_tokens_quantity[0]
            
            # Add remaining tokens as additional series
            for i, token in enumerate(top_5_tokens_quantity[1:], 1):
                if token in quantities_per_hour.columns:
                    additional_series.append({
                        'x': quantities_per_hour.index,
                        'y': quantities_per_hour[token],
                        'marker': 'o',
                        'color': colors[i % len(colors)],
                        'linewidth': 2,
                        'label': f"Token {token}"
                    })
            
            create_plot(
                df=df,
                x_data=quantities_per_hour.index, 
                y_data=quantities_per_hour[first_token] if first_token in quantities_per_hour.columns else [],
                title="Top 5 Tokens by Total Quantity Per Hour", 
                xlabel="Time", 
                ylabel="Total Quantity",
                filename="top_5_tokens_quantity_per_hour.png",
                label=f"Token {first_token}",
                legend_needed=True,
                more_series=additional_series
            )

    end_time = time.time()
    print(f"File processing completed in {end_time - start_time:.2f} seconds.")

if __name__ == "__main__":
    app.run(debug=True)