import pandas as pd
from py2neo import Graph

# Neo4j configuration
NEO4J_URL = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "12345678"

graph = Graph(NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASSWORD))

def load_zone_lookup(file_path):
    zone_df = pd.read_csv(file_path)
    return dict(zip(zone_df["LocationID"], zone_df["Zone"]))

def load_data(file_path, zone_lookup):
    df = pd.read_csv(file_path, usecols=[
        "tpep_pickup_datetime", "tpep_dropoff_datetime", "PULocationID", "DOLocationID",
        "passenger_count", "trip_distance", "total_amount"
    ])
    
    # Convert timestamps
    df["tpep_pickup_datetime"] = pd.to_datetime(df["tpep_pickup_datetime"])
    df["tpep_dropoff_datetime"] = pd.to_datetime(df["tpep_dropoff_datetime"])
    
    # Extract day of week and hour of day
    df["day_of_week"] = df["tpep_pickup_datetime"].dt.dayofweek + 1  # Monday = 1, Sunday = 7
    df["hour_of_day"] = df["tpep_pickup_datetime"].dt.hour
    
    # Map location IDs to zone names
    df["PUZone"] = df["PULocationID"].map(zone_lookup)
    df["DOZone"] = df["DOLocationID"].map(zone_lookup)
    
    # Calculate trip duration in minutes
    df["trip_time"] = (df["tpep_dropoff_datetime"] - df["tpep_pickup_datetime"]).dt.total_seconds() / 60
    
    return df

def create_graph(df):
    # Create unique zones
    zones = set(df["PUZone"].dropna().unique()).union(set(df["DOZone"].dropna().unique()))
    for zone in zones:
        graph.run("""
            MERGE (z:Zone {name: $zone})
        """, zone=zone)
    
    # Create edges for trips
    for _, row in df.iterrows():
        if pd.isna(row["PUZone"]) or pd.isna(row["DOZone"]):
            continue
        graph.run("""
            MATCH (start:Zone {name: $start_zone})
            MATCH (end:Zone {name: $end_zone})
            MERGE (start)-[r:TRIP {day_of_week: $day_of_week, hour_of_day: $hour_of_day}]->(end)
            ON CREATE SET r.total_amount = $amount, r.trip_count = 1, r.passenger_count = $passengers, r.trip_distance = $distance, r.trip_time = $time
            ON MATCH SET r.total_amount = r.total_amount + $amount, r.trip_count = r.trip_count + 1, r.passenger_count = r.passenger_count + $passengers, r.trip_distance = r.trip_distance + $distance, r.trip_time = r.trip_time + $time
        """,
        start_zone=row["PUZone"], end_zone=row["DOZone"], amount=row["total_amount"], passengers=row["passenger_count"], distance=row["trip_distance"], time=row["trip_time"], day_of_week=row["day_of_week"], hour_of_day=row["hour_of_day"])

def create_indexes():
    graph.run("CREATE INDEX FOR (z:Zone) ON (z.name)")
    graph.run("CREATE INDEX FOR ()-[r:TRIP]-() ON (r.day_of_week, r.hour_of_day)")

def main():
    zone_lookup = load_zone_lookup("data/taxi+_zone_lookup.csv")
    file_path = "data/yellow_tripdata_2019-01.csv"  # Update the path accordingly
    df = load_data(file_path, zone_lookup)
    create_graph(df)
    create_indexes()
    print("Data successfully inserted into Neo4j with indexes!")

if __name__ == "__main__":
    main()
