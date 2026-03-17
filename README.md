# DolphinTrade

A comprehensive automated trading system with machine learning integration for financial markets.

## Overview

DolphinTrade is a trading automation platform that combines technical analysis indicators with machine learning models to generate trading signals. The system includes a Django backend, MT4 custom indicators, and ML-based prediction algorithms.

## Project Structure

```
DolphinTrade/
├── backend/
│   └── dolphin/
│       ├── dolphin/           # Django project settings
│       ├── TradingStradegy/   # Trading strategy implementations
│       ├── TradingDataGeneration/  # Data processing utilities
│       ├── users/             # User management
│       ├── MT4Algorithms/    # MT4 indicator algorithms
│       ├── Data/              # Market data (EURUSD csv files)
│       └── ML models (.sav)   # Trained ML classifiers
├── mt4indicators/
│   └── main_indicators/       # MetaTrader 4 custom indicators
│       ├── Super Signal v3d.mq4
│       └── Extreme_Spike_new.mq4
└── frontend/                  # Frontend project files
```

## Features

- **Technical Indicators**: Implementation of Super Signal, Extreme Spike, Binary Arrows, and other MT4 indicators
- **Machine Learning**: XGBoost-based classifiers for trade prediction
- **Multi-timeframe Analysis**: Support for 1, 5, 15, and 30-minute charts
- **Django Backend**: REST API for trading signal management
- **Automated Trading**: Integration with MetaTrader 4

## Technology Stack

- **Backend**: Django 4.2, Python 3.x
- **ML**: scikit-learn, XGBoost, pandas
- **Trading**: MetaTrader 4, MT4 Indicators (MQ4)
- **Task Queue**: Celery for async processing
- **Database**: SQLite3 (development)

## Installation

1. Navigate to the backend directory:
   ```bash
   cd backend/dolphin
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run migrations:
   ```bash
   python manage.py migrate
   ```

4. Start the development server:
   ```bash
   python manage.py runserver
   ```

5. (Optional) Start Celery worker:
   ```bash
   celery -A dolphin worker -l info
   ```

## Trading Strategies

The project implements several technical analysis strategies:

- **Super Signal**: Trend reversal indicator
- **Extreme Spike**: Volatility-based signal detection
- **Binary Arrows**: Binary option signal provider
- **TM Indicator**: Custom trend momentum indicator

## ML Models

Pre-trained models are available in `.sav` format:
- `xgbclassifier_15.sav` - 15-minute prediction model
- `combineclassifier.sav` - Combined signal classifier

## Data

Sample market data is included in `Data/`:
- EURUSD_1_MIN.csv
- EURUSD_5_MIN.csv
- EURUSD_15_MIN.csv
- EURUSD_30_MIN.csv

## License

Private - All rights reserved
