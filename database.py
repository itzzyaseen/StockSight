import os
import pandas as pd
from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer, Text, Boolean, update
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import uuid
import streamlit as st

# Removed dotenv usage
# Instead, environment variables should be set directly in Streamlit Cloud or locally

# UUID compatibility for SQL Server
def generate_uuid():
    return str(uuid.uuid4())

# Database configuration (SQL Server local default or from env)
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "mssql+pyodbc://localhost/StockSight?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes"
)

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set or invalid.")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models
class StockData(Base):
    __tablename__ = "stock_data"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    symbol = Column(String(20), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class CompanyInfo(Base):
    __tablename__ = "company_info"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    symbol = Column(String(20), nullable=False, unique=True, index=True)
    company_name = Column(String(255))
    sector = Column(String(100))
    industry = Column(String(100))
    market_cap = Column(Float)
    pe_ratio = Column(Float)
    dividend_yield = Column(Float)
    fifty_two_week_high = Column(Float)
    fifty_two_week_low = Column(Float)
    business_summary = Column(Text)
    last_updated = Column(DateTime, default=datetime.utcnow)

class UserWatchlist(Base):
    __tablename__ = "user_watchlist"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    symbol = Column(String(20), nullable=False, index=True)
    added_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class AnalysisCache(Base):
    __tablename__ = "analysis_cache"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    symbol = Column(String(20), nullable=False, index=True)
    period = Column(String(10), nullable=False)
    interval = Column(String(10), nullable=False)
    data_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create all tables
def init_database():
    try:
        Base.metadata.create_all(bind=engine)
        return True
    except Exception as e:
        st.error(f"Database initialization error: {str(e)}")
        return False

# Database operations
def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        pass

def save_stock_data(symbol, historical_data):
    db = get_db()
    try:
        cutoff_date = datetime.now() - timedelta(days=30)
        db.query(StockData).filter(
            StockData.symbol == symbol,
            StockData.date >= cutoff_date
        ).delete()

        for date, row in historical_data.iterrows():
            stock_record = StockData(
                symbol=symbol,
                date=date.to_pydatetime(),
                open_price=float(row['Open']),
                high_price=float(row['High']),
                low_price=float(row['Low']),
                close_price=float(row['Close']),
                volume=int(row['Volume'])
            )
            db.add(stock_record)

        db.commit()
        return True
    except Exception as e:
        db.rollback()
        st.error(f"Error saving stock data: {str(e)}")
        return False
    finally:
        db.close()

def save_company_info(symbol, company_data):
    db = get_db()
    try:
        existing = db.query(CompanyInfo).filter(CompanyInfo.symbol == symbol).first()
        
        if existing:
            db.execute(
                update(CompanyInfo)
                .where(CompanyInfo.symbol == symbol)
                .values(
                    company_name=company_data.get('longName', ''),
                    sector=company_data.get('sector', ''),
                    industry=company_data.get('industry', ''),
                    market_cap=company_data.get('marketCap'),
                    pe_ratio=company_data.get('trailingPE'),
                    dividend_yield=company_data.get('dividendYield'),
                    fifty_two_week_high=company_data.get('fiftyTwoWeekHigh'),
                    fifty_two_week_low=company_data.get('fiftyTwoWeekLow'),
                    business_summary=company_data.get('longBusinessSummary', ''),
                    last_updated=datetime.utcnow()
                )
            )
        else:
            company_record = CompanyInfo(
                symbol=symbol,
                company_name=company_data.get('longName', ''),
                sector=company_data.get('sector', ''),
                industry=company_data.get('industry', ''),
                market_cap=company_data.get('marketCap'),
                pe_ratio=company_data.get('trailingPE'),
                dividend_yield=company_data.get('dividendYield'),
                fifty_two_week_high=company_data.get('fiftyTwoWeekHigh'),
                fifty_two_week_low=company_data.get('fiftyTwoWeekLow'),
                business_summary=company_data.get('longBusinessSummary', '')
            )
            db.add(company_record)

        db.commit()
        return True
    except Exception as e:
        db.rollback()
        st.error(f"Error saving company info: {str(e)}")
        return False
    finally:
        db.close()

def get_cached_stock_data(symbol, period='1y'):
    db = get_db()
    try:
        days = {'1mo': 30, '3mo': 90, '6mo': 180, '1y': 365, '2y': 730}.get(period, 365)
        start_date = datetime.now() - timedelta(days=days)

        records = db.query(StockData).filter(
            StockData.symbol == symbol,
            StockData.date >= start_date
        ).order_by(StockData.date).all()

        if records:
            data = [{
                'Date': r.date,
                'Open': r.open_price,
                'High': r.high_price,
                'Low': r.low_price,
                'Close': r.close_price,
                'Volume': r.volume
            } for r in records]

            df = pd.DataFrame(data)
            df.set_index('Date', inplace=True)
            return df

        return None
    except Exception as e:
        st.error(f"Error retrieving cached data: {str(e)}")
        return None
    finally:
        db.close()

def get_company_info_from_db(symbol):
    db = get_db()
    try:
        company = db.query(CompanyInfo).filter(CompanyInfo.symbol == symbol).first()

        if company:
            return {
                'longName': company.company_name,
                'sector': company.sector,
                'industry': company.industry,
                'marketCap': company.market_cap,
                'trailingPE': company.pe_ratio,
                'dividendYield': company.dividend_yield,
                'fiftyTwoWeekHigh': company.fifty_two_week_high,
                'fiftyTwoWeekLow': company.fifty_two_week_low,
                'longBusinessSummary': company.business_summary
            }

        return None
    except Exception as e:
        st.error(f"Error retrieving company info: {str(e)}")
        return None
    finally:
        db.close()

def add_to_watchlist(symbol):
    db = get_db()
    try:
        existing = db.query(UserWatchlist).filter(
            UserWatchlist.symbol == symbol,
            UserWatchlist.is_active == True
        ).first()

        if not existing:
            watchlist_item = UserWatchlist(symbol=symbol)
            db.add(watchlist_item)
            db.commit()
            return True

        return False
    except Exception as e:
        db.rollback()
        st.error(f"Error adding to watchlist: {str(e)}")
        return False
    finally:
        db.close()

def remove_from_watchlist(symbol):
    db = get_db()
    try:
        item = db.query(UserWatchlist).filter(
            UserWatchlist.symbol == symbol,
            UserWatchlist.is_active == True
        ).first()

        if item:
            db.execute(
                update(UserWatchlist)
                .where(UserWatchlist.symbol == symbol)
                .values(is_active=False)
            )
            db.commit()
            return True

        return False
    except Exception as e:
        db.rollback()
        st.error(f"Error removing from watchlist: {str(e)}")
        return False
    finally:
        db.close()

def get_watchlist():
    db = get_db()
    try:
        watchlist = db.query(UserWatchlist).filter(
            UserWatchlist.is_active == True
        ).order_by(UserWatchlist.added_at.desc()).all()

        return [item.symbol for item in watchlist]
    except Exception as e:
        st.error(f"Error retrieving watchlist: {str(e)}")
        return []
    finally:
        db.close()

def get_popular_stocks():
    db = get_db()
    try:
        cutoff = datetime.now() - timedelta(days=7)
        popular = db.query(StockData.symbol).filter(
            StockData.created_at >= cutoff
        ).distinct().limit(10).all()

        return [s[0] for s in popular]
    except Exception:
        return []
    finally:
        db.close()
