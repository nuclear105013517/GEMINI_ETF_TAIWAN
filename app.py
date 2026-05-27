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
    
    .ios-strategy-desc { font-size: 16px; font-weight: 500; line-height: 1.5; color: var(--text-color); opacity: 0.9; margin-top: 8px; }
</style>
"""
st.markdown(ios_css, unsafe_allow_html=True)

# ==========================================
# 工具函數區
# ==========================================
def format_list_item(item, force_blue=False):
    item = str(item).replace('⚠️', '').strip()
    match = re.match(r'\[(.*?)\](.*)', item)
    if match:
        tag = match.group(1).strip()
        content = match.group(2).strip()
        if force_blue: badge_class = "badge-blue"
        elif '多頭' in tag or '+' in tag or '強烈' in content or '獲利' in tag: badge_class = "badge-green"
        elif '空頭' in tag or '-' in tag or '風險' in content or '警告' in tag: badge_class = "badge-red"
        elif '0' in tag or '無效' in content or '中性' in tag: badge_class = "badge-gray"
        elif '注意' in tag or '支撐' in tag or '防守' in tag: badge_class = "badge-orange"
        else: badge_class = "badge-blue"
        return f"<li class='ios-list-item'><div class='ios-badge {badge_class}'>{tag}</div><div class='ios-list-text'>{content}</div></li>"
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
    if any(k in text for k in ["1日", "Tick", "隔日沖", "極短線"]): return "1天"
    replace_map = {"一": "1", "兩": "2", "二": "2", "三": "3", "四": "4", "五": "5", "十年": "10年"}
    for k, v in replace_map.items(): text = text.replace(k, v)
    
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
    if "年" in text:
        match = re.search(r'(\d+(?:\.\d+)?)\s*年', text)
        if match:
            years = float(match.group(1))
            if years < 1: return "3-6個月"
            elif years <= 1: return "1年"
            elif years <= 3: return "1-3年"
            elif years <= 5: return "3-5年"
            else: return "5年以上"
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
    return "1年"

def get_horizon_years(horizon_str):
    mapping = {"1天": 0.003, "1-5天": 0.01, "1個月內": 0.08, "1-3個月": 0.25, "3-6個月": 0.5, "1年": 1.0, "1-3年": 2.0, "3-5年": 4.0, "5年以上": 5.0}
    return mapping.get(horizon_str, 1.0)

@st.cache_data(ttl=3600)
def fetch_twse_institutional_cache(pure_ticker, date_str):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = f"https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date={date_str}&selectType=ALL"
        res = requests.get(url, headers=headers, timeout=5).json()
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
# 核心優化：嚴謹路徑依賴回測引擎 (Rigorous Path-Dependent Engine)
# ==========================================
def run_path_dependent_backtest(df, horizon_str, is_tw_market=True, user_years=1.0):
    """
    優化重點：
    1. 加入 Sharpe Ratio 與 MAE (最大不利偏移) 計算。
    2. 摩擦成本模型嚴謹化 (加入滑點假設)。
    3. 避免過度擬合：放寬單一特徵條件，利用整體距離測度或放寬範圍，確保取樣數足夠。
    """
    bar_mapping_daily = {"1天": 1, "1-5天": 3, "1個月內": 20, "1-3個月": 60, "3-6個月": 120, "1年": 252, "1-3年": 504, "3-5年": 756, "5年以上": 1260}
    forward_bars = bar_mapping_daily.get(horizon_str, 20)
    
    # 樣本不夠時，動態限縮預測窗期
    if len(df) < forward_bars + 60:
        forward_bars = max(1, int(len(df) * 0.2)) 
        
    backtest_df = df.copy()
    if not all(col in backtest_df.columns for col in ['MA20', 'MA60', 'ATR', 'BIAS_20']):
        return None
        
    # 1. 嚴謹摩擦成本設定 (雙邊手續費+證交稅+預估滑點)
    if is_tw_market:
        if forward_bars <= 5: friction_cost = 0.45  # 短線交易稅減半 + 滑點
        else: friction_cost = 0.6  # 正常雙邊交易稅費 + 實務滑點
    else:
        friction_cost = 0.1  # 美股免稅，僅計入券商費與流動性滑點

    # 2. 動態停損位 (基於波動率時間展開：Square Root of Time)
    # 將日 ATR 轉換為 N 日預估波動範圍
    volatility_scalar = np.sqrt(forward_bars)
    # 動態調整乘數，避免長天期停損過大失去意義，實務上設有上限
    m_atr = min(3.0, 1.0 + (volatility_scalar * 0.15)) 
    backtest_df['Stop_Loss_Price'] = backtest_df['Close'] - (backtest_df['ATR'] * m_atr)

    # 3. 路徑依賴檢驗 (Look-ahead 期間內的最低價與最終價)
    backtest_df['Future_Min'] = backtest_df['Low'].iloc[::-1].rolling(window=forward_bars, min_periods=1).min().iloc[::-1].shift(-1)
    backtest_df['Future_Close'] = backtest_df['Close'].shift(-forward_bars)
    
    # 4. 報酬率計算 (嚴守停損紀律)
    backtest_df['Hit_SL'] = backtest_df['Future_Min'] <= backtest_df['Stop_Loss_Price']
    backtest_df['Raw_Forward_Ret'] = np.where(
        backtest_df['Hit_SL'],
        (backtest_df['Stop_Loss_Price'] - backtest_df['Close']) / backtest_df['Close'] * 100,
        (backtest_df['Future_Close'] - backtest_df['Close']) / backtest_df['Close'] * 100
    )
    
    backtest_df['Adjusted_Forward_Return'] = backtest_df['Raw_Forward_Ret'] - friction_cost
    backtest_df['Is_Win'] = backtest_df['Adjusted_Forward_Return'] > 0
    
    # 5. MAE (Maximum Adverse Excursion) 評估下檔壓力
    backtest_df['Max_Drawdown_Pct'] = ((backtest_df['Future_Min'] - backtest_df['Close']) / backtest_df['Close']) * 100
    
    # 清除無法對齊的近期資料 (避免前視偏差)
    backtest_df = backtest_df.dropna(subset=['Future_Close'])
    if len(backtest_df) < 50:
        return None
        
    # 6. 動態特徵 KNN 匹配 (防呆處理)
    safe_close = np.where(backtest_df['Close'] == 0, 1e-5, backtest_df['Close'])
    backtest_df['ATR_Pct'] = (backtest_df['ATR'] / safe_close) * 100
    backtest_df['Trend_Direction'] = backtest_df['Close'] > backtest_df['MA60']
    
    latest = df.iloc[-1]
    current_bias = latest['BIAS_20']
    current_atr_pct = (latest['ATR'] / latest['Close']) * 100 if latest['Close'] > 0 else 0
    current_trend = latest['Close'] > latest['MA60']
    
    # 放寬容忍度以捕捉足夠的統計分佈，避免維度災難
    bias_tolerance = max(2.5, current_atr_pct * 1.2)
    atr_tolerance = max(1.5, current_atr_pct * 0.8)
    
    similar_cond = (
        (backtest_df['BIAS_20'] >= current_bias - bias_tolerance) & 
        (backtest_df['BIAS_20'] <= current_bias + bias_tolerance) &
        (backtest_df['ATR_Pct'] >= current_atr_pct - atr_tolerance) &
        (backtest_df['ATR_Pct'] <= current_atr_pct + atr_tolerance) &
        (backtest_df['Trend_Direction'] == current_trend)
    )
    matched_indices = backtest_df[similar_cond].index
    
    # 過濾重疊樣本 (確保獨立性)
    independent_matches = []
    last_valid_idx = -1
    
    for i in range(len(matched_indices)):
        idx_pos = backtest_df.index.get_loc(matched_indices[i])
        if last_valid_idx == -1 or (idx_pos - last_valid_idx) >= (forward_bars // 3 + 1): 
            independent_matches.append(matched_indices[i])
            last_valid_idx = idx_pos

    similar_df = backtest_df.loc[independent_matches]
    sample_size = len(similar_df)
    
    if sample_size >= 8: # 降低絕對門檻，倚靠後方顯著性檢定
        win_rate = (similar_df['Is_Win'].sum() / sample_size) * 100
        returns = similar_df['Adjusted_Forward_Return']
        expected_value = returns.mean()
        std_dev = returns.std()
        
        # 計算期間 Sharpe Ratio (假設無風險利率 2%)
        rf_rate_period = 2.0 * (forward_bars / 252) 
        sharpe = (expected_value - rf_rate_period) / std_dev if std_dev > 0.01 else 0.0
        
        # 平均最大不利偏移 (MAE)
        avg_mdd = similar_df['Max_Drawdown_Pct'].mean()
        
        return {
            "win_rate": win_rate,
            "sample_size": sample_size,
            "ev": expected_value,
            "sharpe": sharpe,
            "avg_mdd": avg_mdd
        }
    return None

# ==========================================
# 資料清洗與特徵工程模組 (完全 Pandas 向量化)
# ==========================================
def calculate_common_indicators(df):
    new_cols = {}
    new_cols['MA20'] = df['Close'].rolling(window=20).mean()
    new_cols['MA60'] = df['Close'].rolling(window=60).mean()
    new_cols['MA200'] = df['Close'].rolling(window=200).mean()
    new_cols['BIAS_20'] = np.where(new_cols['MA20'] != 0, ((df['Close'] - new_cols['MA20']) / new_cols['MA20']) * 100, 0)
    
    delta = df['Close'].diff()
    avg_gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    avg_loss = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    rs = np.where(avg_loss == 0, 100, avg_gain / avg_loss)
    new_cols['RSI_14'] = np.where(avg_loss == 0, 100, 100 - (100 / (1 + rs)))
    
    new_cols['High_Low'] = df['High'] - df['Low']
    new_cols['High_Close'] = np.abs(df['High'] - df['Close'].shift())
    new_cols['Low_Close'] = np.abs(df['Low'] - df['Close'].shift())
    tr = pd.DataFrame(new_cols)[['High_Low', 'High_Close', 'Low_Close']].max(axis=1)
    new_cols['TR'] = tr
    new_cols['ATR'] = tr.rolling(window=14).mean()
    
    low_9 = df['Low'].rolling(window=9).min()
    high_9 = df['High'].rolling(window=9).max()
    price_diff = (high_9 - low_9).replace(0, 1e-5) # 防範除以0
    new_cols['RSV'] = ((df['Close'] - low_9) / price_diff) * 100
    new_cols['RSV'] = new_cols['RSV'].fillna(50)
    new_cols['K'] = new_cols['RSV'].ewm(com=2, adjust=False).mean()
    new_cols['D'] = new_cols['K'].ewm(com=2, adjust=False).mean()
    
    new_cols['BB_Std'] = df['Close'].rolling(20).std()
    new_cols['BB_Upper'] = new_cols['MA20'] + (2 * new_cols['BB_Std'])
    new_cols['BB_Lower'] = new_cols['MA20'] - (2 * new_cols['BB_Std'])
    new_cols['OBV'] = (np.sign(delta) * df['Volume']).fillna(0).cumsum()
    new_cols['OBV_MA10'] = new_cols['OBV'].rolling(10).mean()
    
    drop_keys = ['High_Low', 'High_Close', 'Low_Close', 'TR']
    clean_cols = {k: v for k, v in new_cols.items() if k not in drop_keys}
    
    df = pd.concat([df, pd.DataFrame(clean_cols, index=df.index)], axis=1)
    return df

# ==========================================
# 基礎物件與評估器
# ==========================================
class ETFAnalyzer:
    def __init__(self, raw_ticker, ticker_yf, etf_name, user_years, horizon_str):
        self.raw_ticker, self.ticker_yf = raw_ticker, ticker_yf
        self.is_tw_stock = ticker_yf.endswith('.TW') or ticker_yf.endswith('.TWO')
        self.etf_name, self.user_years, self.horizon_str = etf_name, user_years, horizon_str
        self.data, self.score, self.evaluation_details, self.institutional_data = None, 50, [], None
        self.period = "max"
        self.interval = "1d" # [修正] 統一使用日線，以確保指標閾值機率分佈不失真

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
        if not self.is_tw_stock or self.interval != "1d": return
        for days_back in range(5): 
            target_date = self.data.index[-1]
            if target_date.tz is not None: target_date = target_date.tz_localize(None)
            target_date -= timedelta(days=days_back)
            date_str = target_date.strftime("%Y%m%d")
            res = fetch_twse_institutional_cache(self.raw_ticker, date_str)
            if res:
                self.institutional_data = res
                return

    def calculate_indicators(self):
        self.data = calculate_common_indicators(self.data)

    def analyze_score(self):
        if len(self.data) < 2: return
        latest, prev = self.data.iloc[-1], self.data.iloc[-2]
        is_long_term = self.user_years >= 1.0
        
        self.evaluation_details.append(f"[注意] 採用日線顆粒度搭配動態窗期展開，避免特徵失真。")

        if self.institutional_data:
            total_net = (self.institutional_data['foreign'] + self.institutional_data['sitc'] + self.institutional_data['dealer']) / 1000
            self.evaluation_details.append(f"[中性] 法人單日買賣超 {total_net:,.0f} 張 (註: ETF籌碼多為造市，無強烈方向性)")

        if is_long_term:
            self.evaluation_details.append("[策略] 啟動長週期的均線與乖離護城河評估。")
            if pd.notna(latest['MA200']):
                if latest['Close'] > latest['MA200']:
                    self.score += 20; self.evaluation_details.append("[+多頭] 站穩年線(200MA)之上，長線牛市結構延續。")
                else:
                    self.score -= 10; self.evaluation_details.append("[-空頭] 價格跌破年線，趨勢偏弱，建議採取定期定額分攤成本。")
            
            bias60 = ((latest['Close'] - latest['MA60']) / latest['MA60']) * 100 if pd.notna(latest['MA60']) else 0
            if pd.notna(bias60):
                if bias60 < -12: self.score += 20; self.evaluation_details.append(f"[+多頭] 季線極度負乖離 ({bias60:.2f}%)，大盤型 ETF 具均值回歸價值。")
                elif bias60 < -6: self.score += 10; self.evaluation_details.append(f"[+支撐] 季線負乖離 ({bias60:.2f}%)，具備長線佈局空間。")
                elif bias60 > 10: self.score -= 15; self.evaluation_details.append(f"[-風險] 季線正乖離過大 ({bias60:.2f}%)，追高勝率顯著下滑。")
        else:
            bias = latest['BIAS_20']
            if pd.notna(bias):
                if bias < -5: self.score += 10; self.evaluation_details.append(f"[+支撐] 20均線負乖離 ({bias:.2f}%)，短線超跌區間。")
                elif bias > 5: self.score -= 10; self.evaluation_details.append(f"[-風險] 20均線正乖離 ({bias:.2f}%)，熱度過高提防回撤。")
                
            rsi, k, d = latest['RSI_14'], latest['K'], latest['D']
            if pd.notna(rsi):
                if rsi < 35: self.score += 15; self.evaluation_details.append(f"[+支撐] RSI 低檔 ({rsi:.1f})，適合回檔承接。")
                elif rsi > 70: self.score -= 15; self.evaluation_details.append(f"[-風險] RSI 高檔 ({rsi:.1f})。")
                
            if pd.notna(k) and pd.notna(d):
                if k < 30 and k > d and prev['K'] <= prev['D']: self.score += 15; self.evaluation_details.append("[+多頭] KD低檔黃金交叉。")
                elif k > 80 and k < d and prev['K'] >= prev['D']: self.score -= 15; self.evaluation_details.append("[-空頭] KD高檔死亡交叉。")
        
        self.score = max(0, min(self.score, 100))

    def get_time_based_advice(self, term_type):
        s = self.score
        if term_type in ["1天", "1-5天", "1個月內"]:
            if s >= 70: return "建議短線偏多操作 (動能充沛)"
            elif s >= 45: return "中性觀望 (無顯著統計優勢)"
            else: return "建議避開 (極短線具下行摩擦成本風險)"
        elif term_type in ["1-3個月", "3-6個月"]:
            if s >= 65: return "建議積極進場 (波段多頭架構)"
            elif s >= 50: return "建議分批建倉 (波段趨勢尚可)"
            else: return "建議觀望 (波段仍具修正壓力)"
        else:
            if s >= 65: return "單筆加碼價值顯著 (長線位階具安全邊際)"
            else: return "維持紀律定期定額 (藉由時間平抑波動風險)"

    def get_report_data(self):
        latest = self.data.iloc[-1]
        backtest_result = run_path_dependent_backtest(self.data, self.horizon_str, self.is_tw_stock, self.user_years)
        
        if backtest_result:
            win_rate_str = f"期望值 {backtest_result['ev']:.2f}% | 勝率 {backtest_result['win_rate']:.1f}% | 夏普 {backtest_result['sharpe']:.2f}"
            win_rate_footer = f"擷取 {backtest_result['sample_size']} 次獨立情境 | 平均最大回撤(MAE) {backtest_result['avg_mdd']:.1f}%"
        else:
            win_rate_str, win_rate_footer = "獨立樣本顯著性不足", "相似情境樣本過少，為杜絕回測過擬合不予呈現"

        vol_scalar = np.sqrt(max(1, get_horizon_years(self.horizon_str)*252))
        m_atr = min(3.0, 1.0 + (vol_scalar * 0.1))
        atr = latest.get('ATR', latest['Close']*0.015)
        
        support = latest['Close'] - (atr * m_atr)
        resistance = latest['Close'] + (atr * m_atr * 1.5)

        return {
            "type": "ETF", "name": self.etf_name, "ticker": self.ticker_yf,
            "price": latest['Close'], "latest_time": latest.name.strftime("%Y/%m/%d"),
            "score": self.score, "matched_tier": self.horizon_str,
            "advice": self.get_time_based_advice(self.horizon_str),
            "details": self.evaluation_details,
            "win_rate": win_rate_str, "win_rate_footer": win_rate_footer, "is_weekly": False,
            "support": support, "resistance": resistance
        }

class StockEvaluator:
    def __init__(self, raw_ticker, ticker_yf, stock_name, market_label, matched_horizon_str, fm):
        self.raw_ticker, self.ticker = raw_ticker, ticker_yf
        self.stock_name, self.market_label = stock_name, market_label
        self.matched_horizon, self.user_horizon_text = matched_horizon_str, matched_horizon_str
        self.fm, self.stock, self.df, self.info = fm, yf.Ticker(self.ticker), pd.DataFrame(), {}
        self.is_us_stock = market_label == "美股/全球"
        self.user_years = get_horizon_years(matched_horizon_str)
        self.interval = "1d" # [修正] 統一使用日線
        self.period = "max"
        
        base_horizons = {
            "1天": {"fund": 0.0, "tech": 0.8, "chip": 0.2, "desc": "高頻短線，純粹動能與通道突破"},
            "1-5天": {"fund": 0.0, "tech": 0.7, "chip": 0.3, "desc": "短波段，看重價量與籌碼突擊"},
            "1個月內": {"fund": 0.1, "tech": 0.6, "chip": 0.3, "desc": "短線波段，技術與籌碼並重"},
            "1-3個月": {"fund": 0.2, "tech": 0.5, "chip": 0.3, "desc": "中線過渡，技術面為主，基本面發酵"},
            "3-6個月": {"fund": 0.3, "tech": 0.4, "chip": 0.3, "desc": "中線，重視產業趨勢與大戶動向"},
            "1年": {"fund": 0.5, "tech": 0.4, "chip": 0.1, "desc": "長線起步，需堅實財務支撐"},
            "1-3年": {"fund": 0.7, "tech": 0.2, "chip": 0.1, "desc": "長線護城河，估值(PEG)為核心"},
            "3-5年": {"fund": 0.85, "tech": 0.15, "chip": 0.0, "desc": "長線高度看重 ROE、盈餘動態成長力與護城河"},
            "5年以上": {"fund": 0.95, "tech": 0.05, "chip": 0.0, "desc": "極長線複利思維，完全取決於財務內在價值趨勢"}
        }
        
        self.horizons = {}
        for k, v in base_horizons.items():
            if self.is_us_stock and v['chip'] > 0:
                total_ft = v['fund'] + v['tech']
                new_f = v['fund'] + (v['chip'] * (v['fund'] / total_ft))
                new_t = v['tech'] + (v['chip'] * (v['tech'] / total_ft))
                self.horizons[k] = {"fund": new_f, "tech": new_t, "chip": 0.0, "desc": v['desc'] + " (美股免計籌碼)"}
            else:
                self.horizons[k] = v

    def fetch_data(self):
        self.df = self.stock.history(period=self.period, interval=self.interval, auto_adjust=True)
        if self.df.empty and self.ticker.endswith('.TW'):
            self.ticker = self.ticker.replace('.TW', '.TWO')
            self.stock = yf.Ticker(self.ticker)
            self.df = self.stock.history(period=self.period, interval=self.interval, auto_adjust=True)
            
        try: self.info = self.stock.info or {}
        except: self.info = {}
        if self.df.empty: raise ValueError("無法獲取股價數據，請確認代號正確性。")

    def calculate_indicators(self):
        self.df = calculate_common_indicators(self.df)

    def analyze_fundamentals(self):
        score, details = 50, []
        pe = self.info.get('trailingPE') or self.info.get('forwardPE')
        pb = self.info.get('priceToBook')
        roe = self.info.get('returnOnEquity')
        eps = self.info.get('trailingEps')
        peg = self.info.get('pegRatio') 

        latest_price = self.df['Close'].iloc[-1]
        
        # 估值自適應回補
        if pe is None and eps is not None and eps > 0:
            pe = latest_price / eps

        pe_threshold = 25 if self.is_us_stock else 18
        ma200 = self.df['MA200'].iloc[-1] if 'MA200' in self.df.columns else None
        is_downtrend = (ma200 is not None) and (latest_price < ma200)

        if pe is not None:
            if peg is not None and 0 < peg <= 1.2:
                score += 20; details.append(f"[+多頭] PEG估值 ({peg:.1f}) 顯示盈餘成長動能具備優勢。")
            elif 0 < pe <= pe_threshold: 
                if is_downtrend and pe < 8:
                    score -= 15; details.append(f"[-警告] 【價值陷阱】低本益比({pe:.1f})但趨勢向下，市場定價悲觀。")
                else:
                    score += 15; details.append(f"[+防守] 靜態本益比({pe:.1f}) 落於合理防禦區間。")
            elif pe > pe_threshold:
                if roe is not None and roe > 0.2:
                    score += 0; details.append(f"[中性] 高本益比({pe:.1f}) 受到高 ROE (>20%) 護城河支撐。")
                else:
                    score -= 15; details.append(f"[-風險] 估值過高({pe:.1f})，缺乏對應成長性。")
            elif pe <= 0: 
                score -= 15; details.append("[-空頭] 企業處於虧損循環 (EPS < 0)。")
        else: 
            details.append("[中性] 盈餘資料暫時缺失，動用防禦性給分機制。")

        if pb is not None:
            pb_threshold = 8.0 if self.is_us_stock else 3.5
            if 0 < pb < pb_threshold: score += 10; details.append(f"[+多頭] PB({pb:.1f}) 屬合理淨值溢價區間。")
            else: score -= 10; details.append(f"[-風險] 股價淨值比({pb:.1f}) 過熱。")

        if roe is not None:
            roe_val = roe * 100
            if roe_val > 15: score += 15; details.append(f"[+多頭] 資本回報率強大 ({roe_val:.1f}%)。")
            elif roe_val > 8: score += 5; details.append(f"[+防守] 資本回報率表現穩健 ({roe_val:.1f}%)。")
            else: score -= 15; details.append(f"[-空頭] 資金運用效率偏弱 ({roe_val:.1f}%)。")

        return max(0, min(score, 100)), details, eps

    def analyze_technicals(self):
        score, details = 50, []
        latest, prev = self.df.iloc[-1], self.df.iloc[-2]
        is_long_term = self.user_years >= 1.0
        long_trend_bad = False

        if pd.notna(latest['MA200']):
            if latest['Close'] > latest['MA60'] > latest['MA200']:
                score += (25 if is_long_term else 10); details.append("[+多頭] 股價>季線>年線，結構完美。")
            elif latest['Close'] > latest['MA200']:
                score += 10; details.append("[+支撐] 股價力守生命年線。")
            else:
                long_trend_bad = True
                score -= 20; details.append("[-空頭] 股價破年線，長線空頭架構。")

        if not is_long_term:
            if long_trend_bad:
                score -= 10; details.append("[-警告] 逆勢作多期望值遭受大級別趨勢壓抑。")

            if latest['OBV'] > latest['OBV_MA10'] and prev['OBV'] <= prev['OBV_MA10']:
                score += 15; details.append("[+多頭] OBV 帶量突破，主力資金推升跡象。")
            elif latest['OBV'] < latest['OBV_MA10']:
                score -= 10; details.append("[-空頭] 量能潮疲軟，缺乏動能。")

            if latest['Close'] > latest['BB_Upper']:
                score -= 15; details.append("[-風險] 突破布林上軌，具備極大均值回歸拉回壓力。")
            elif latest['Close'] < latest['BB_Lower']:
                score += 15; details.append("[+多頭] 觸及布林下軌，短線超賣區。")
            elif latest['Close'] > latest['MA20'] and latest['MA20'] > prev['MA20']:
                score += 10; details.append("[+支撐] 月均線上揚保護。")
                
            if latest['K'] < 25 and latest['K'] > latest['D'] and prev['K'] <= prev['D']: 
                score += 5; details.append("[+多頭] KD低檔轉折 (輔助訊號)。")

        atr = latest.get('ATR', latest['Close'] * 0.02)
        vol_scalar = np.sqrt(max(1, self.user_years * 252))
        multiplier = min(3.0, 1.0 + (vol_scalar * 0.1))

        support = latest['Close'] - (atr * multiplier)
        resistance = latest['Close'] + (atr * (multiplier * 1.5))
        
        return max(0, min(score, 100)), details, support, resistance

    def analyze_chips(self):
        score, details = 50, [] 
        if self.is_us_stock or self.interval != "1d":
            details.append("[中性] 長天期模型已自動將籌碼因子降權，轉化為財務動能。")
            return 50, details

        start_date = (datetime.date.today() - datetime.timedelta(days=40)).strftime("%Y-%m-%d")
        try:
            df_inst = self.fm.taiwan_stock_institutional_investors(stock_id=self.raw_ticker, start_date=start_date)
            if df_inst is not None and not df_inst.empty:
                df_inst['net_buy'] = df_inst['buy'] - df_inst['sell']
                recent_3_days_net = df_inst.groupby('date')['net_buy'].sum().tail(3).sum() / 1000
                
                if recent_3_days_net > 1000: score += 20; details.append(f"[+多頭] 法人近3日累計強買 {recent_3_days_net:,.0f} 張")
                elif recent_3_days_net > 100: score += 10; details.append(f"[+多頭] 法人近3日偏多操作 ({recent_3_days_net:,.0f}張)")
                elif recent_3_days_net > -200: score += 0; details.append(f"[中性] 法人近3日無顯著方向 ({recent_3_days_net:,.0f}張)")
                else: score -= 20; details.append(f"[-空頭] 法人近3日集中出貨 {abs(recent_3_days_net):,.0f} 張")
            else: details.append("[中性] 近期無顯著法人進出數據")
        except: details.append("[中性] 籌碼面 API 調取受限")
        return max(0, min(score, 100)), details

    def _get_advice_level(self, total_score):
        if total_score >= 78: return "強烈建議佈局 (期望值具備高防禦力與攻擊性)"
        elif total_score >= 60: return "建議逢低建倉 (多空結構偏優)"
        elif total_score >= 45: return "中性觀望 / 嚴控資金水位"
        elif total_score >= 30: return "不建議買進 (盈虧比差勁)"
        else: return "強烈避開 / 具備下行破位風險"

    def get_report_data(self):
        self.fetch_data()
        self.calculate_indicators()
        fund_score, fund_details, eps = self.analyze_fundamentals() 
        tech_score, tech_details, support, resistance = self.analyze_technicals() 
        chip_score, chip_details = self.analyze_chips() 

        user_w = self.horizons[self.matched_horizon]
        user_total = (fund_score * user_w['fund']) + (tech_score * user_w['tech']) + (chip_score * user_w['chip'])

        latest = self.df.iloc[-1]
        is_tw = not self.is_us_stock
        
        # 嚴謹化路徑依賴回測
        backtest_result = run_path_dependent_backtest(self.df, self.matched_horizon, is_tw, self.user_years)
        
        if backtest_result:
            win_rate_str = f"期望值 {backtest_result['ev']:.2f}% | 勝率 {backtest_result['win_rate']:.1f}% | 夏普 {backtest_result['sharpe']:.2f}"
            win_rate_footer = f"擷取 {backtest_result['sample_size']} 次歷史獨立特徵 | 平均最大回撤 {backtest_result['avg_mdd']:.1f}% (已扣除滑點成本)"
        else:
            win_rate_str, win_rate_footer = "統計顯著性不足", "為杜絕過擬合(Overfitting)與倖存者偏差，不予呈現無效樣本數"

        return {
            "type": "Stock", "name": self.stock_name, "ticker": self.ticker,
            "price": latest['Close'], "latest_time": latest.name.strftime("%Y/%m/%d"), "eps": eps,
            "support": support, "resistance": resistance,
            "user_horizon": self.user_horizon_text, "matched_horizon": self.matched_horizon,
            "user_total": user_total, "advice": self._get_advice_level(user_total),
            "strategy": user_w['desc'],
            "weights": {"fund": user_w['fund']*100, "tech": user_w['tech']*100, "chip": user_w['chip']*100},
            "details_fund": fund_details, "details_tech": tech_details, "details_chip": chip_details,
            "win_rate": win_rate_str, "win_rate_footer": win_rate_footer, "is_weekly": False
        }

# ==========================================
# 核心大腦路由與主程式
# ==========================================
@st.cache_resource
def get_fm_dataloader():
    return DataLoader()

@st.cache_data(ttl=86400) 
def get_taiwan_stock_info():
    fm = get_fm_dataloader()
    return fm.taiwan_stock_info()

class MasterRoutingSystem:
    def __init__(self):
        self.fm = get_fm_dataloader()
        
    def auto_detect_type(self, raw_ticker):
        raw_ticker = raw_ticker.strip().upper()
        is_tw = any(char.isdigit() for char in raw_ticker)
        ticker_yf, is_etf = raw_ticker, False
        stock_name, market_label = "未知標的", "美股/全球"
        
        if is_tw:
            try:
                stock_info_cache = get_taiwan_stock_info()
                target = stock_info_cache[stock_info_cache['stock_id'] == raw_ticker]
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
    st.markdown('<div class="ios-sub-title">Institutional Quant Edition | 嚴謹路徑回測與防禦演算法</div>', unsafe_allow_html=True)

    # 風險警告宣告
    st.warning("📊 **量化風險聲明 (Quant Warning):** 任何大於 5 年之回測數據，由於依賴當前活躍代號，先天具備**倖存者偏差 (Survivorship Bias)**；請搭配 Sharpe Ratio 與 MAE 評估真實下檔風險。")

    col_input1, col_input2 = st.columns([2, 2])
    with col_input1: user_ticker = st.text_input("輸入股票或 ETF 代號", value="2330", placeholder="例如：2330, 0050, AAPL, QQQ")
    with col_input2: user_horizon_raw = st.text_input("輸入預期投資時長", value="1個月", placeholder="例如：1天、3個月、5年")

    if st.button("啟動機構級別量化評估"):
        if not user_ticker:
            st.error("請輸入正確的金融資產代號")
            return
            
        with st.spinner("深度調取底層資料、執行無前視偏差(No Look-ahead)路徑回測中..."):
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
                    <div class='ios-strategy-desc'><b>評估時長：</b>{report.get('matched_horizon', horizon_str)} (統一採用特徵穩健之日線解析)</div>
                    <div class='ios-strategy-desc'><b>量化綜合評分：</b>{report.get('user_total', report.get('score', 50)):.1f} / 100 分</div>
                    <div class='ios-strategy-desc'><b>核心戰略部署：</b>{report.get('strategy', '多因子量化評估')}</div>
                    """
                    st.markdown(create_card(card_title, card_value, custom_html=score_html, icon="📈", footer=f"最後數據獲取時間: {report['latest_time']}"), unsafe_allow_html=True)
                    st.markdown(create_card("動態風險情境回測", report['win_rate'], icon="🎯", footer=report['win_rate_footer']), unsafe_allow_html=True)
                
                with col_m2:
                    advice_items = [f"[決策反饋] {report['advice']}"]
                    advice_items.append(f"[風控防禦] 波動率動態防守停損位：{report['support']:.2f}")
                    advice_items.append(f"[上檔壓力] 波動率動態獲利了結位：{report['resistance']:.2f}")
                    
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