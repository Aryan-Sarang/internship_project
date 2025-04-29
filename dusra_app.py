from flask import Flask, render_template, request, jsonify, send_file, redirect
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use a non-interactive backend
import matplotlib.pyplot as plt

app = Flask(__name__)

# Set the upload folder path
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
    # Delete uploaded files
    for f in os.listdir(app.config["UPLOAD_FOLDER"]):
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], f)
        if os.path.isfile(file_path):
            os.remove(file_path)

    # Delete generated graphs
    for f in os.listdir(app.config["GRAPH_FOLDER"]):
        file_path = os.path.join(app.config["GRAPH_FOLDER"], f)
        if os.path.isfile(file_path):
            os.remove(file_path)

    # Redirect to home page
    return redirect("/")

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file part"})
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "message": "No selected file"})
    
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(file_path)
    
    # Process the file and generate graphs
    try:
        process_file_and_generate_graphs(file_path)
        return jsonify({"success": True, "message": "File processed successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error processing file: {str(e)}"})

@app.route("/graphs")
def show_graphs():
    try:
        # Retrieve all graph files in the GRAPH_FOLDER
        graph_files = [f for f in os.listdir(app.config["GRAPH_FOLDER"]) if f.endswith(".png")]
        print(f"Graph files found: {graph_files}")  # Debug log

        # Generate URLs for the graphs
        graph_urls = [os.path.join("static/graphs", f) for f in graph_files]
        return render_template("graphs.html", graph_urls=graph_urls)
    except Exception as e:
        print(f"Error in /graphs route: {e}")  # Debug log
        return jsonify({"success": False, "message": str(e)})

@app.route("/delete_uploads", methods=["POST"])
def delete_uploads():
    try:
        print("Deleting uploaded files...")  # Debug log
        # Remove all files in the upload folder
        for file in os.listdir(app.config["UPLOAD_FOLDER"]):
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], file)
            if os.path.isfile(file_path):
                os.remove(file_path)
                print(f"Deleted: {file_path}")  # Debug log
        
        print("Deleting generated graphs...")  # Debug log
        # Optionally, clear the graphs folder as well
        for file in os.listdir(app.config["GRAPH_FOLDER"]):
            file_path = os.path.join(app.config["GRAPH_FOLDER"], file)
            if os.path.isfile(file_path):
                os.remove(file_path)
                print(f"Deleted: {file_path}")  # Debug log

        return jsonify({"success": True, "message": "Uploads and graphs deleted successfully"})
    except Exception as e:
        print(f"Error deleting files: {str(e)}")  # Debug log
        return jsonify({"success": False, "message": f"Error deleting files: {str(e)}"})

