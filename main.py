import requests
import time
import json
import os
from datetime import datetime

# ================= ⚙️ 配置区域 =================
#该版本，可以随时推送信息，包括补仓信息

# 1. TG 配置 私人监控频道
TG_BOT_TOKEN = ""
TG_CHAT_ID = "-"

# 2. 扫描间隔 (秒)
CHECK_INTERVAL = 10 

# 3. 文件路径
SNAPSHOT_FILE = "positions_snapshot.json"
ADDRESS_FILE = "address.txt"

# ===============================================

def log(text):
    """打印带时间的日志"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {text}")

def send_telegram_message(text):
    """发送 TG 消息 (直连模式)"""
    if "你的_" in TG_BOT_TOKEN: return
    
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        # 海外服务器直连，无需 proxies
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        log(f"❌ TG 发送失败: {e}")

def load_snapshot():
    if not os.path.exists(SNAPSHOT_FILE): return {}
    try:
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return {}

def save_snapshot(data):
    try:
        with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except: pass

def process_monitor():
    old_snapshot = load_snapshot()
    new_snapshot = {} 
    
    # 读取地址文件
    try:
        with open(ADDRESS_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except:
        log(f"❌ 找不到 {ADDRESS_FILE}，请确认文件存在")
        return

    for line in lines:
        line = line.strip()
        if not line or '-' not in line: continue
        
        parts = line.rsplit('-', 1)
        alias = parts[0].strip()
        address = parts[1].strip()

        # 地址合法性检查
        if not address.startswith("0x") or len(address) < 40:
            continue
        
        # 初始化新快照槽位
        if address not in new_snapshot: new_snapshot[address] = {}

        # 请求 API (直连)
        url = f"https://data-api.polymarket.com/positions?user={address}"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                # 失败时保留旧数据
                new_snapshot[address] = old_snapshot.get(address, {})
                continue
            positions = resp.json()
        except:
            new_snapshot[address] = old_snapshot.get(address, {})
            continue

        for pos in positions:
            # 忽略极小余额
            current_size = float(pos.get('size', 0))
            if current_size < 0.1: continue 

            asset_info = pos.get('asset')
            asset_id = asset_info.get('id') if isinstance(asset_info, dict) else asset_info
            if not asset_id: continue

            # 获取市值 (用于显示)
            current_value = float(pos.get('currentValue', 0))

            # --- 🔥 核心对比逻辑 ---
            user_old_data = old_snapshot.get(address, {})
            prev_size = user_old_data.get(asset_id, 0)

            diff = current_size - prev_size

            # 只要增量 > 0.01 就推送
            if diff > 0.01:
                
                # 初始化保护：如果是新加入的地址或首次运行
                if address not in old_snapshot:
                    print(f"   ⚡ [初始化] {alias}: 录入持仓 {current_size:.1f} (不推送)")
                else:
                    # 只有真正的增量才推送
                    market_name = pos.get('title') or "Unknown Market"
                    outcome = pos.get('outcome')
                    avg_price = float(pos.get('avgPrice', 0))
                    
                    action_title = "🚀 新开仓" if prev_size == 0 else "➕ 加仓"

                    msg = (
                        f"{action_title}: <b>{alias}</b>\n\n"
                        f"🎯 <b>{market_name}</b>\n"
                        f"🎲 方向: {outcome}\n"
                        f"🔥 <b>买入: +{diff:,.1f}</b>\n"
                        f"📦 总持仓: {current_size:,.1f}\n"
                        f"💰 均价: ${avg_price:.3f}\n"
                        f"💵 <b>市值: ${current_value:,.2f}</b>\n"
                        f"<a href='https://polymarket.com/profile/{address}'>查看主页</a>"
                    )
                    
                    log(f"🔔 推送: {alias} {action_title} +{diff} (市值 ${current_value:.0f})")
                    send_telegram_message(msg)

            # 更新快照
            new_snapshot[address][asset_id] = current_size

    # 保存文件
    save_snapshot(new_snapshot)

if __name__ == "__main__":
    print("\n========================================")
    print("🤖 Polymarket 监控 (服务器直连版)")
    print("🌍 环境: 海外服务器 (无代理)")
    print("✅ 功能: 增量监控 + 市值显示")
    print("========================================\n")

    # 连接测试
    print("正在测试 TG 连接...", end="")
    try:
        requests.get(f"https://api.telegram.org/bot{TG_BOT_TOKEN}/getMe", timeout=5)
        print(" [OK]")
    except Exception as e:
        print(f" [失败] 请检查服务器网络: {e}")

    try:
        while True:
            process_monitor()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        print("\n停止")