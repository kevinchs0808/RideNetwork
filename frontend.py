import streamlit as st
from py2neo import Graph
import networkx as nx
from pyvis.network import Network
import pandas as pd
from datetime import datetime
import calendar

# Neo4j configuration
NEO4J_URL = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "12345678"

graph = Graph(NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASSWORD))

def get_days_count(year, month):
    weekdays, weekends = 0, 0
    for day in range(1, calendar.monthrange(year, month)[1] + 1):
        if calendar.weekday(year, month, day) < 5:
            weekdays += 1
        else:
            weekends += 1
    return calendar.monthrange(year, month)[1], weekdays, weekends

def get_filtered_data(day_mode, time_mode):
    day_filter = ""
    time_filter = ""
    total_days, weekdays, weekends = get_days_count(year=2020, month=1)
    print(f"total_days: {total_days}")
    print(f"weekdays: {weekdays}")
    print(f"weekends: {weekends}")
    divisor = total_days  # Default for 'Overall'
    
    if day_mode == "Weekday":
        day_filter = "AND r.day_of_week IN [1, 2, 3, 4, 5]"
        divisor = weekdays
    elif day_mode == "Weekend":
        day_filter = "AND r.day_of_week IN [6, 7]"
        divisor = weekends
    
    if time_mode == "Dawn":
        time_filter = "AND r.hour_of_day >= 0 AND r.hour_of_day <= 5"
    elif time_mode == "Morning":
        time_filter = "AND r.hour_of_day >= 6 AND r.hour_of_day <= 11"
    elif time_mode == "Afternoon":
        time_filter = "AND r.hour_of_day >= 12 AND r.hour_of_day <= 17"
    elif time_mode == "Night":
        time_filter = "AND r.hour_of_day >= 18 AND r.hour_of_day <= 23"
    
    query = f"""
    MATCH (start:Zone)-[r:TRIP]->(end:Zone)
    WHERE r.trip_count > 0 {day_filter} {time_filter}
    RETURN start.name AS pickup, end.name AS dropoff, 
           r.total_amount AS total_revenue,
           r.trip_count AS total_trips,
           r.passenger_count AS total_passengers,
           r.trip_distance AS total_distance,
           r.trip_time AS total_time
    """
    return graph.run(query).to_data_frame()

def visualize_network(df, metric, zone_lookup_path="data/taxi+_zone_lookup.csv"):
    # Load taxi zone lookup CSV
    zone_lookup = pd.read_csv(zone_lookup_path)
    zone_lookup = zone_lookup.set_index("Zone")["Borough"].to_dict()  # Convert to dictionary for lookup

    G = nx.DiGraph()

    # Define borough-based colors
    borough_colors = {
        "Manhattan": "red",
        "Brooklyn": "blue",
        "Queens": "green",
        "Bronx": "orange",
        "Staten Island": "purple",
        "Unknown": "gray"
    }

    print(df.columns)

    df = df.groupby(['pickup', 'dropoff']).agg({metric: 'sum'}).reset_index()

    # Sort edges by the selected metric in descending order and take the top 100
    df = df.sort_values(by=metric, ascending=False).head(1000)

    print(df)

    for _, row in df.iterrows():
        pickup_zone = row["pickup"]
        dropoff_zone = row["dropoff"]

        # Get borough info
        pickup_borough = zone_lookup.get(pickup_zone, "Unknown")
        dropoff_borough = zone_lookup.get(dropoff_zone, "Unknown")

        # Add nodes with borough color
        G.add_node(pickup_zone, color=borough_colors.get(pickup_borough, "gray"))
        G.add_node(dropoff_zone, color=borough_colors.get(dropoff_borough, "gray"))

        # Add weighted edge
        weight = row[metric]
        edge_width = max(1, weight / df[metric].max() * 10)  # Normalize edge width

        G.add_edge(pickup_zone, dropoff_zone, weight=edge_width, color='gold')

    # Create PyVis network
    net = Network(height='600px', width='100%', notebook=False, directed=True)
    net.repulsion()
    net.from_nx(G)

    # Apply node colors
    for node in net.nodes:
        node["color"] = G.nodes[node["id"]]["color"]  # Assign borough color

    return net


def main():
    st.title("Ride Network - Jan 2020")
    
    day_mode = st.selectbox("Select Day Mode", ["Overall", "Weekday", "Weekend"])
    time_mode = st.selectbox("Select Time Mode", ["Overall", "Dawn", "Morning", "Afternoon", "Night"])
    metric = st.selectbox("Select Metric", ["total_revenue", "total_trips", "total_passengers", "total_distance", "total_time"])
    
    df = get_filtered_data(day_mode, time_mode)
    net = visualize_network(df, metric)
    
    net.save_graph(f"{day_mode}_{time_mode}_{metric}.html")
    st.components.v1.html(open(f"{day_mode}_{time_mode}_{metric}.html", "r", encoding="utf-8").read(), height=650)

if __name__ == "__main__":
    main()
