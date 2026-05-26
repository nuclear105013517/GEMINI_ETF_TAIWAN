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
        
        self.evaluation_details.append("[注意] 本分析採用『還原總報酬權值』，歷史股息已自動回填。")
        self.evaluation_details.append("[警告] 最終獲利受『折溢價率』影響極大，下單前請確認即時折溢價。")

        if self.institutional_data:
            total_net = (self.institutional_data['foreign'] + self.institutional_data['sitc'] + self.institutional_data['dealer']) / 1000
            self.evaluation_details.append(f"[ 0分] 法人單日買賣超 {total_net:,.0f} 張 (註: ETF籌碼多為造市避險，不具強烈方向性)")

        if is_long_term:
            self.evaluation_details.append("[策略] 長期投資屏蔽短線雜訊，專注長週期均線與乖離護城河。")
            if pd.notna(latest['MA200']):
                if latest['Close'] > latest['MA200']:
                    self.score += 20; self.evaluation_details.append("[+20分] 站穩年線(200MA)之上，長線牛市結構延續。")
                else:
                    self.score -= 10; self.evaluation_details.append("[-10分] 價格跌破年線，趨勢偏弱，建議採取定期定額攤平。")
            
            bias60 = ((latest['Close'] - latest['MA60']) / latest['MA60']) * 100
            if pd.notna(bias60):
                if bias60 < -12: self.score += 20; self.evaluation_details.append(f"[+20分] 季線極度負乖離 ({bias60:.2f}%)，大盤型 ETF 極佳買點。")
                elif bias60 < -6: self.score += 10; self.evaluation_details.append(f"[+10分] 季線負乖離 ({bias60:.2f}%)，長線分批佈局機會。")
                elif bias60 > 10: self.score -= 15; self.evaluation_details.append(f"[-15分] 季線正乖離過大 ({bias60:.2f}%)，追高風險攀升。")
        else:
            bias = latest['BIAS_20']
            if pd.notna(bias):
                if bias < -5: self.score += 10; self.evaluation_details.append(f"[+10分] 20日負乖離 ({bias:.2f}%)，短線超跌。")
                elif bias > 5: self.score -= 10; self.evaluation_details.append(f"[-10分] 20日正乖離 ({bias:.2f}%)，短線熱度過高。")
                
            rsi, k, d = latest['RSI_14'], latest['K'], latest['D']
            if pd.notna(rsi):
                if rsi < 35: self.score += 15; self.evaluation_details.append(f"[+15分] RSI 進入相對低檔 ({rsi:.1f})，適合回檔承接。")
                elif rsi > 65: self.score -= 15; self.evaluation_details.append(f"[-15分] RSI 進入相對高檔 ({rsi:.1f})。")
                
            if pd.notna(k) and pd.notna(d):
                if k < 30 and k > d and prev['K'] <= prev['D']: self.score += 15; self.evaluation_details.append("[+15分] KD低檔黃金交叉。")
                elif k > 80 and k < d and prev['K'] >= prev['D']: self.score -= 15; self.evaluation_details.append("[-15分] KD高檔死亡交叉。")
        
        self.score = max(0, min(self.score, 100))

    def get_time_based_advice(self, term_type):
        s = self.score
        if term_type in ["1天", "1-5天", "1個月內"]:
            if s >= 70: return "建議短線偏多操作 (動能充沛)"
            elif s >= 45: return "中性觀望 (無明顯方向性優勢)"
            else: return "建議避開 (極短線具下行摩擦成本風險)"
        elif term_type in ["1-3個月", "3-6個月"]:
            if s >= 65: return "建議積極進場 (波段多頭架構)"
            elif s >= 50: return "建議分批建倉 (波段趨勢尚可)"
            else: return "建議觀望 (波段仍具修正壓力)"
        else:
            if s >= 65: return "具備單筆加碼價值 (長線位階相對便宜)"
            else: return "維持紀律定期定額 (平抑長期波動風險)"

    def get_report_data(self):
        latest = self.data.iloc[-1]
        
        win_rate, sample_size, avg_return, ev = run_historical_backtest(self.data, self.horizon_str, self.is_weekly, self.is_tw_stock)
        
        if win_rate is not None:
            win_rate_str = f"期望值 {ev:.2f}% | 勝率 {win_rate:.1f}%"
            win_rate_footer = f"回測基礎: 擷取 {sample_size} 次歷史極度相似結構之客觀反饋"
        else:
            win_rate_str, win_rate_footer = "樣本顯著性不足", "相似情境低於 30 次，為防統計偏誤不予呈現"

        # 優化 2: ETF 動態 ATR 防守
        atr = latest.get('ATR', latest['Close']*0.015)
        if self.user_years <= 0.01: m_atr = 1.0
        elif self.user_years <= 0.25: m_atr = 1.5
        elif self.user_years <= 1.0: m_atr = 2.5
        else: m_atr = 4.0
            
        support = latest['Close'] - (atr * m_atr)
        resistance = latest['Close'] + (atr * m_atr * 1.5)

        return {
            "type": "ETF", "name": self.etf_name, "ticker": self.ticker_yf,
            "price": latest['Close'], "latest_time": latest.name.strftime("%Y/%m/%d"),
            "score": self.score, "matched_tier": self.horizon_str,
            "advice": self.get_time_based_advice(self.horizon_str),
            "details": self.evaluation_details,
            "win_rate": win_rate_str, "win_rate_footer": win_rate_footer, "is_weekly": self.is_weekly,
            "support": support, "resistance": resistance
        }

