import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from database import (
    init_database, save_stock_data, save_company_info,
    get_cached_stock_data, get_company_info_from_db,
    add_to_watchlist, remove_from_watchlist, get_watchlist
)

# 1. Page config must be the very first Streamlit command
st.set_page_config(page_title="StockSight Responsive", page_icon="📈", layout="wide")

# 2. Inject CSS for responsive design (desktop + mobile)
st.markdown(
    """
    <style>
    /* Reset some basic styles */
    body {
        margin: 0;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }

    /* Desktop styles */
    @media (min-width: 768px) {
        .stApp {
            max-width: 1200px;
            margin: auto;
            padding: 20px 40px;
        }
        h1, h2, h3, h4, h5 {
            font-weight: 700;
        }
        .sidebar .block-container {
            padding: 1rem 1rem 1rem 1rem;
        }
        /* Larger charts */
        .element-container iframe, .element-container canvas {
            max-height: 600px !important;
        }
    }

    /* Mobile styles */
    @media (max-width: 767px) {
        .stApp {
            padding: 10px 15px;
            font-size: 14px;
        }
        .sidebar .block-container {
            padding: 1rem 0.5rem 1rem 0.5rem;
        }
        h1 {
            font-size: 1.5rem;
        }
        h2 {
            font-size: 1.2rem;
        }
        /* Make buttons full width */
        button[kind="primary"], button[kind="secondary"] {
            width: 100% !important;
            font-size: 16px !important;
            padding: 12px !important;
        }
        /* Responsive charts */
        .element-container iframe, .element-container canvas {
            max-height: 350px !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# 3. Initialize database if not done
if 'db_initialized' not in st.session_state:
    st.session_state.db_initialized = init_database()

st.title("📈 Stock Analysis Dashboard")
st.markdown("Analyze Indian and Global Stocks with Interactive Charts and Indicators.")

st.sidebar.header("Select Stock")

# Watchlist Section
watchlist = get_watchlist()
selected_watchlist = st.sidebar.selectbox("Choose from Watchlist:", [""] + watchlist)

for sym in watchlist[:5]:
    col1, col2 = st.sidebar.columns([3, 1])
    with col1:
        st.write(f"• {sym}")
    with col2:
        if st.button("×", key=f"rm_{sym}"):
            remove_from_watchlist(sym)
            st.experimental_rerun()

# Stock Symbol or Company Name Input
default_symbol = selected_watchlist or "TATASTEEL"
symbol_input = st.sidebar.text_input("Enter Stock Symbol or Company Name:", value=default_symbol)
query_input = symbol_input.upper().strip()

# Function to search symbol by company name or verify symbol
def search_symbol(query):
    # Try symbol as is or NSE with .NS
    symbols_to_try = [query]
    if not query.endswith(".NS") and "." not in query:
        symbols_to_try.append(query + ".NS")

    for sym in symbols_to_try:
        try:
            ticker = yf.Ticker(sym)
            info = ticker.info
            if 'regularMarketPrice' in info:
                return sym, info
        except Exception:
            pass

    # If no symbol found, try searching by company name via yfinance search (limited API)
    # Alternative: Use yfinance 'tickers' or unofficial APIs. 
    # Here, we try a crude approach by searching top US stocks for match

    # Use yfinance Tickers and search function if available (simulate)
    # WARNING: yfinance does not have official company name search. This is a workaround.

    # You can implement your own mapping dictionary or use an external API for name-to-symbol mapping.
    # For demo, let's check some common US tickers:
    common_us_stocks = {
        "APPLE": "AAPL",
        "MICROSOFT": "MSFT",
        "GOOGLE": "GOOG",
        "ALPHABET": "GOOG",
        "TESLA": "TSLA",
        "AMAZON": "AMZN",
        "FACEBOOK": "META",
        "META": "META"
    }
    for name, sym in common_us_stocks.items():
        if query in name:
            try:
                ticker = yf.Ticker(sym)
                info = ticker.info
                if 'regularMarketPrice' in info:
                    return sym, info
            except Exception:
                continue

    return None, None

# Try to get the symbol and info
stock_symbol, stock_info = search_symbol(query_input)

# Time & Interval Selection
time_period = st.sidebar.selectbox("Time Period", ["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"], index=3)
interval = st.sidebar.selectbox("Interval", ["1d", "5d", "1wk", "1mo", "3mo"], index=0)

def get_currency_symbol(info):
    currency = info.get("financialCurrency", "") if info else ""
    return {
        "INR": "₹",
        "USD": "$",
        "EUR": "€"
    }.get(currency, "$")

@st.cache_data(ttl=300)
def fetch_data(symbol, period, interval):
    try:
        cached = get_cached_stock_data(symbol, period)
        cached_info = get_company_info_from_db(symbol)
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval)
        info = ticker.info
        if 'regularMarketPrice' not in info:
            raise ValueError(f"Symbol '{symbol}' not found or no data available.")
        if not hist.empty:
            save_stock_data(symbol, hist)
        if info:
            save_company_info(symbol, info)
        return {
            'historical': hist,
            'info': info,
            'success': True,
            'error': None
        }
    except Exception as e:
        if cached is not None and cached_info is not None:
            return {
                'historical': cached,
                'info': cached_info,
                'success': True,
                'error': None
            }
        return {'historical': None, 'info': None, 'success': False, 'error': str(e)}

if stock_symbol:
    st.subheader(f"Fetching data for {stock_symbol}...")
    result = fetch_data(stock_symbol, time_period, interval)
    if not result['success']:
        st.error(f"❌ Failed to fetch data for '{stock_symbol}': {result['error']}")
        st.info("✅ Make sure it's a valid NSE symbol like TCS, RELIANCE, or a US symbol like AAPL, GOOG. "
                "If it's an Indian stock, try adding `.NS` (e.g., `TATASTEEL.NS`).")
    else:
        hist_data = result['historical']
        info = result['info']
        currency_symbol = get_currency_symbol(info)

        col1, col2 = st.columns([4, 1])
        with col1:
            st.header(f"{info.get('longName', stock_symbol)} ({stock_symbol})")
        with col2:
            if stock_symbol not in watchlist:
                if st.button("⭐ Add to Watchlist"):
                    add_to_watchlist(stock_symbol)
                    st.success("Added to Watchlist")
                    st.experimental_rerun()
            else:
                st.button("⭐ In Watchlist", disabled=True)

        col1, col2, col3, col4 = st.columns(4)
        current = hist_data['Close'].iloc[-1]
        prev = info.get('regularMarketPreviousClose', hist_data['Close'].iloc[-2])
        diff = current - prev
        pct = (diff / prev) * 100 if prev else 0

        col1.metric("Current Price", f"{currency_symbol}{current:.2f}", f"{diff:.2f} ({pct:.2f}%)")
        col2.metric("Market Cap", f"{currency_symbol}{info.get('marketCap', 0):,.0f}")
        col3.metric("P/E Ratio", f"{info.get('trailingPE', 'N/A')}")
        col4.metric("52W High", f"{currency_symbol}{info.get('fiftyTwoWeekHigh', 'N/A')}")

        st.subheader("📊 Price Chart")
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=hist_data.index,
            open=hist_data['Open'],
            high=hist_data['High'],
            low=hist_data['Low'],
            close=hist_data['Close'],
            name="Candlestick"
        ))
        fig.update_layout(
            title=f"{stock_symbol} Price Chart", yaxis_title="Price", height=600, xaxis_title="Date"
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📈 Volume Chart")
        fig_vol = go.Figure()
        fig_vol.add_trace(go.Bar(
            x=hist_data.index,
            y=hist_data['Volume'],
            name='Volume', marker_color='lightblue'
        ))
        fig_vol.update_layout(title="Volume Traded", yaxis_title="Volume", height=300)
        st.plotly_chart(fig_vol, use_container_width=True)

        st.subheader("📋 Data Table")
        table_data = hist_data[['Open', 'High', 'Low', 'Close', 'Volume']].round(2)
        table_data.index = table_data.index.strftime('%Y-%m-%d')
        st.dataframe(table_data, use_container_width=True)

        st.download_button("📥 Download CSV", table_data.to_csv(), file_name=f"{stock_symbol}.csv", mime="text/csv")

        st.subheader("ℹ️ Company Info")
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Sector:**", info.get('sector', 'N/A'))
            st.write("**Industry:**", info.get('industry', 'N/A'))
            st.write("**Employees:**", info.get('fullTimeEmployees', 'N/A'))
        with col2:
            st.write("**Website:**", info.get('website', 'N/A'))
            st.write("**Revenue:**", f"{currency_symbol}{info.get('totalRevenue', 0):,}")
            profit_margin = info.get('profitMargins', None)
            if profit_margin is not None:
                st.write("**Profit Margin:**", f"{profit_margin * 100:.2f}%")
            else:
                st.write("**Profit Margin:** N/A")

        if info.get('longBusinessSummary'):
            st.write("**Summary:**")
            st.info(info.get('longBusinessSummary'))
else:
    st.info("👈 Enter a stock symbol or company name from India or US in the sidebar to get started.")
