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
from pytz import timezone

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

    with open(file_path, "r") as file:
        for line_num, line in enumerate(file, 1):
            columns = line.strip().split(",")
            if len(columns) >= 8:
                try:
                    raw_epoch_time = int(columns[6])
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

                    token = columns[1].strip()
                    order_quantity = float(columns[-1])
                    action = columns[0].strip()

                    adjusted_times.append(adjusted_time)
                    tokens.append(token)
                    order_quantities.append(order_quantity)
                    actions.append(action)
                except (ValueError, IndexError) as e:
                    if line_num <= 10:
                        print(f"Error parsing line {line_num}: {str(e)}")
                    continue

    df = pd.DataFrame({
        "adjusted_time": adjusted_times,
        "token": tokens,
        "order_quantity": order_quantities,
        "action": actions
    })

    df.dropna(subset=["adjusted_time"], inplace=True)
    df["hour"] = df["adjusted_time"].dt.floor("H")

    # Graph 1: Number of Entries per Hour
    entries_per_hour = df.groupby("hour").size()
    create_plot(df, entries_per_hour.index, entries_per_hour.values,
                "Number of Entries per Hour", "Time", "Number of Entries",
                "entries_per_hour.png")

    # Graph 2: Total Order Quantity per Hour
    quantity_per_hour = df.groupby("hour")["order_quantity"].sum()
    create_plot(df, quantity_per_hour.index, quantity_per_hour.values,
                "Total Order Quantity per Hour", "Time", "Total Order Quantity",
                "order_quantity_per_hour.png", color="green")

    # Graph 3: T to N/M Combination Count per Hour
    combo_hours = []
    for i in range(len(df) - 1):
        if df.iloc[i]["action"] == "T" and df.iloc[i + 1]["action"] in ["N", "M"]:
            combo_hours.append(df.iloc[i]["hour"])
    if combo_hours:
        combo_series = pd.Series(combo_hours).value_counts().sort_index()
        create_plot(df, combo_series.index, combo_series.values,
                    "T to N/M Combination Count per Hour", "Time", "T to N/M Combinations",
                    "t_nm_combo_count_per_hour.png", color="red")

    # Graph 4: Top 5 Tokens by Number of Orders Per Hour
    top_5_tokens = df["token"].value_counts().head(5).index.tolist()
    print("\n🔍 Top 5 Tokens by Number of Orders:", top_5_tokens)

    df_top_tokens = df[df["token"].isin(top_5_tokens)]
    if not df_top_tokens.empty:
        orders_per_hour = df_top_tokens.groupby(["hour", "token"]).size().unstack(fill_value=0).sort_index()
        print("\n📊 Orders Per Hour Table:")
        print(orders_per_hour)

        for token in top_5_tokens:
            if token in orders_per_hour.columns:
                print(f"\n📈 Token {token} hourly orders:")
                print(orders_per_hour[token])

                nonzero = orders_per_hour[token].replace(0, np.nan).dropna()
                if len(nonzero) < 2:
                    print(f"⚠️ Token {token} has <2 non-zero data points. May not form a visible line.")

        first_token = top_5_tokens[0]
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
        additional_series = [
            {
                'x': orders_per_hour.index,
                'y': orders_per_hour[token],
                'marker': 'o',
                'color': colors[i % len(colors)],
                'linewidth': 2,
                'label': f"{token}"
            }
            for i, token in enumerate(top_5_tokens[1:], 1) if token in orders_per_hour.columns
        ]

        create_plot(df, orders_per_hour.index, orders_per_hour[first_token],
                    "Top 5 Tokens by Number of Orders Per Hour", "Time", "Number of Orders",
                    "top_5_tokens_orders_per_hour.png", label=first_token, legend_needed=True, more_series=additional_series)

    # Graph 5: Top 5 Tokens by Quantity Traded per Hour
    top_5_qty_tokens = df.groupby("token")["order_quantity"].sum().nlargest(5).index.tolist()
    print("\n🔍 Top 5 Tokens by Total Quantity:", top_5_qty_tokens)

    df_top_qty = df[df["token"].isin(top_5_qty_tokens)]
    if not df_top_qty.empty:
        qty_per_hour = df_top_qty.groupby(["hour", "token"])["order_quantity"].sum().unstack(fill_value=0).sort_index()
        print("\n📊 Quantity Per Hour Table:")
        print(qty_per_hour)

        for token in top_5_qty_tokens:
            if token in qty_per_hour.columns:
                print(f"\n📈 Token {token} hourly quantities:")
                print(qty_per_hour[token])

                nonzero = qty_per_hour[token].replace(0, np.nan).dropna()
                if len(nonzero) < 2:
                    print(f"⚠️ Token {token} has <2 non-zero data points. May not form a visible line.")

        first_qty_token = top_5_qty_tokens[0]
        qty_colors = ['#17becf', '#bcbd22', '#e377c2', '#8c564b', '#7f7f7f']
        qty_series = [
            {
                'x': qty_per_hour.index,
                'y': qty_per_hour[token],
                'marker': 'o',
                'color': qty_colors[i % len(qty_colors)],
                'linewidth': 2,
                'label': f"{token}"
            }
            for i, token in enumerate(top_5_qty_tokens[1:], 1) if token in qty_per_hour.columns
        ]

        create_plot(df, qty_per_hour.index, qty_per_hour[first_qty_token],
                    "Top 5 Tokens by Total Quantity Per Hour", "Time", "Total Quantity",
                    "top_5_tokens_quantity_per_hour.png", label=first_qty_token, legend_needed=True, more_series=qty_series)

    # Graph 6: Pie Chart of Number of Entries for Each Unique Token
    entries_per_token = df["token"].value_counts()

    # Debug: Print the unique tokens and their entry counts
    print("\n📊 Number of Entries for Each Unique Token:")
    print(entries_per_token)

    # Calculate the total number of entries
    total_entries = entries_per_token.sum()

    # Club tokens with <= 1% of total entries into "Others"
    entries_per_token_clubbed = entries_per_token[entries_per_token / total_entries > 0.01]
    others_count = entries_per_token[entries_per_token / total_entries <= 0.01].sum()

    if others_count > 0:
        entries_per_token_clubbed["Others"] = others_count

    # Debug: Print the clubbed token counts
    print("\n📊 Clubbed Number of Entries for Each Unique Token:")
    print(entries_per_token_clubbed)

    # Plot the pie chart
    plt.figure(figsize=(10, 10))
    plt.pie(
        entries_per_token_clubbed.values,
        labels=entries_per_token_clubbed.index,
        autopct='%1.1f%%',
        startangle=140,
        colors=plt.cm.tab20.colors,  # Use a colorful colormap
        wedgeprops=dict(width=0.4)   # Make it a donut chart style (optional)
    )

    # Add title
    plt.title("Number of Entries for Each Unique Token", fontsize=16, fontweight='bold')

    # Display the count of unique tokens in the top-right corner
    plt.text(1.5, 1.5, f"Total Tokens: {len(entries_per_token)}", fontsize=12, fontweight='bold', ha='center')

    # Save the pie chart
    plt.tight_layout()
    plt.savefig(os.path.join(GRAPH_FOLDER, "06_entries_per_token_pie.png"), dpi=100)
    plt.close()


    # Graph 7: Pie Chart of Total Quantity Traded for Each Unique Token (Descending Order)
    quantity_per_token = df.groupby("token")["order_quantity"].sum().sort_values(ascending=False)

    # Debug: Print the unique tokens and their total quantities
    print("\n📊 Total Quantity Traded for Each Unique Token (Descending Order):")
    print(quantity_per_token)

    # Calculate the total quantity traded
    total_quantity = quantity_per_token.sum()

    # Club tokens with <= 1% of total quantity into "Others"
    quantity_per_token_clubbed = quantity_per_token[quantity_per_token / total_quantity > 0.01]
    others_quantity = quantity_per_token[quantity_per_token / total_quantity <= 0.01].sum()

    if others_quantity > 0:
        quantity_per_token_clubbed["Others"] = others_quantity

    # Debug: Print the clubbed token quantities
    print("\n📊 Clubbed Total Quantity Traded for Each Unique Token:")
    print(quantity_per_token_clubbed)

    # Plot the pie chart
    plt.figure(figsize=(10, 10))
    plt.pie(
        quantity_per_token_clubbed.values,
        labels=quantity_per_token_clubbed.index,
        autopct='%1.1f%%',
        startangle=140,
        colors=plt.cm.tab20b.colors,  # Different colorful colormap
        wedgeprops=dict(width=0.4)    # Donut-style pie chart
    )

    # Add title
    plt.title("Total Quantity Traded for Each Unique Token (Descending Order)", fontsize=16, fontweight='bold')

    # Display the count of unique tokens in the top-right corner
    plt.text(1.5, 1.5, f"Total Tokens: {len(quantity_per_token)}", fontsize=12, fontweight='bold', ha='center')

    # Save the pie chart
    plt.tight_layout()
    plt.savefig(os.path.join(GRAPH_FOLDER, "07_total_quantity_per_token_pie.png"), dpi=100)
    plt.close()


    print(f"\n✅ File processing completed in {time.time() - start_time:.2f} seconds.")

if __name__ == "__main__":
    app.run(debug=True)