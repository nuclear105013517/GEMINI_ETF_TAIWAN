import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import datetime
from datetime import timedelta
import re
from FinMind.data import DataLoader
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# 介面設定與 iOS CSS 
# ==========================================
st.set_page_config(page_title="台美股/ETF 量化決策系統", layout="wide", initial_sidebar_state="collapsed")

ios_css = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Inter", sans-serif !important;
        letter-spacing: -0.015em;
    }

    .ios-large-title { font-size: 34px; font-weight: 800; margin-bottom: 4px; color: var(--text-color); letter-spacing: -0.03em; }
    .ios-sub-title { font-size: 16px; font-weight: 500; color: #8E8E93; margin-bottom: 32px; }

    .stTextInput>div>div>input { 
        background-color: var(--secondary-background-color) !important; 
        color: var(--text-color) !important; 
        border: none !important; border-radius: 14px !important;
        padding: 14px 16px !important; font-size: 16px !important;
        font-weight: 500 !important;
    }
    .stTextInput>div>div>input:focus { box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.3) !important; }

    .stButton>button {
        background-color: #007AFF !important; color: #FFFFFF !important;
        border: none !important; border-radius: 14px !important;
        padding: 12px 24px !important; font-weight: 600 !important; font-size: 17px !important;
        transition: all 0.2s cubic-bezier(0.25, 0.1, 0.25, 1) !important; width: 100%;
    }
    .stButton>button:hover { opacity: 0.85; transform: scale(0.98); }
    .stButton>button:active { transform: scale(0.95); }

    .ios-card {
        background-color: var(--secondary-background-color);
        border-radius: 22px; padding: 22px; margin-bottom: 20px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.04);
        border: 1px solid rgba(150,150,150,0.1);
        display: flex; flex-direction: column; height: 100%;
    }
    .ios-card-header { display: flex; align-items: center; margin-bottom: 12px; gap: 8px; }
    .ios-icon {
        font-size: 18px; width: 32px; height: 32px;
        background: rgba(150,150,150,0.1); border-radius: 10px;
        display: flex; align-items: center; justify-content: center;
    }
    .ios-card-title { font-size: 14px; font-weight: 600; color: #8E8E93; text-transform: uppercase; letter-spacing: 0.5px; }
    .ios-card-value { font-size: 34px; font-weight: 700; color: var(--text-color); margin-bottom: 4px; letter-spacing: -0.04em; }
    .ios-card-value-small { font-size: 22px; font-weight: 700; color: var(--text-color); margin-bottom: 4px; letter-spacing: -0.02em; }
    .ios-card-footer { font-size: 13px; color: #8E8E93; margin-top: auto; padding-top: 16px; font-weight: 500; }
    .ios-card-content { margin-top: 8px; }

    .ios-list {
        background: rgba(150,150,150,0.05); border-radius: 14px;
        padding: 0; margin: 12px 0 0 0; list-style: none; overflow: hidden;
    }
    .ios-list-item {
        padding: 12px 16px; border-bottom: 0.5px solid rgba(150,150,150,0.15);
        display: flex; flex-direction: column; gap: 8px;
    }
    .ios-list-item:last-child { border-bottom: none; }
    .ios-list-text { font-size: 15px; font-weight: 500; color: var(--text-color); line-height: 1.4; opacity: 0.9; }

    .ios-badge { font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 20px; width: fit-content; }
    .badge-green { background: rgba(52, 199, 89, 0.15); color: #34C759; }
    .badge-red { background: rgba(255, 59, 48, 0.15); color: #FF3B30; }
    .badge-gray { background: rgba(142, 142, 147, 0.15); color: #8E8E93; }
    .badge-orange { background: rgba(255, 149, 0, 0.15); color: #FF9500; }
    .badge-blue { background: rgba(0, 122, 255, 0.15); color: #007AFF; }
    .badge-purple { background: rgba(175, 82, 222, 0.15); color: #AF52DE; }
    
    .ios-strategy-desc { font-size: 16px; font-weight: 500; line-height: 1.5; color: var(--text-color); opacity: 0.9; margin-top: 8px; }
</style>
"""
st.markdown(ios_css, unsafe_allow_html=True)

# ==========================================
# 工具函數區與 API 快取 (優化阻塞問題)
# ==========================================
def format_list_item(item, force_blue=False):
    item = str(item).replace('⚠️', '').strip()
    match = re.match(r'\[(.*?)\](.*)', item)
    if match:
        tag = match.group(1).strip()
        content = match.group(2).strip()
        if force_blue: badge_class = "badge-blue"
        elif '多頭' in tag or '+' in tag or '強烈' in content: badge_class = "badge-green"
        elif '空頭' in tag or '-' in tag or '風險' in content or '警告' in tag: badge_class = "badge-red"
        elif '0' in tag or '無效' in content: badge_class = "badge-gray"
        elif '注意' in tag or '支撐' in tag: badge_class = "badge-orange"
        else: badge_class = "badge-blue"
        return f"<li class='ios-list-item'><div class='ios-badge {badge_class}'>{tag}</div><div class='ios-list-text'>{content}</div></li>"
    else:
        return f"<li class='ios-list-item'><div class='ios-list-text'>{item}</div></li>"

def create_card(title, value, custom_html="", list_items=None, use_small_value=False, icon="📊", footer="", force_blue_badge=False):
    val_class = "ios-card-value-small" if use_small_value else "ios-card-value"
    html_parts = [
        '<div class="ios-card">',
        f'<div class="ios-card-header"><div class="ios-icon">{icon}</div><div class="ios-card-title">{title}</div></div>',
        f'<div class="{val_class}">{value}</div>'
    ]
    if list_items:
        items_str = "".join([format_list_item(item, force_blue_badge) for item in list_items])
        html_parts.append(f"<ul class='ios-list'>{items_str}</ul>")
    if custom_html: html_parts.append(f'<div class="ios-card-content">{custom_html}</div>')
    if footer: html_parts.append(f'<div class="ios-card-footer">{footer}</div>')
    html_parts.append('</div>')
    return "".join(html_parts)

def parse_investment_horizon(text):
    text = text.replace(" ", "")
    if any(k in text for k in ["存股", "長期", "不賣", "退休"]): return "5年以上"
    if any(k in text for k in ["當沖", "日內", "Tick", "隔日沖", "極短線"]): return "1天"
    replace_map = {"一": "1", "兩": "2", "二": "2", "三": "3", "四": "4", "五": "5"}
    for k, v in replace_map.items(): text = text.replace(k, v)
    if text == "十年": text = "10年"
    if "天" in text or "日" in text:
        match = re.search(r'(\d+)\s*[天日]', text)
        if match:
            days = int(match.group(1))
            if days <= 1: return "1天"
            elif days <= 5: return "1-5天"
            elif days <= 20: return "1個月內"
            return "1-5天"
    if "周" in text or "週" in text:
        match = re.search(r'(\d+)\s*[周週]', text)
        if match:
            weeks = int(match.group(1))
            if weeks <= 1: return "1-5天"
            elif weeks <= 4: return "1個月內"
            else: return "1-3個月"
            return "1個月內"
    if "年" in text:
        match = re.search(r'(\d+(?:\.\d+)?)\s*年', text)
        if match:
            years = float(match.group(1))
            if years < 1: return "3-6個月"
            elif years <= 1: return "1年"
            elif years <= 3: return "1-3年"
            elif years <= 5: return "3-5年"
            else: return "5年以上"
            return "1-3年"
    if "月" in text:
        match = re.search(r'(\d+(?:\.\d+)?)\s*個?月', text)
        if match:
            months = float(match.group(1))
            if months <= 1: return "1個月內"
            elif months <= 3: return "1-3個月"
            elif months <= 6: return "3-6個月"
            elif months <= 12: return "1年"
            elif months <= 36: return "1-3年"
            else: return "3-5年"
            return "3-6個月"
    return "1年"

def get_horizon_years(horizon_str):
    mapping = {"1天": 0.003, "1-5天": 0.01, "1個月內": 0.08, "1-3個月": 0.25, "3-6個月": 0.5, "1年": 1.0, "1-3年": 2.0, "3-5年": 4.0, "5年以上": 5.0}
    return mapping.get(horizon_str, 1.0)

@st.cache_data(ttl=3600)
def fetch_twse_institutional_cache(pure_ticker, date_str):
    """加入快取機制，避免證交所 API 頻繁請求導致系統卡死"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = f"https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date={date_str}&selectType=ALL"
        res = requests.get(url, headers=headers, timeout=3).json()
        if res.get('stat') == 'OK' and 'data' in res:
            fields = res['fields']
            idx_id = fields.index("證券代號") if "證券代號" in fields else 0
            idx_f = next((i for i, f in enumerate(fields) if "外" in f and "買賣超" in f), 4)
            idx_s = next((i for i, f in enumerate(fields) if "投信" in f and "買賣超" in f), 10)
            idx_d = next((i for i, f in enumerate(fields) if "自營商" in f and "買賣超" in f), 11)
            
            def to_shares(val):
                try: return int(str(val).replace(',', '').replace(' ', ''))
                except: return 0
                
            for row in res['data']:
                if row[idx_id].strip().replace('"', '') == pure_ticker:
                    return {'foreign': to_shares(row[idx_f]), 'sitc': to_shares(row[idx_s]), 'dealer': to_shares(row[idx_d]), 'date': date_str}
    except:
        pass
    return None

# ==========================================
# 優化版：動態期望值與防護回測引擎 (修復勝率幻覺)
# ==========================================
def run_historical_backtest(df, horizon_str, is_weekly_data=False, is_tw_market=True):
    bar_mapping_daily = {"1天": 1, "1-5天": 3, "1個月內": 20, "1-3個月": 40, "3-6個月": 90, "1年": 252, "1-3年": 504, "3-5年": 756, "5年以上": 1260}
    bar_mapping_weekly = {"1年": 52, "1-3年": 104, "3-5年": 156, "5年以上": 260}
    
    forward_bars = bar_mapping_weekly.get(horizon_str, 52) if is_weekly_data else bar_mapping_daily.get(horizon_str, 20)
    backtest_df = df.copy()
    
    if not all(col in backtest_df.columns for col in ['MA20', 'MA60', 'RSI_14']):
        return None, 0, 0.0, 0.0

    # 1. 引入摩擦成本 (台股手續費折扣+交易稅約 0.2%，美股約 0.05%)
    friction_cost = 0.2 if is_tw_market else 0.05
    
    # 2. 計算真實前瞻報酬
    backtest_df['Forward_Return_Pct'] = ((backtest_df['Close'].shift(-forward_bars) - backtest_df['Close']) / backtest_df['Close'] * 100)
    
    # 短線交易強制扣除雙邊摩擦成本，避免 EV 虛高
    if forward_bars <= 3:
        backtest_df['Forward_Return_Pct'] -= friction_cost

    backtest_df['Is_Win'] = backtest_df['Forward_Return_Pct'] > 0
    
    if len(backtest_df) < forward_bars + 60:
        return None, 0, 0.0, 0.0
        
    latest = backtest_df.iloc[-1]
    
    # 3. 採用動態乖離率區間取代硬性指標，確保取樣豐富度
    current_bias = ((latest['Close'] - latest['MA20']) / latest['MA20']) * 100
    cond_bias = (backtest_df['Close'] - backtest_df['MA20']) / backtest_df['MA20'] * 100
    
    # 尋找歷史上乖離率差異在 ±3% 內的相似環境
    similar_cond = (cond_bias >= current_bias - 3) & (cond_bias <= current_bias + 3)
    similar_df = backtest_df[similar_cond].dropna(subset=['Is_Win', 'Forward_Return_Pct'])
        
    sample_size = len(similar_df)
    
    # 4. 樣本數門檻提高至 30 以符合大樣本定理
    if sample_size >= 30:
        win_rate = (similar_df['Is_Win'].sum() / sample_size) * 100
        avg_return = similar_df['Forward_Return_Pct'].mean()
        
        avg_win = similar_df[similar_df['Is_Win']]['Forward_Return_Pct'].mean() if similar_df['Is_Win'].sum() > 0 else 0
        avg_loss = similar_df[~similar_df['Is_Win']]['Forward_Return_Pct'].mean() if (~similar_df['Is_Win']).sum() > 0 else 0
        
        expected_value = ((win_rate/100) * avg_win) + (((100-win_rate)/100) * avg_loss)
        return win_rate, sample_size, avg_return, expected_value
    else:
        return None, sample_size, 0.0, 0.0

# ==========================================
# ETF 評估器 
# ==========================================
class ETFAnalyzer:
    def __init__(self, raw_ticker, ticker_yf, etf_name, user_years, horizon_str):
        self.raw_ticker, self.ticker_yf = raw_ticker, ticker_yf
        self.is_tw_stock = ticker_yf.endswith('.TW') or ticker_yf.endswith('.TWO')
        self.etf_name, self.user_years, self.horizon_str = etf_name, user_years, horizon_str
        self.data, self.score, self.evaluation_details, self.institutional_data = None, 50, [], None
        
        self.is_weekly = user_years > 3.0
        self.interval = "1wk" if self.is_weekly else "1d"
        self.period = "max"

    def fetch_data(self):
        etf = yf.Ticker(self.ticker_yf)
        self.data = etf.history(period=self.period, interval=self.interval, auto_adjust=True)
        if self.data is None or self.data.empty:
            if self.ticker_yf.endswith('.TW'):
                self.ticker_yf = self.ticker_yf.replace('.TW', '.TWO')
                etf = yf.Ticker(self.ticker_yf)
                self.data = etf.history(period=self.period, interval=self.interval, auto_adjust=True)
        if self.data is None or len(self.data) < 20: 
            raise ValueError(f"無法獲取 {self.ticker_yf} 足夠資料。")

    def fetch_institutional_data(self):
        if not self.is_tw_stock or self.is_weekly: return
        # 限制只抓近 3 天，提升效能
        for days_back in range(3):
            target_date = self.data.index[-1]
            if target_date.tz is not None: target_date = target_date.tz_localize(None)
            target_date -= timedelta(days=days_back)
            date_str = target_date.strftime("%Y%m%d")
            
            res = fetch_twse_institutional_cache(self.raw_ticker, date_str)
            if res:
                self.institutional_data = res
                return

    def calculate_indicators(self):
        df = self.data
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA60'] = df['Close'].rolling(window=60).mean()
        df['MA200'] = df['Close'].rolling(window=200).mean()
        df['BIAS_20'] = ((df['Close'] - df['MA20']) / df['MA20']) * 100
        
        delta = df['Close'].diff()
        avg_gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
        avg_loss = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
        df['RSI_14'] = 100 - (100 / (1 + (avg_gain / avg_loss)))
        
        df['High_Low'] = df['High'] - df['Low']
        df['High_Close'] = np.abs(df['High'] - df['Close'].shift())
        df['Low_Close'] = np.abs(df['Low'] - df['Close'].shift())
        df['TR'] = df[['High_Low', 'High_Close', 'Low_Close']].max(axis=1)
        df['ATR'] = df['TR'].rolling(window=14).mean()
        
        low_9, high_9 = df['Low'].rolling(window=9).min(), df['High'].rolling(window=9).max()
        price_diff = (high_9 - low_9).replace(0, np.nan) 
        df['RSV'] = ((df['Close'] - low_9) / price_diff) * 100
        df['RSV'] = df['RSV'].fillna(50)
        df['K'] = df['RSV'].ewm(com=2, adjust=False).mean()
        df['D'] = df['K'].ewm(com=2, adjust=False).mean()

    def analyze_score(self):
        if len(self.data) < 2: return
        latest, prev = self.data.iloc[-1], self.data.iloc[-2]
        is_long_term = self.user_years >= 1.0
        
        self.evaluation_details.append("