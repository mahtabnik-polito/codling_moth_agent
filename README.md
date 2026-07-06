# Climate & Codling Moth Advisory Dashboard

An interactive, responsive web-based monitoring dashboard connected to a PostgreSQL database. It visualizes local temperature, humidity, and Heating Degree Days (HDD) across multiple monitoring stations and uses a built-in biological rule engine (the **Moth Advisory Agent**) to estimate the current life cycle generations of the codling moth.

## Features

- **Dynamic Weather Visualizations**: Double Y-axes line charts showing temperature (°C) and humidity (%) trends, bar charts showing daily HDD aggregates, and area charts showing Cumulative Degree Days.
- **AI Moth Advisory Agent**: Automatically tracks Cumulative Degree Days and maps the population to developmental stages (Pre-Flight, G1, G2, G3 Partial, and Post-Season/Diapause) with biological assessments and recommended action guides.
- **Development Timeline**: Renders a vertical stage transition log detailing the calendar dates and cumulative degree days when each generational boundary was crossed.
- **Flexible Filters**: Date range selector, presets (Last 30 Days, Last 90 Days, All Time), station selectors, and hourly vs. daily granularity toggles.
- **Bulk CSV Data Exporter**: Includes a standalone script (`export_sensor_data.py`) to run database queries and export raw sensor data directly to CSV.

## Project Structure

```
codling_moth_agent/
│
├── templates/
│   └── index.html             # Frontend dashboard dashboard template
│
├── app.py                     # Flask web server & lifecycle rule engine
├── deploy_agent.py            # Standalone file to deploy the Agent
├── moth_advisory_agent
│   └── agent.py               # Frontend dashboard dashboard template
│   └── requirements.txt       # Python packages
│   └── tools.py               # Tools
└── requirements.txt           # Python packages
```

## Setup & Installation

### 1. Prerequisites
- Python 3.12+ installed.
- Access to the target PostgreSQL server (credentials are pre-configured in `app.py`).

### 2. Installation
Navigate to the project root directory and create a virtual environment:

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Activate virtual environment (macOS/Linux)
source venv/bin/activate

# Install dependencies
python -m pip install -r requirements.txt
```

## Running the Application

### 1. Start the Web Server
Launch the Flask development server:

```bash
python app.py
```

By default, the server will start at:
👉 **[http://127.0.0.1:5000/](http://127.0.0.1:5000/)**