# ==========================================
# 股票評估器 (全面升級量能與動態估值防禦)
# ==========================================
class StockEvaluator:
    def __init__(self, raw_ticker, ticker_yf, stock_name, market_label, matched_horizon_str, fm):
        self.raw_ticker, self.ticker = raw_ticker, ticker_yf
        self.stock_name, self.market_label = stock_name, market_label
        self.matched_horizon, self.user_horizon_text = matched_horizon_str, matched_horizon_str
        self.fm, self.stock, self.df, self.info = fm, yf.Ticker(self.ticker), pd.DataFrame(), {}
        self.is_us_stock = market_label == "美股/全球"
        
        self.user_years = get_horizon_years(matched_horizon_str)
        self.is_weekly = self.user_years > 3.0
        self.interval = "1wk" if self.is_weekly else "1d"
        self.period = "max"
        
        base_horizons = {
            "1天": {"fund": 0.0, "tech": 0.8, "chip": 0.2, "desc": "預測次日極短線，重度依賴動能與通道突破"},
            "1-5天": {"fund": 0.0, "tech": 0.7, "chip": 0.3, "desc": "隔日沖/短波段，看重價量結構與籌碼突擊"},
            "1個月內": {"fund": 0.1, "tech": 0.6, "chip": 0.3, "desc": "短線波段，技術面與籌碼面為主"},
            "1-3個月": {"fund": 0.2, "tech": 0.5, "chip": 0.3, "desc": "短中線，依賴技術型態與基本面發酵"},
            "3-6個月": {"fund": 0.3, "tech": 0.4, "chip": 0.3, "desc": "短中線重視技術與大戶流向"},
            "1年": {"fund": 0.5, "tech": 0.4, "chip": 0.1, "desc": "中線需基本面支撐，搭配技術多頭"},
            "1-3年": {"fund": 0.7, "tech": 0.2, "chip": 0.1, "desc": "中長線看重動態估值(PEG)，技術面抓低點"},
            "3-5年": {"fund": 0.85, "tech": 0.15, "chip": 0.0, "desc": "長線高度看重 ROE、盈餘動態成長力與護城河"},
            "5年以上": {"fund": 0.95, "tech": 0.05, "chip": 0.0, "desc": "極長線複利思維，完全取決於財務內在價值趨勢"}
        }
        
        self.horizons = {}
        for k, v in base_horizons.items():
            if self.is_us_stock and v['chip'] > 0:
                total_ft = v['fund'] + v['tech']
                new_fund = v['fund'] + (v['chip'] * (v['fund'] / total_ft))
                new_tech = v['tech'] + (v['chip'] * (v['tech'] / total_ft))
                self.horizons[k] = {"fund": new_fund, "tech": new_tech, "chip": 0.0, "desc": v['desc'] + " (美股免計籌碼權重)"}
            else:
                self.horizons[k] = v

    def fetch_data(self):
        self.df = self.stock.history(period=self.period, interval=self.interval, auto_adjust=True)
        try: self.info = self.stock.info or {}
        except: self.info = {}
        if self.df.empty: raise ValueError("無法獲取股價數據。")

    def calculate_indicators(self):
        df = self.df
        df['MA20'], df['MA60'], df['MA200'] = df['Close'].rolling(20).mean(), df['Close'].rolling(60).mean(), df['Close'].rolling(200).mean()
        
        df['BB_Std'] = df['Close'].rolling(20).std()
        df['BB_Upper'] = df['MA20'] + (2 * df['BB_Std'])
        df['BB_Lower'] = df['MA20'] - (2 * df['BB_Std'])
        
        df['OBV'] = (np.sign(df['Close'].diff()) * df['Volume']).fillna(0).cumsum()
        df['OBV_MA10'] = df['OBV'].rolling(10).mean()
        
        delta = df['Close'].diff()
        avg_gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
        avg_loss = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
        df['RSI_14'] = 100 - (100 / (1 + (avg_gain / avg_loss)))
        
        df['High_Low'] = df['High'] - df['Low']
        df['High_Close'] = np.abs(df['High'] - df['Close'].shift())
        df['Low_Close'] = np.abs(df['Low'] - df['Close'].shift())
        df['TR'] = df[['High_Low', 'High_Close', 'Low_Close']].max(axis=1)
        df['ATR'] = df['TR'].rolling(window=14).mean()

        low_min, high_max = df['Low'].rolling(9).min(), df['High'].rolling(9).max()
        price_diff = (high_max - low_min).replace(0, np.nan)
        df['RSV'] = ((df['Close'] - low_min) / price_diff) * 100
        df['RSV'] = df['RSV'].fillna(50)
        df['K'], df['D'] = df['RSV'].ewm(com=2, adjust=False).mean(), df['RSV'].ewm(com=2, adjust=False).mean().ewm(com=2, adjust=False).mean()

    def analyze_fundamentals(self):
        score, details = 50, []
        pe = self.info.get('trailingPE', self.info.get('forwardPE'))
        pb = self.info.get('priceToBook')
        roe = self.info.get('returnOnEquity')
        eps = self.info.get('trailingEps')
        peg = self.info.get('pegRatio') 

        pe_threshold = 28 if self.is_us_stock else 20
        latest_price = self.df['Close'].iloc[-1]
        ma200 = self.df['MA200'].iloc[-1] if 'MA200' in self.df.columns else None
        
        is_downtrend = (ma200 is not None) and (latest_price < ma200)

        if pe is not None:
            if peg is not None and 0 < peg <= 1.2:
                score += 20; details.append(f"[+20分] PEG估值 ({peg:.1f}) 顯示盈餘成長動能強勁。")
            elif 0 < pe <= pe_threshold: 
                if is_downtrend and pe < 8:
                    score -= 15; details.append(f"[-15分] 【價值陷阱警告】本益比極低 ({pe:.1f}) 但長期趨勢向下，極可能是景氣循環末期。")
                else:
                    score += 15; details.append(f"[+15分] 靜態本益比({pe:.1f}) 處於合理區間。")
            elif pe > pe_threshold:
                if roe is not None and roe > 0.2:
                    score += 0; details.append(f"[ 0分] 本益比({pe:.1f}) 偏高，但受惠高 ROE (>20%) 給予估值溢價。")
                else:
                    score -= 15; details.append(f"[-15分] 本益比({pe:.1f}) 偏高溢價，缺乏成長護城河支撐。")
            elif pe <= 0: 
                score -= 15; details.append("[-15分] 企業處於虧損狀態 (PE < 0)。")
        else: 
            details.append("[ 0分] 本益比資料未提供")

        if pb is not None:
            pb_threshold = 8.0 if self.is_us_stock else 3.5
            if 0 < pb < pb_threshold: score += 10; details.append(f"[+10分] 股價淨值比({pb:.1f}) 屬安全防禦區間。")
            else: score -= 10; details.append(f"[-10分] 股價淨值比({pb:.1f}) 資產溢價過高。")

        if roe is not None:
            roe_val = roe * 100
            if roe_val > 15: score += 15; details.append(f"[+15分] 資本回報率高 ({roe_val:.1f}%)，資金效率強大。")
            elif roe_val > 8: score += 5; details.append(f"[+5分] 資本回報率 ({roe_val:.1f}%) 表現穩健。")
            else: score -= 15; details.append(f"[-15分] 資本回報率偏低 ({roe_val:.1f}%)。")

        return max(0, min(score, 100)), details, eps

    def analyze_technicals(self):
        score, details = 50, []
        latest, prev = self.df.iloc[-1], self.df.iloc[-2]
        is_long_term = self.user_years >= 1.0
        
        if self.is_weekly: details.append("[注意] 系統切換至『週 K 線』過濾短期雜訊。")

        long_trend_bad = False
        if pd.notna(latest['MA200']):
            if latest['Close'] > latest['MA60'] > latest['MA200']:
                score += (25 if is_long_term else 10); details.append("[+多頭] 股價 > 季線 > 年線，完美多頭排列。")
            elif latest['Close'] > latest['MA200']:
                score += 10; details.append("[+支撐] 股價力守年線之上。")
            else:
                long_trend_bad = True
                score -= 20; details.append("[-空頭] 股價跌破年線，長線空頭結構確立。")

        if not is_long_term:
            if long_trend_bad:
                score -= 10; details.append("[-警告] 大趨勢向下，短線做多期望值受到壓抑。")

            if latest['OBV'] > latest['OBV_MA10'] and prev['OBV'] <= prev['OBV_MA10']:
                score += 15; details.append("[+15分] OBV 量能突破均線，主力資金介入跡象明顯。")
            elif latest['OBV'] < latest['OBV_MA10']:
                score -= 10; details.append("[-10分] OBV 量能疲弱，缺乏上漲推升燃料。")

            if latest['Close'] > latest['BB_Upper']:
                score -= 15; details.append("[-15分] 股價突破布林上軌，極短線乖離過大易拉回。")
            elif latest['Close'] < latest['BB_Lower']:
                score += 15; details.append("[+15分] 股價觸及布林下軌，短線具備超跌反彈契機。")
            elif latest['Close'] > latest['MA20'] and latest['MA20'] > prev['MA20']:
                score += 10; details.append("[+10分] 月均線(20MA)上彎且具備支撐。")
                
            if latest['K'] < 25 and latest['K'] > latest['D'] and prev['K'] <= prev['D']: 
                score += 5; details.append("[+ 5分] KD低檔黃金交叉 (輔助訊號)。")

        # 優化 2：動態 ATR 防護網 (依照投資人週期縮放)
        atr = latest.get('ATR', latest['Close'] * 0.02)
        if self.user_years <= 0.01: # 1-5天
            multiplier = 1.0
        elif self.user_years <= 0.25: # 1-3個月
            multiplier = 1.5
        elif self.user_years <= 1.0: # 1年
            multiplier = 2.5
        else: # 長期存股
            multiplier = 4.0

        support = latest['Close'] - (atr * multiplier)
        resistance = latest['Close'] + (atr * (multiplier * 1.5))
        
        return max(0, min(score, 100)), details, support, resistance

    def analyze_chips(self):
        score, details = 50, [] 
        if self.is_us_stock or self.is_weekly:
            details.append("[ 0分] 系統已自動將籌碼權重平滑轉移至基本面與趨勢面。")
            return 50, details

        start_date = (datetime.date.today() - datetime.timedelta(days=40)).strftime("%Y-%m-%d")
        try:
            df_inst = self.fm.taiwan_stock_institutional_investors(stock_id=self.raw_ticker, start_date=start_date)
            if df_inst is not None and not df_inst.empty:
                df_inst['net_buy'] = df_inst['buy'] - df_inst['sell']
                recent_3_days_net = df_inst.groupby('date')['net_buy'].sum().tail(3).sum() / 1000
                
                if recent_3_days_net > 1000: score += 20; details.append(f"[+20分] 法人近3日累計強力買超 {recent_3_days_net:,.0f} 張")
                elif recent_3_days_net > 100: score += 10; details.append(f"[+10分] 法人近3日偏多操作 ({recent_3_days_net:,.0f}張)")
                elif recent_3_days_net > -200: score += 0; details.append(f"[ 0分] 法人近3日無顯著方向 ({recent_3_days_net:,.0f}張)")
                else: score -= 20; details.append(f"[-20分] 法人近3日集中倒貨出脫 {abs(recent_3_days_net):,.0f} 張")
            else: details.append("[ 0分] 近期無法人進出數據")
        except: details.append("[ 0分] 籌碼面 API 調取受限")
        return max(0, min(score, 100)), details

    def _get_advice_level(self, total_score):
        if total_score >= 78: return "強烈建議佈局 (期望值具備高防禦力與攻擊性)"
        elif total_score >= 60: return "建議逢低建倉 (多空結構偏優)"
        elif total_score >= 45: return "中性觀望 / 嚴控資金水位"
        elif total_score >= 30: return "不建議買進 (盈虧比較差)"
        else: return "強烈避開 / 具備下行破位風險"

    def get_report_data(self):
        self.fetch_data()
        self.calculate_indicators()
        fund_score, fund_details, eps = self.analyze_fundamentals() 
        tech_score, tech_details, support, resistance = self.analyze_technicals() 
        chip_score, chip_details = self.analyze_chips() 

        user_w = self.horizons[self.matched_horizon]
        weighted_f = fund_score * user_w['fund']
        weighted_t = tech_score * user_w['tech']
        weighted_c = chip_score * user_w['chip']
        
        user_total = weighted_f + weighted_t + weighted_c

        latest = self.df.iloc[-1]
        
        # 採用優化版動態回測
        is_tw = not self.is_us_stock
        win_rate, sample_size, avg_return, ev = run_historical_backtest(self.df, self.matched_horizon, self.is_weekly, is_tw)
        
        if win_rate is not None:
            win_rate_str = f"期望值 {ev:.2f}% | 勝率 {win_rate:.1f}%"
            win_rate_footer = f"系統回測基礎: 過濾近 {len(self.df)} 根K線，擷取 {sample_size} 次高擬合情境計算"
        else:
            win_rate_str, win_rate_footer = "樣本顯著性不足", "相似情境過少 (<30)，強制屏蔽失真數據，保障交易品質"

        return {
            "type": "Stock", "name": self.stock_name, "ticker": self.ticker,
            "price": latest['Close'], "latest_time": latest.name.strftime("%Y/%m/%d"), "eps": eps,
            "support": support, "resistance": resistance,
            "user_horizon": self.user_horizon_text, "matched_horizon": self.matched_horizon,
            "user_total": user_total, "advice": self._get_advice_level(user_total),
            "strategy": user_w['desc'],
            "weights": {"fund": user_w['fund']*100, "tech": user_w['tech']*100, "chip": user_w['chip']*100},
            "details_fund": fund_details, "details_tech": tech_details, "details_chip": chip_details,
            "win_rate": win_rate_str, "win_rate_footer": win_rate_footer, "is_weekly": self.is_weekly
        }