def process_file_and_generate_graphs(file_path):
    print(f"Processing file: {file_path}")  # Debug log

    # Lists to store the adjusted epoch times, token numbers, and order quantities
    adjusted_times = []
    tokens = []
    order_quantities = []
    actions = []

    # Read log file and process the 2nd value (token number), 7th value (time), and last column (order quantity)
    with open(file_path, "r") as file:
        for line in file:
            columns = line.strip().split(",")  # Assuming CSV-like format
            if len(columns) >= 8:  # Ensure there are at least 8 columns
                try:
                    # Extract the 7th value (Unix epoch time) and add the offset
                    raw_epoch_time = int(columns[6])  # Use the 7th column for timestamps
                    adjusted_epoch_time = raw_epoch_time + 315532800000000000

                    # Normalize the epoch time to seconds (if it's in nanoseconds or microseconds)
                    if adjusted_epoch_time > 1e18:  # Likely nanoseconds
                        epoch_time = adjusted_epoch_time // 1e9
                    elif adjusted_epoch_time > 1e15:  # Likely microseconds
                        epoch_time = adjusted_epoch_time // 1e6
                    else:  # Already in seconds
                        epoch_time = adjusted_epoch_time

                    # Convert Unix epoch time to datetime
                    adjusted_time = pd.to_datetime(epoch_time, unit="s", origin="unix")

                    # Localize to Asia/Kolkata timezone
                    adjusted_time = adjusted_time.tz_localize("UTC").tz_convert("Asia/Kolkata")

                    # Debug log for timestamps
                    print(f"Raw epoch time: {raw_epoch_time}, Adjusted epoch time: {adjusted_epoch_time}, Normalized epoch time: {epoch_time}, Adjusted time: {adjusted_time}")

                    # Extract the token number (2nd value)
                    token = columns[1].strip()

                    # Extract the order quantity (last column)
                    order_quantity = float(columns[-1])  # Convert to float for summation

                    # Extract the action column (assumed to be the 1st column)
                    action = columns[0].strip()

                    # Append the adjusted time, token, order quantity, and action to their respective lists
                    adjusted_times.append(adjusted_time)
                    tokens.append(token)
                    order_quantities.append(order_quantity)
                    actions.append(action)
                except (ValueError, IndexError) as e:
                    # Skip invalid entries and log the error
                    print(f"Skipping invalid entry: {line.strip()} - Error: {e}")
                    continue

    # Convert the lists to a Pandas DataFrame
    df = pd.DataFrame({
        "adjusted_time": adjusted_times,
        "token": tokens,
        "order_quantity": order_quantities,
        "action": actions
    })

    # Ensure 'adjusted_time' is properly converted to datetime
    df["adjusted_time"] = pd.to_datetime(df["adjusted_time"], errors="coerce")

    # Drop any rows with invalid datetime values
    before_drop = len(df)
    df.dropna(subset=["adjusted_time"], inplace=True)
    after_drop = len(df)

    print(f"Dropped {before_drop - after_drop} rows due to invalid datetime.")  # Debug log

    # --- Existing Graphs ---

    # Plot 1: Number of Entries per Hour
    entries_per_hour = df.groupby(df["adjusted_time"].dt.floor("H")).size()
    plt.figure(figsize=(10, 6))
    plt.plot(entries_per_hour.index, entries_per_hour.values, marker="o", linestyle="-", color="blue")
    plt.title("Number of Entries per Hour (Asia/Kolkata Timezone)")
    plt.xlabel("Time (Hourly)")
    plt.ylabel("Number of Entries")
    plt.grid(axis="y", linestyle="--", alpha=0.7)
    for x, y in zip(entries_per_hour.index, entries_per_hour.values):
        plt.annotate(f"{y}", (x, y), textcoords="offset points", xytext=(0, 5), ha="center")
    entries_graph_path = os.path.join(app.config["GRAPH_FOLDER"], "entries_per_hour.png")
    plt.savefig(entries_graph_path)
    plt.close()
    print(f"Saved graph: {entries_graph_path}")  # Debug log

    # Plot 2: Total Order Quantity per Hour
    order_quantity_per_hour = df.groupby(df["adjusted_time"].dt.floor("H"))["order_quantity"].sum()
    plt.figure(figsize=(10, 6))
    plt.plot(order_quantity_per_hour.index, order_quantity_per_hour.values, marker="o", linestyle="-", color="green")
    plt.title("Total Order Quantity per Hour (Asia/Kolkata Timezone)")
    plt.xlabel("Time (Hourly)")
    plt.ylabel("Total Order Quantity")
    plt.grid(axis="y", linestyle="--", alpha=0.7)
    for x, y in zip(order_quantity_per_hour.index, order_quantity_per_hour.values):
        plt.annotate(f"{y:.2f}", (x, y), textcoords="offset points", xytext=(0, 5), ha="center")
    order_quantity_graph_path = os.path.join(app.config["GRAPH_FOLDER"], "order_quantity_per_hour.png")
    plt.savefig(order_quantity_graph_path)
    plt.close()
    print(f"Saved graph: {order_quantity_graph_path}")  # Debug log

    # Plot 3: T to N/M Combination Count per Hour
    combo_hours = []
    for i in range(len(df) - 1):
        current_action = df.iloc[i]["action"]
        next_action = df.iloc[i + 1]["action"]
        if current_action == "T" and next_action in ["N", "M"]:
            combo_hour = df.iloc[i]["adjusted_time"].floor("H")
            combo_hours.append(combo_hour)
    combo_hours_series = pd.Series(combo_hours)
    t_nm_combo_count_per_hour = combo_hours_series.value_counts().sort_index()
    plt.figure(figsize=(10, 6))
    plt.plot(t_nm_combo_count_per_hour.index, t_nm_combo_count_per_hour.values, marker="o", linestyle="-", color="red")
    plt.title("T to N/M Combination Count per Hour (Asia/Kolkata Timezone)")
    plt.xlabel("Time (Hourly)")
    plt.ylabel("T to N/M Combinations")
    plt.grid(axis="y", linestyle="--", alpha=0.7)
    for x, y in zip(t_nm_combo_count_per_hour.index, t_nm_combo_count_per_hour.values):
        plt.annotate(f"{y}", (x, y), textcoords="offset points", xytext=(0, 5), ha="center")
    t_nm_combo_graph_path = os.path.join(app.config["GRAPH_FOLDER"], "t_nm_combo_count_per_hour.png")
    plt.savefig(t_nm_combo_graph_path)
    plt.close()
    print(f"Saved graph: {t_nm_combo_graph_path}")  # Debug log

    # --- New Graph: Top 5 Tokens with Most Orders Per Hour ---

    # Count the total number of orders for each token
    token_order_counts = df["token"].value_counts()

    # Get the top 5 tokens with the most orders
    top_5_tokens = token_order_counts.head(5).index.tolist()
    print(f"Top 5 tokens: {top_5_tokens}")  # Debug log

    # Filter the DataFrame to include only the top 5 tokens
    df_top_tokens = df[df["token"].isin(top_5_tokens)]

    # Group by hour and token, and count the number of orders
    orders_per_hour = df_top_tokens.groupby([df_top_tokens["adjusted_time"].dt.floor("H"), "token"]).size().unstack(fill_value=0)

    # Plot the order counts for the top 5 tokens
    plt.figure(figsize=(12, 8))
    for token in top_5_tokens:
        if token in orders_per_hour.columns:
            plt.plot(orders_per_hour.index, orders_per_hour[token], marker="o", linestyle="-", label=f"Token {token}")
            for x, y in zip(orders_per_hour.index, orders_per_hour[token]):
                plt.annotate(f"{y}", (x, y), textcoords="offset points", xytext=(0, 5), ha="center")

    plt.title("Top 5 Tokens with Most Orders Per Hour (Asia/Kolkata Timezone)")
    plt.xlabel("Time (Hourly)")
    plt.ylabel("Number of Orders")
    plt.legend(title="Tokens")
    plt.grid(axis="y", linestyle="--", alpha=0.7)

    # Save the graph
    top_tokens_graph_path = os.path.join(app.config["GRAPH_FOLDER"], "top_5_tokens_per_hour.png")
    plt.savefig(top_tokens_graph_path)
    plt.close()
    print(f"Saved graph: {top_tokens_graph_path}")  # Debug log

    # --- New Graph: Top 5 Tokens Quantity-Wise Per Hour ---

    # Calculate the total order quantity for each token
    token_quantity_totals = df.groupby("token")["order_quantity"].sum()

    # Get the top 5 tokens with the highest total quantities
    top_5_tokens_quantity = token_quantity_totals.nlargest(5).index.tolist()
    print(f"Top 5 tokens (quantity-wise): {top_5_tokens_quantity}")  # Debug log

    # Filter the DataFrame to include only the top 5 tokens
    df_top_tokens_quantity = df[df["token"].isin(top_5_tokens_quantity)]

    # Group by hour and token, and sum the order quantities
    quantities_per_hour = df_top_tokens_quantity.groupby([df_top_tokens_quantity["adjusted_time"].dt.floor("H"), "token"])["order_quantity"].sum().unstack(fill_value=0)

    # Debug: Print the grouped data
    print("Quantities per hour (grouped):")
    print(quantities_per_hour)

    # Plot the total order quantities for the top 5 tokens
    plt.figure(figsize=(12, 8))
    for token in top_5_tokens_quantity:
        if token in quantities_per_hour.columns:
            plt.plot(quantities_per_hour.index, quantities_per_hour[token], marker="o", linestyle="-", label=f"Token {token}")
            for x, y in zip(quantities_per_hour.index, quantities_per_hour[token]):
                plt.annotate(f"{y:.2f}", (x, y), textcoords="offset points", xytext=(0, 5), ha="center")

    plt.title("Top 5 Tokens Quantity-Wise Per Hour (Asia/Kolkata Timezone)")
    plt.xlabel("Time (Hourly)")
    plt.ylabel("Total Order Quantity")
    plt.legend(title="Tokens")
    plt.grid(axis="y", linestyle="--", alpha=0.7)

    # Format the x-axis as hourly intervals
    ax = plt.gca()
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y-%m-%d %H:%M"))
    plt.gcf().autofmt_xdate()

    # Save the graph
    top_tokens_quantity_graph_path = os.path.join(app.config["GRAPH_FOLDER"], "top_5_tokens_quantity_per_hour.png")
    plt.savefig(top_tokens_quantity_graph_path)
    plt.close()
    print(f"Saved graph: {top_tokens_quantity_graph_path}")  # Debug log

    # Return the paths to the generated graphs
    return [entries_graph_path, order_quantity_graph_path, t_nm_combo_graph_path, top_tokens_graph_path, top_tokens_quantity_graph_path]

if __name__ == "__main__":
    app.run(debug=True)