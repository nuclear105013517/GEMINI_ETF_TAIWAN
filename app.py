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
# 介面設定
# ==========================================
st.set_page_config(page_title="台美股/ETF 量化決策", layout="wide", initial_sidebar_state="collapsed")

# ==========================================
# 100% Apple iOS 卡片化 CSS 核心
# ==========================================
ios_css = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Inter", sans-serif !important;
        letter-spacing: -0.015em;
    }

    /* 大標題 Apple Stocks 風格 */
    .ios-large-title { font-size: 34px; font-weight: 800; margin-bottom: 4px; color: var(--text-color); letter-spacing: -0.03em; }
    .ios-sub-title { font-size: 16px; font-weight: 500; color: #8E8E93; margin-bottom: 32px; }

    /* iOS 搜尋/輸入框 */
    .stTextInput>div>div>input { 
        background-color: var(--secondary-background-color) !important; 
        color: var(--text-color) !important; 
        border: none !important; border-radius: 14px !important;
        padding: 14px 16px !important; font-size: 16px !important;
        font-weight: 500 !important;
    }
    .stTextInput>div>div>input:focus { box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.3) !important; }

    /* iOS 藍色動作按鈕 */
    .stButton>button {
        background-color: #007AFF !important; color: #FFFFFF !important;
        border: none !important; border-radius: 14px !important;
        padding: 12px 24px !important; font-weight: 600 !important; font-size: 17px !important;
        transition: all 0.2s cubic-bezier(0.25, 0.1, 0.25, 1) !important; width: 100%;
    }
    .stButton>button:hover { opacity: 0.85; transform: scale(0.98); }
    .stButton>button:active { transform: scale(0.95); }

    /* ==========================================
       iOS 卡片設計 (Card-based UI)
       ========================================== */
    .ios-card {
        background-color: var(--secondary-background-color);
        border-radius: 22px;
        padding: 22px;
        margin-bottom: 20px;
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

    /* ==========================================
       iOS 設定頁風格清單 (Inset-Grouped Lists)
       ========================================== */
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

    /* iOS 動態彩色標籤 (Badges) */
    .ios-badge { font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 20px; width: fit-content; }
    .badge-green { background: rgba(52, 199, 89, 0.15); color: #34C759; }
    .badge-red { background: rgba(255, 59, 48, 0.15); color: #FF3B30; }
    .badge-gray { background: rgba(142, 142, 147, 0.15); color: #8E8E93; }
    .badge-orange { background: rgba(255, 149, 0, 0.15); color: #FF9500; }
    .badge-blue { background: rgba(0, 122, 255, 0.15); color: #007AFF; }

    /* iOS 膠囊比例條 (Weight Bar) */
    .ios-weight-bar {
        display: flex; flex-wrap: wrap; gap: 12px; margin-top: 16px; margin-bottom: 12px;
        background: rgba(150,150,150,0.05); padding: 14px; border-radius: 14px;
    }
    .weight-item { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 600; color: var(--text-color); }
    .dot { width: 10px; height: 10px; border-radius: 50%; }
    .dot-blue { background: #007AFF; }
    .dot-purple { background: #AF52DE; }
    .dot-orange { background: #FF9500; }
    .ios-strategy-desc { font-size: 16px; font-weight: 500; line-height: 1.5; color: var(--text-color); opacity: 0.9; margin-top: 8px; }
</style>
"""
st.markdown(ios_css, unsafe_allow_html=True)

# ==========================================
# UI 渲染核心：徹底消除換行縮排，防止 Markdown 誤判 HTML
# ==========================================
def format_list_item(item, force_blue=False):
    item = str(item).replace('⚠️', '').strip()
    match = re.match(r'\[(.*?)\](.*)', item)
    if match:
        tag = match.group(1).strip()
        content = match.group(2).strip()
        
        # 增加 force_blue 參數，如果是其他投資年限區塊，強制統一顯示藍色
        if force_blue:
            badge_class = "badge-blue"
        elif '+' in tag or '強烈' in content or '多頭' in content: 
            badge_class = "badge-green"
        elif '-' in tag or '空頭' in content or '風險' in content or '跌' in content: 
            badge_class = "badge-red"
        elif '0' in tag: 
            badge_class = "badge-gray"
        elif '警告' in tag or '注意' in content or '壓力' in content: 
            badge_class = "badge-orange"
        else: 
            badge_class = "badge-blue"
            
        return f"<li class='ios-list-item'><div class='ios-badge {badge_class}'>{tag}</div><div class='ios-list-text'>{content}</div></li>"
    else:
        return f"<li class='ios-list-item'><div class='ios-list-text'>{item}</div></li>"

def create_card(title, value, custom_html="", list_items=None, use_small_value=False, icon="📊", footer="", force_blue_badge=False):
    val_class = "ios-card-value-small" if use_small_value else "ios-card-value"
    
    html_parts = []
    html_parts.append('<div class="ios-card">')
    html_parts.append(f'<div class="ios-card-header"><div class="ios-icon">{icon}</div><div class="ios-card-title">{title}</div></div>')
    html_parts.append(f'<div class="{val_class}">{value}</div>')
    
    if list_items:
        # 傳遞 force_blue_badge 以強制變更特定卡片內的標籤顏色
        items_str = "".join([format_list_item(item, force_blue_badge) for item in list_items])
        html_parts.append(f"<ul class='ios-list'>{items_str}</ul>")
        
    if custom_html:
        html_parts.append(f'<div class="ios-card-content">{custom_html}</div>')
        
    if footer:
        html_parts.append(f'<div class="ios-card-footer">{footer}</div>')
        
    html_parts.append('</div>')
    
    # 透過 "".join 將 HTML 壓成單行，100% 防止 Streamlit 誤認為 Code Block 導致標籤外洩
    return "".join(html_parts)

# ==========================================
# 核心邏輯層
# ==========================================
def parse_investment_horizon(text):
    text = text.replace(" ", "")
    if any(k in text for k in ["存股", "長期", "不賣", "退休"]): return "5年以上"
    if any(k in text for k in ["短線", "當沖", "隔日沖"]): return "1-3個月"
    if "半年" in text: return "3-6個月"

    replace_map = {"一": "1", "兩": "2", "二": "2", "三": "3", "四": "4", "五": "5"}
    for k, v in replace_map.items(): text = text.replace(k, v)
    if text == "十年": text = "10年"

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
            if months <= 3: return "1-3個月"
            elif months <= 6: return "3-6個月"
            elif months <= 12: return "1年"
            elif months <= 36: return "1-3年"
            else: return "3-5年"
        return "3-6個月"

    if any(k in text for k in ["天", "日", "周", "週"]): return "1-3個月"
    return "1年" 

def get_horizon_years(horizon_str):
    mapping = {"1-3個月": 0.25, "3-6個月": 0.5, "1年": 1.0, "1-3年": 2.0, "3-5年": 4.0, "5年以上": 5.0}
    return mapping.get(horizon_str, 1.0)

class ETFAnalyzer:
    def __init__(self, raw_ticker, ticker_yf, etf_name, user_years):
        self.raw_ticker, self.ticker_yf = raw_ticker, ticker_yf
        self.is_tw_stock = ticker_yf.endswith('.TW') or ticker_yf.endswith('.TWO')
        self.etf_name, self.user_years = etf_name, user_years
        self.data, self.news, self.score, self.evaluation_details, self.institutional_data = None, [], 0, [], None

    def fetch_data(self):
        etf = yf.Ticker(self.ticker_yf)
        self.data = etf.history(period="6mo")
        if self.data is None or self.data.empty:
            if self.ticker_yf.endswith('.TW'):
                self.ticker_yf = self.ticker_yf.replace('.TW', '.TWO')
                etf = yf.Ticker(self.ticker_yf)
                self.data = etf.history(period="6mo")
        if self.data is None or len(self.data) < 20: raise ValueError(f"無法獲取 {self.ticker_yf} 足夠資料。")

    def fetch_institutional_data(self):
        if not self.is_tw_stock: return
        pure_ticker, headers = self.raw_ticker, {'User-Agent': 'Mozilla/5.0'}
        def to_shares(val):
            try: return int(str(val).replace(',', '').replace(' ', ''))
            except: return 0
        for days_back in range(5):
            target_date = self.data.index[-1]
            if target_date.tz is not None: target_date = target_date.tz_localize(None)
            target_date -= timedelta(days=days_back)
            try:
                if self.ticker_yf.endswith('.TW'):
                    date_str = target_date.strftime("%Y%m%d")
                    url = f"https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date={date_str}&selectType=ALL"
                    res = requests.get(url, headers=headers, timeout=5).json()
                    if res.get('stat') == 'OK' and 'data' in res:
                        fields = res['fields']
                        idx_id = fields.index("證券代號") if "證券代號" in fields else 0
                        idx_f = next((i for i, f in enumerate(fields) if "外" in f and "買賣超" in f), 4)
                        idx_s = next((i for i, f in enumerate(fields) if "投信" in f and "買賣超" in f), 10)
                        idx_d = next((i for i, f in enumerate(fields) if "自營商" in f and "買賣超" in f), 11)
                        for row in res['data']:
                            if row[idx_id].strip().replace('"', '') == pure_ticker:
                                self.institutional_data = {'foreign': to_shares(row[idx_f]), 'sitc': to_shares(row[idx_s]), 'dealer': to_shares(row[idx_d]), 'date': date_str}
                                return
                elif self.ticker_yf.endswith('.TWO'):
                    roc_date = f"{target_date.year - 1911}/{target_date.strftime('%m/%d')}"
                    url = f"https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php?l=zh-tw&o=json&se=EW&t=D&d={roc_date}"
                    res = requests.get(url, headers=headers, timeout=5).json()
                    if 'aaData' in res and len(res['aaData']) > 0:
                        for row in res['aaData']:
                            if row[0] == pure_ticker:
                                self.institutional_data = {'foreign': to_shares(row[4]) if len(row)>4 else 0, 'sitc': to_shares(row[10]) if len(row)>10 else 0, 'dealer': to_shares(row[13]) if len(row)>13 else 0, 'date': roc_date}
                                return
            except: continue

    def calculate_indicators(self):
        df = self.data
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['BIAS_20'] = ((df['Close'] - df['SMA_20']) / df['SMA_20']) * 100
        delta = df['Close'].diff()
        avg_gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
        avg_loss = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
        df['RSI_14'] = 100 - (100 / (1 + (avg_gain / avg_loss)))
        low_9, high_9 = df['Low'].rolling(window=9).min(), df['High'].rolling(window=9).max()
        price_diff = (high_9 - low_9).replace(0, np.nan) 
        df['RSV'] = ((df['Close'] - low_9) / price_diff) * 100
        df['RSV'] = df['RSV'].fillna(50)
        df['K'] = df['RSV'].ewm(com=2, adjust=False).mean()
        df['D'] = df['K'].ewm(com=2, adjust=False).mean()
        df['MACD'] = df['Close'].ewm(span=12, adjust=False).mean() - df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['Volume_5MA'] = df['Volume'].rolling(window=5).mean()

    def analyze_score(self):
        if len(self.data) < 2: return
        latest, prev = self.data.iloc[-1], self.data.iloc[-2]
        
        if latest['Volume_5MA'] < 500000:
            self.evaluation_details.append(f"[警告] 近5日均量偏低 ({latest['Volume_5MA']/1000:.0f}張)，需留意流動性風險。")

        bias = latest['BIAS_20']
        if pd.notna(bias):
            if bias < -5: self.score += 2; self.evaluation_details.append(f"[+2分] 20日乖離率 {bias:.2f}%，處低檔超跌。")
            elif bias > 5: self.score -= 2; self.evaluation_details.append(f"[-2分] 20日乖離率 {bias:.2f}%，偏離過高。")
            else: self.evaluation_details.append(f"[ 0分] 20日乖離正常 ({bias:.2f}%)。")
            
        rsi, k, d = latest['RSI_14'], latest['K'], latest['D']
        if pd.notna(rsi):
            if rsi < 30: self.score += 2; self.evaluation_details.append(f"[+2分] RSI進入超賣區 ({rsi:.1f})。")
            elif rsi > 70: self.score -= 2; self.evaluation_details.append(f"[-2分] RSI進入超買區 ({rsi:.1f})。")
            
        if pd.notna(k) and pd.notna(d):
            if k < 30 and k > d and prev['K'] <= prev['D']: self.score += 3; self.evaluation_details.append("[+3分] KD低檔黃金交叉。")
            elif k > 80 and k < d and prev['K'] >= prev['D']: self.score -= 3; self.evaluation_details.append("[-3分] KD高檔死亡交叉。")
            
        macd, sig = latest['MACD'], latest['MACD_Signal']
        if pd.notna(macd) and pd.notna(sig):
            if macd > sig and prev['MACD'] <= prev['MACD_Signal']: self.score += 3; self.evaluation_details.append("[+3分] MACD低檔黃金交叉。")
            elif macd < sig and prev['MACD'] >= prev['MACD_Signal']: self.score -= 3; self.evaluation_details.append("[-3分] MACD高檔死亡交叉。")
            
        # ==========================================
        # 修改：將 ETF 籌碼分析統一比照股票，呈現買賣超張數與加扣分機制
        # ==========================================
        if self.institutional_data:
            f_net = self.institutional_data['foreign'] / 1000
            s_net = self.institutional_data['sitc'] / 1000
            d_net = self.institutional_data['dealer'] / 1000
            total_net = f_net + s_net + d_net
            
            if total_net > 500:
                self.score += 2
                self.evaluation_details.append(f"[+2分] 法人單日買超 {total_net:,.0f} 張 (外資 {f_net:+.0f}, 投信 {s_net:+.0f}, 自營 {d_net:+.0f})")
            elif total_net > -100:
                self.evaluation_details.append(f"[ 0分] 法人單日中性橫盤 ({total_net:,.0f}張) (外資 {f_net:+.0f}, 投信 {s_net:+.0f}, 自營 {d_net:+.0f})")
            else:
                self.score -= 2
                self.evaluation_details.append(f"[-2分] 法人單日賣超 {abs(total_net):,.0f} 張 (外資 {f_net:+.0f}, 投信 {s_net:+.0f}, 自營 {d_net:+.0f})")

    def get_time_based_advice(self, term_type):
        s = self.score
        if term_type == "1-3個月":
            if s >= 6: return "強烈建議進場 (短線爆發力)"
            elif s >= 2: return "建議進場 (短線趨勢偏多)"
            elif s >= -1: return "中性觀望 (無明顯方向)"
            else: return "強烈不建議進場 (有修正風險)"
        elif term_type == "3-6個月":
            if s >= 4: return "強烈建議進場 (波段買點浮現)"
            elif s >= 1: return "建議分批進場 (波段趨勢尚可)"
            else: return "建議觀望 (波段仍有下探風險)"
        elif term_type == "1年":
            if s >= 2: return "建議單筆加碼 (位階偏低)"
            elif s > -4: return "建議定期定額進場 (平滑成本)"
            else: return "建議小額定期定額 (短線偏高)"
        else: return "建議長線佈局 (隨時皆是買點，時間是護城河)"

    def get_report_data(self):
        latest, recent_low = self.data.iloc[-1], self.data['Low'].tail(20).min()
        sma20, current_price = latest['SMA_20'], latest['Close']
        g_low = recent_low * 0.98 if latest['RSI_14'] < 30 else min(recent_low, current_price * 0.95)
        g_high = recent_low * 1.02 if latest['RSI_14'] < 30 else (sma20 if pd.notna(sma20) else current_price)
        matched_tier = "5年以上" if self.user_years > 5.0 else ("3-5年" if self.user_years > 3.0 else ("1-3年" if self.user_years > 1.0 else ("1年" if self.user_years > 0.5 else ("3-6個月" if self.user_years > 0.25 else "1-3個月"))))

        all_horizons = [f"[{term}] {self.get_time_based_advice(term)}" for term in ["1-3個月", "3-6個月", "1年", "1-3年", "3-5年", "5年以上"]]
        
        return {
            "type": "ETF", "name": self.etf_name, "ticker": self.ticker_yf,
            "price": current_price, "g_low": g_low, "g_high": g_high,
            "score": self.score, "matched_tier": matched_tier,
            "advice": self.get_time_based_advice(matched_tier),
            "details": self.evaluation_details, "all_horizons": all_horizons
        }

class StockEvaluator:
    def __init__(self, raw_ticker, ticker_yf, stock_name, market_label, matched_horizon_str, fm):
        self.raw_ticker, self.ticker = raw_ticker, ticker_yf
        self.stock_name, self.market_label = stock_name, market_label
        self.matched_horizon, self.user_horizon_text = matched_horizon_str, matched_horizon_str
        self.fm, self.stock, self.df, self.info = fm, yf.Ticker(self.ticker), pd.DataFrame(), {}
        self.horizons = {
            "1-3個月": {"fund": 0.1, "tech": 0.6, "chip": 0.3, "desc": "極短線依賴技術型態與法人動能"},
            "3-6個月": {"fund": 0.2, "tech": 0.5, "chip": 0.3, "desc": "短中線重視技術指標與大戶流向"},
            "1年": {"fund": 0.4, "tech": 0.4, "chip": 0.2, "desc": "中線需基本面支撐，搭配技術多頭"},
            "1-3年": {"fund": 0.6, "tech": 0.3, "chip": 0.1, "desc": "中長線看重估值，技術面抓低點"},
            "3-5年": {"fund": 0.8, "tech": 0.2, "chip": 0.0, "desc": "長線高度看重 ROE，忽略短期籌碼"},
            "5年以上": {"fund": 0.9, "tech": 0.1, "chip": 0.0, "desc": "極長線純看財務體質與配息"}
        }

    def fetch_data(self):
        self.df = self.stock.history(period="6mo")
        try: self.info = self.stock.info or {}
        except: self.info = {}
        if self.df.empty: raise ValueError(f"無法獲取股價數據。")

    def calculate_indicators(self):
        self.df['MA20'], self.df['MA60'] = self.df['Close'].rolling(20).mean(), self.df['Close'].rolling(60).mean()
        low_min, high_max = self.df['Low'].rolling(9).min(), self.df['High'].rolling(9).max()
        price_diff = (high_max - low_min).replace(0, np.nan)
        self.df['RSV'] = ((self.df['Close'] - low_min) / price_diff) * 100
        self.df['RSV'] = self.df['RSV'].fillna(50)
        self.df['K'] = self.df['RSV'].ewm(com=2, adjust=False).mean()
        self.df['D'] = self.df['K'].ewm(com=2, adjust=False).mean()
        self.df['Volume_5MA'] = self.df['Volume'].rolling(window=5).mean()

    def analyze_fundamentals(self):
        score, details = 0, []
        pe = self.info.get('trailingPE', self.info.get('forwardPE'))
        pb, roe, yield_pct, eps = self.info.get('priceToBook'), self.info.get('returnOnEquity'), self.info.get('dividendYield'), self.info.get('trailingEps')
        
        if pe is not None:
            if 0 < pe < 20: score += 10; details.append(f"[+10分] 本益比({pe:.2f}) < 20，估值具吸引力")
            elif 20 <= pe <= 35: score += 5; details.append(f"[+5分] 本益比({pe:.2f}) 處於正常區間")
            elif pe <= 0: details.append(f"[ 0分] 本益比為負，近期可能虧損")
            else: details.append(f"[ 0分] 本益比({pe:.2f}) > 35 偏高，注意溢價")
        else: score += 5; details.append("[+5分] 本益比資料未提供")

        if pb is not None:
            if 0 < pb < 3.5: score += 5; details.append(f"[+5分] 股價淨值比({pb:.2f}) 相對安全")
            else: details.append(f"[ 0分] 股價淨值比({pb:.2f}) 偏高")
        else: score += 2.5; details.append("[+2.5分] 淨值比資料未提供")

        if roe is not None:
            roe_val = roe * 100
            if roe_val > 12: score += 10; details.append(f"[+10分] 近四季 ROE({roe_val:.2f}%) > 12%，效率佳")
            elif roe_val > 5: score += 5; details.append(f"[+5分] 近四季 ROE({roe_val:.2f}%) 表現尚可")
            else: details.append(f"[ 0分] 近四季 ROE({roe_val:.2f}%) 偏低")
        else: score += 5; details.append("[+5分] ROE資料未提供")

        if yield_pct is not None:
            yield_val = yield_pct * 100
            if yield_val > 4: score += 5; details.append(f"[+5分] 預估殖利率({yield_val:.2f}%) > 4%，具保護")
            else: details.append(f"[ 0分] 殖利率({yield_val:.2f}%) 偏低")
        else: score += 2.5; details.append("[+2.5分] 殖利率資料未提供")

        return score, details, eps

    def analyze_technicals(self):
        score, details = 0, []
        latest, prev = self.df.iloc[-1], self.df.iloc[-2]
        if latest['Volume_5MA'] < 500000: details.append(f"[警告] 近5日均量低 ({latest['Volume_5MA']/1000:.0f}張)，留意流動性")

        if latest['Close'] > latest['MA20'] > latest['MA60']: score += 15; details.append("[+15分] 股價 > 月線 > 季線，多頭排列")
        elif latest['Close'] < latest['MA20'] and latest['MA20'] < latest['MA60']: details.append("[ 0分] 技術面空頭走勢，不建議接刀")
        else: score += 5; details.append("[+5分] 均線交織，區間盤整階段")
        
        if latest['K'] < 30:
            score += 10; details.append(f"[+10分] KD低檔超賣 (K:{latest['K']:.1f})")
            if latest['K'] > latest['D'] and prev['K'] <= prev['D']: score += 5; details.append("[訊號] KD 低檔黃金交叉")
        elif latest['K'] > 80: details.append(f"[ 0分] KD高檔超買 (K:{latest['K']:.1f})，注意過熱")
        else: score += 5; details.append(f"[+5分] KD指標位於中性區間 (K:{latest['K']:.1f})")
        
        recent_low, recent_high = self.df['Low'].tail(20).min(), self.df['High'].tail(20).max()
        if latest['Close'] <= recent_low * 1.05: score += 10; details.append(f"[+10分] 接近近20日支撐點({recent_low:.2f})")
        return score, details, recent_low, recent_high

    def analyze_chips(self):
        score, details = 0, []
        if self.market_label == "美股/全球":
            score += 10; details.append("[+10分] 海外市場不適用台灣籌碼分析")
            return score, details

        start_date = (datetime.date.today() - datetime.timedelta(days=40)).strftime("%Y-%m-%d")
        try:
            df_inst = self.fm.taiwan_stock_institutional_investors(stock_id=self.raw_ticker, start_date=start_date)
            if df_inst is not None and not df_inst.empty:
                df_inst['net_buy'] = df_inst['buy'] - df_inst['sell']
                recent_3_days_net = df_inst.groupby('date')['net_buy'].sum().tail(3).sum() / 1000
                if recent_3_days_net > 500: score += 10; details.append(f"[+10分] 法人近3日買超 {recent_3_days_net:,.0f} 張")
                elif recent_3_days_net > -100: score += 5; details.append(f"[+5分] 法人近3日中性橫盤 ({recent_3_days_net:,.0f}張)")
                else: details.append(f"[ 0分] 法人近3日賣超 {abs(recent_3_days_net):,.0f} 張")
            else: score += 5; details.append("[+5分] 近期無法人進出數據")

            df_shares = self.fm.taiwan_stock_holding_shares_per(stock_id=self.raw_ticker, start_date=start_date)
            if df_shares is not None and not df_shares.empty:
                df_big_holders = df_shares[df_shares['HoldingSharesLevel'] == 'more than 1,000,001'].sort_values(by='date')
                if len(df_big_holders) >= 2:
                    diff = df_big_holders['percent'].iloc[-1] - df_big_holders['percent'].iloc[-2]
                    if diff > 0.1: score += 10; details.append(f"[+10分] 千張大戶單週增加 {diff:+.2f}%")
                    elif diff < -0.1: details.append(f"[ 0分] 千張大戶單週減少 {abs(diff):-.2f}%")
                    else: score += 5; details.append(f"[+5分] 千張大戶持股比率穩定")
                else: score += 5; details.append("[+5分] 集保大戶數據不足")
            else: score += 5; details.append("[+5分] 未獲取股權分散數據")
        except Exception: 
            score += 10; details.append("[+10分] API 限制，給予中立計分")
        return score, details

    def _get_advice_level(self, total_score):
        if total_score >= 75: return "強烈建議進場"
        elif total_score >= 60: return "建議進場"
        elif total_score >= 45: return "中性觀望為主"
        elif total_score >= 30: return "不建議進場"
        else: return "強烈不建議進場"

    def get_report_data(self):
        self.fetch_data()
        self.calculate_indicators()
        fund_score, fund_details, eps = self.analyze_fundamentals()
        tech_score, tech_details, support, resistance = self.analyze_technicals()
        chip_score, chip_details = self.analyze_chips()

        f_pct, t_pct, c_pct = (fund_score / 30) * 100, (tech_score / 40) * 100, (chip_score / 20) * 100
        user_w = self.horizons[self.matched_horizon]
        weighted_f, weighted_t, weighted_c = f_pct * user_w['fund'], t_pct * user_w['tech'], c_pct * user_w['chip']
        max_f, max_t, max_c = user_w['fund'] * 100, user_w['tech'] * 100, user_w['chip'] * 100

        user_total = weighted_f + weighted_t + weighted_c
        
        all_horizons = []
        for horizon, w in self.horizons.items():
            h_total = (f_pct * w['fund']) + (t_pct * w['tech']) + (c_pct * w['chip'])
            all_horizons.append(f"[{horizon}] {self._get_advice_level(h_total)}")

        return {
            "type": "Stock", "name": self.stock_name, "ticker": self.ticker,
            "price": self.df['Close'].iloc[-1], "eps": eps,
            "support": support, "resistance": resistance,
            "user_horizon": self.user_horizon_text, "matched_horizon": self.matched_horizon,
            "user_total": user_total, "advice": self._get_advice_level(user_total),
            "strategy": user_w['desc'],
            "weights": {"fund": max_f, "tech": max_t, "chip": max_c},
            "scores": {"fund": weighted_f, "tech": weighted_t, "chip": weighted_c},
            "details_fund": fund_details, "details_tech": tech_details, "details_chip": chip_details,
            "all_horizons": all_horizons
        }

class MasterRoutingSystem:
    def __init__(self):
        self.fm, self._stock_info_cache = DataLoader(), None
    def auto_detect_type(self, raw_ticker):
        is_tw = any(char.isdigit() for char in raw_ticker)
        ticker_yf, is_etf, stock_name, market_label = raw_ticker, False, "未知名稱", "美股/全球"
        if is_tw:
            try:
                if self._stock_info_cache is None: self._stock_info_cache = self.fm.taiwan_stock_info()
                target = self._stock_info_cache[self._stock_info_cache['stock_id'] == raw_ticker]
                if not target.empty:
                    stock_name = target.iloc[0]['stock_name']
                    industry, market_type = str(target.iloc[0].get('industry_category', '')).upper(), str(target.iloc[0].get('type', '')).lower()
                    market_label = "上櫃" if 'tpex' in market_type or 'otc' in market_type else "上市"
                    ticker_yf = f"{raw_ticker}.TWO" if market_label == "上櫃" else f"{raw_ticker}.TW"
                    if 'ETF' in industry or raw_ticker.startswith('00'): is_etf = True
                else:
                    ticker_yf = f"{raw_ticker}.TW"
                    if raw_ticker.startswith('00'): is_etf = True
            except:
                ticker_yf = f"{raw_ticker}.TW"
                if raw_ticker.startswith('00'): is_etf = True
        try:
            info = yf.Ticker(ticker_yf).info or {}
            if info.get('quoteType') == 'ETF': is_etf = True
            elif info.get('quoteType') == 'EQUITY': is_etf = False
            if stock_name == "未知名稱": stock_name = info.get('shortName', info.get('longName', raw_ticker))
        except: pass
        return ticker_yf, is_etf, stock_name, market_label

# ==========================================
# 網頁 UI 綁定層
# ==========================================
st.markdown('<div class="ios-large-title">台美股與 ETF 量化決策系統</div>', unsafe_allow_html=True)
st.markdown('<div class="ios-sub-title">Quantitative Decision System for Taiwan and US Stocks and ETFs</div>', unsafe_allow_html=True)

with st.container():
    col1, col2 = st.columns(2)
    with col1: raw_ticker = st.text_input("股票或 ETF 代號, 例如: 0050, 2330, TSLA", value="2412").strip().upper().replace('.TW', '').replace('.TWO', '')
    with col2: horizon_input = st.text_input("預計投資年限, 例如: 1年, 當沖, 退休, 10年", value="1年").strip()

st.markdown("<br>", unsafe_allow_html=True)

# 調整：修改排列欄位並放置於第一列，使按鈕切齊畫面左側
btn_col1, btn_col2 = st.columns([1, 4])
with btn_col1: start_analysis = st.button("開始分析")

if start_analysis and raw_ticker:
    with st.spinner("連接市場資料庫運算中..."):
        try:
            system = MasterRoutingSystem()
            matched_horizon = parse_investment_horizon(horizon_input)
            horizon_years = get_horizon_years(matched_horizon)
            ticker_yf, is_etf, stock_name, market_label = system.auto_detect_type(raw_ticker)
            
            st.markdown("<hr style='border:1px solid rgba(150,150,150,0.1); margin: 32px 0;'>", unsafe_allow_html=True)
            st.markdown(f'<div class="ios-large-title">{stock_name}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="ios-sub-title">{ticker_yf} ‧ {market_label}</div>', unsafe_allow_html=True)

            if is_etf:
                analyzer = ETFAnalyzer(raw_ticker, ticker_yf, stock_name, horizon_years)
                analyzer.fetch_data()
                analyzer.fetch_institutional_data()
                analyzer.calculate_indicators()
                analyzer.analyze_score()
                data = analyzer.get_report_data()
                
                c1, c2, c3 = st.columns(3)
                with c1: st.markdown(create_card("最新收盤價", f"${data['price']:.2f}", icon="💵"), unsafe_allow_html=True)
                with c2: st.markdown(create_card("承接區間", f"${data['g_low']:.2f} - ${data['g_high']:.2f}", footer="需配合折溢價判斷", icon="🎯"), unsafe_allow_html=True)
                with c3: st.markdown(create_card("綜合評分", f"{data['score']}", footer="量化多空指標", icon="⭐️"), unsafe_allow_html=True)
                
                st.markdown(create_card(f"智能投資建議 ‧ {horizon_input}", data['advice'], footer="此建議由演算法根據您選擇的時間長度，動態配置參數權重後生成。", icon="🧠"), unsafe_allow_html=True)

                c4, c5 = st.columns(2)
                with c4: st.markdown(create_card("技術面與籌碼解析", "分析日誌", list_items=data['details'], use_small_value=True, icon="📝"), unsafe_allow_html=True)
                
                # 調整：加入 force_blue_badge=True 讓其他投資年限標籤強制顯示藍色
                with c5: st.markdown(create_card("跨週期策略", "其他投資年限", list_items=data['all_horizons'], use_small_value=True, icon="⏱️", force_blue_badge=True), unsafe_allow_html=True)

            else:
                evaluator = StockEvaluator(raw_ticker, ticker_yf, stock_name, market_label, matched_horizon, system.fm)
                data = evaluator.get_report_data()
                
                c1, c2, c3 = st.columns(3)
                with c1: st.markdown(create_card("最新收盤價", f"${data['price']:,.2f}", icon="💵"), unsafe_allow_html=True)
                with c2: st.markdown(create_card("短線支撐區間", f"${data['support']:,.2f} - ${data['support']*1.05:,.2f}", footer="波段防守點", icon="🛡️"), unsafe_allow_html=True)
                eps_text = f"${data['eps']:.2f}" if data['eps'] is not None else "N/A"
                with c3: st.markdown(create_card("近四季 EPS", eps_text, footer="基本面獲利指標", icon="📈"), unsafe_allow_html=True)
                
                # 特製：彩色比例膠囊條 (Weight Bar)
                strategy_html = "".join([
                    "<div class='ios-weight-bar'>",
                    f"<div class='weight-item'><span class='dot dot-blue'></span>基本面 {data['weights']['fund']:.0f}%</div>",
                    f"<div class='weight-item'><span class='dot dot-purple'></span>技術面 {data['weights']['tech']:.0f}%</div>",
                    f"<div class='weight-item'><span class='dot dot-orange'></span>籌碼面 {data['weights']['chip']:.0f}%</div>",
                    "</div>",
                    f"<div class='ios-strategy-desc'>{data['strategy']}</div>"
                ])
                
                val_html = f"{data['advice']} <span style='font-size:22px; color:#8E8E93;'>({data['user_total']:.1f}/100)</span>"
                st.markdown(create_card(f"客製化投資決策 ‧ {data['user_horizon']}", val_html, custom_html=strategy_html, icon="🧠"), unsafe_allow_html=True)
                
                c4, c5 = st.columns(2)
                with c4: st.markdown(create_card("基本面價值", f"{data['scores']['fund']:.1f} / {data['weights']['fund']:.0f}", list_items=data['details_fund'], use_small_value=True, icon="🏢"), unsafe_allow_html=True)
                tech_list = data['details_tech'].copy()
                tech_list.append(f"[注意] 參考波段壓力位: ${data['resistance']:,.2f}")
                with c5: st.markdown(create_card("技術面擇時", f"{data['scores']['tech']:.1f} / {data['weights']['tech']:.0f}", list_items=tech_list, use_small_value=True, icon="📊"), unsafe_allow_html=True)

                c6, c7 = st.columns(2)
                chip_footer = "極長線演算法已將短期籌碼波動降噪 (權重歸零)" if data['weights']['chip'] == 0 else ""
                with c6: st.markdown(create_card("大戶籌碼流向", f"{data['scores']['chip']:.1f} / {data['weights']['chip']:.0f}", list_items=data['details_chip'], footer=chip_footer, use_small_value=True, icon="🏦"), unsafe_allow_html=True)
                
                # 調整：加入 force_blue_badge=True 讓其他投資年限標籤強制顯示藍色
                with c7: st.markdown(create_card("跨週期策略", "其他投資年限", list_items=data['all_horizons'], use_small_value=True, icon="⏱️", force_blue_badge=True), unsafe_allow_html=True)

        except Exception as e:
            st.error(f"⚠️ 系統執行發生錯誤，請檢查您的網路連線或證券代號是否正確。(Error: {e})")