# ==========================================
# 核心大腦路由與主程式
# ==========================================
class MasterRoutingSystem:
    def __init__(self):
        self.fm = DataLoader()
        self._stock_info_cache = None
        
    def auto_detect_type(self, raw_ticker):
        raw_ticker = raw_ticker.strip().upper()
        is_tw = any(char.isdigit() for char in raw_ticker)
        ticker_yf, is_etf = raw_ticker, False
        stock_name, market_label = "未知標的", "美股/全球"
        
        if is_tw:
            try:
                if self._stock_info_cache is None: 
                    self._stock_info_cache = self.fm.taiwan_stock_info()
                target = self._stock_info_cache[self._stock_info_cache['stock_id'] == raw_ticker]
                if not target.empty:
                    stock_name = target.iloc[0]['stock_name']
                    industry = str(target.iloc[0].get('industry_category', '')).upper()
                    market_type = str(target.iloc[0].get('type', '')).lower()
                    market_label = "上櫃" if 'tpex' in market_type or 'otc' in market_type else "上市"
                    if 'ETF' in industry or 'EPR' in industry or len(raw_ticker) >= 5: is_etf = True
                    ticker_yf = f"{raw_ticker}.TW"
                else:
                    if len(raw_ticker) >= 5: is_etf = True
                    ticker_yf = f"{raw_ticker}.TW"
            except: ticker_yf = f"{raw_ticker}.TW"
        else:
            if raw_ticker in ["SPY", "VOO", "QQQ", "IWM", "VT", "VTI", "GLD", "TLT", "BND"]:
                is_etf, stock_name = True, f"{raw_ticker} 全球型/主題型 ETF"
            else:
                stock_name = f"{raw_ticker} 國際企業"
        return ticker_yf, is_etf, stock_name, market_label

def main():
    st.markdown('<div class="ios-large-title">台美股/ETF 量化決策系統</div>', unsafe_allow_html=True)
    st.markdown('<div class="ios-sub-title">基於動態期望值 (EV) 與波動率回測架構 (專家增強版)</div>', unsafe_allow_html=True)

    col_input1, col_input2 = st.columns([2, 2])
    with col_input1: user_ticker = st.text_input("輸入股票或 ETF 代號", value="2330", placeholder="例如：2330, 0050, AAPL, QQQ")
    with col_input2: user_horizon_raw = st.text_input("輸入預期投資時長", value="1天", placeholder="例如：當沖、3個月、5年、定期定額")

    if st.button("啟動系統性風險與量化評估"):
        if not user_ticker:
            st.error("請輸入正確的金融資產代號")
            return
            
        with st.spinner("深度調取底層歷史資料、動態基本面與大戶籌碼中..."):
            router = MasterRoutingSystem()
            ticker_yf, is_etf, asset_name, market_label = router.auto_detect_type(user_ticker)
            horizon_str = parse_investment_horizon(user_horizon_raw)
            user_years = get_horizon_years(horizon_str)
            
            try:
                if is_etf:
                    analyzer = ETFAnalyzer(user_ticker, ticker_yf, asset_name, user_years, horizon_str)
                    analyzer.fetch_data()
                    analyzer.fetch_institutional_data()
                    analyzer.calculate_indicators()
                    analyzer.analyze_score()
                    report = analyzer.get_report_data()
                else:
                    evaluator = StockEvaluator(user_ticker, ticker_yf, asset_name, market_label, horizon_str, router.fm)
                    report = evaluator.get_report_data()
                
                col_m1, col_m2 = st.columns([1, 1])
                with col_m1:
                    card_title = f"{report['name']} ({report['ticker']})"
                    card_value = f"{report['price']:.2f}"
                    score_html = f"""
                    <div class='ios-strategy-desc'><b>評估時長：</b>{report.get('matched_horizon', horizon_str)}</div>
                    <div class='ios-strategy-desc'><b>量化綜合評分：</b>{report.get('user_total', report.get('score', 50)):.1f} / 100 分</div>
                    <div class='ios-strategy-desc'><b>核心戰略部署：</b>{report.get('strategy', '多因子量化評估')}</div>
                    """
                    st.markdown(create_card(card_title, card_value, custom_html=score_html, icon="📈", footer=f"最後數據獲取時間: {report['latest_time']}"), unsafe_allow_html=True)
                    st.markdown(create_card("動態情境回測 (期望值 EV 檢驗)", report['win_rate'], icon="🎯", footer=report['win_rate_footer']), unsafe_allow_html=True)
                
                with col_m2:
                    advice_items = [f"[決策反饋] {report['advice']}"]
                    advice_items.append(f"[風控防禦] 基於 ATR 動態防守停損位：{report['support']:.2f}")
                    advice_items.append(f"[上檔壓力] 基於 ATR 動態獲利了結位：{report['resistance']:.2f}")
                    
                    st.markdown(create_card("戰略決策與結果反饋建議", "ACTIONABLE ADVICE", list_items=advice_items, use_small_value=True, icon="⚖️"), unsafe_allow_html=True)
                
                st.markdown("<br><h3 style='font-size:20px; font-weight:700;'>💡 多因子底層量化評分診斷清單</h3>", unsafe_allow_html=True)
                
                if report['type'] == "ETF":
                    st.markdown(create_card("ETF 多空結構明細", "Details", list_items=report['details'], use_small_value=True, icon="📋"), unsafe_allow_html=True)
                else:
                    col_d1, col_d2, col_d3 = st.columns([1, 1, 1])
                    with col_d1: st.markdown(create_card("動態財務與基本面估值", f"{report['weights']['fund']:.0f}% 權重", list_items=report['details_fund'], use_small_value=True, icon="🏢"), unsafe_allow_html=True)
                    with col_d2: st.markdown(create_card("量價結構與技術通道", f"{report['weights']['tech']:.0f}% 權重", list_items=report['details_tech'], use_small_value=True, icon="📊"), unsafe_allow_html=True)
                    with col_d3: st.markdown(create_card("主力結構與大戶籌碼面", f"{report['weights']['chip']:.0f}% 權重", list_items=report['details_chip'], use_small_value=True, icon="👥"), unsafe_allow_html=True)
                        
            except Exception as e:
                st.error(f"量化引擎核心發生金融資料調取中斷錯誤: {str(e)}")

if __name__ == "__main__":
    main()