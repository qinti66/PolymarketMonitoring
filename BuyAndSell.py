import requests
import time
import json
import os
from datetime import datetime

# ================= ⚙️ 配置区域 =================

# 1. TG 配置 公开监控频道
TG_BOT_TOKEN = ""
TG_CHAT_ID = "-"

# 2. 本地代理配置 (关键修改点 !!!)
# 请查看你的 VPN 软件设置，确认 HTTP/SOCKS 端口
PROXY_PORT = "7897"  # 如果是用 v2ray 可能需要改成 10809 或 1080

PROXIES = {
    "http": f"http://127.0.0.1:{PROXY_PORT}",
    "https": f"http://127.0.0.1:{PROXY_PORT}",
}

# 3. 扫描间隔 (秒)
CHECK_INTERVAL = 60 

# 4. 文件路径
SNAPSHOT_FILE = "positions_snapshot.json"
ADDRESS_FILE = "address.txt"

# ===============================================

def log(text):
    """打印带时间的日志"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {text}")

def send_telegram_message(text):
    """发送 TG 消息 (带代理)"""
    if "你的_" in TG_BOT_TOKEN: return
    
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        # ✅ 这里加入了 proxies 参数
        requests.post(url, json=payload, proxies=PROXIES, timeout=10)
    except Exception as e:
        log(f"❌ TG 发送失败 (请检查代理): {e}")

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

        if not address.startswith("0x") or len(address) < 40:
            continue
        
        # 初始化该地址的新快照
        if address not in new_snapshot: new_snapshot[address] = {}

        # 请求 API (带代理)
        url = f"https://data-api.polymarket.com/positions?user={address}"
        try:
            # ✅ 这里加入了 proxies 参数
            resp = requests.get(url, proxies=PROXIES, timeout=10)
            if resp.status_code != 200:
                new_snapshot[address] = old_snapshot.get(address, {})
                continue
            positions_list = resp.json()
        except Exception as e:
            # log(f"API请求失败: {e}") # 调试时可以打开
            new_snapshot[address] = old_snapshot.get(address, {})
            continue

        # --- 1. 构建当前持仓映射 ---
        current_positions_map = {}
        for pos in positions_list:
            asset_info = pos.get('asset')
            asset_id = asset_info.get('id') if isinstance(asset_info, dict) else asset_info
            if asset_id:
                current_positions_map[asset_id] = pos

        # --- 2. 获取所有涉及的 Asset ID (旧 + 新) ---
        user_old_data = old_snapshot.get(address, {})
        all_asset_ids = set(current_positions_map.keys()) | set(user_old_data.keys())

        # --- 3. 遍历对比 ---
        for asset_id in all_asset_ids:
            # 获取新数据
            pos_data = current_positions_map.get(asset_id)
            
            if pos_data:
                current_size = float(pos_data.get('size', 0))
                current_value = float(pos_data.get('currentValue', 0))
                market_name = pos_data.get('title') or "Unknown Market"
                outcome = pos_data.get('outcome') or "?"
                avg_price = float(pos_data.get('avgPrice', 0))
            else:
                # 清仓状态
                current_size = 0.0
                current_value = 0.0
                market_name = "🚫 已清仓/未知市场"
                outcome = "?"
                avg_price = 0.0

            # 获取旧数据
            prev_size = user_old_data.get(asset_id, 0)
            diff = current_size - prev_size

            # 过滤微小波动
            if abs(diff) < 0.01:
                if current_size > 0.01:
                    new_snapshot[address][asset_id] = current_size
                continue

            # --- 4. 判断买卖 ---
            
            # >>> A. 买入 <<<
            if diff > 0.01:
                if address not in old_snapshot:
                    print(f"   ⚡ [初始化] {alias}: 录入持仓 {current_size:.1f}")
                else:
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
                    log(f"🔔 推送买入: {alias} +{diff:.1f}")
                    send_telegram_message(msg)

            # >>> B. 卖出 (修复逻辑) <<<
            elif diff < -0.01:
                if address not in old_snapshot:
                    pass
                else:
                    action_title = "👋 清仓" if current_size < 0.1 else "🔻 减仓/止盈"
                    msg = (
                        f"{action_title}: <b>{alias}</b>\n\n"
                        f"🎯 <b>{market_name}</b>\n"
                        f"🎲 方向: {outcome}\n"
                        f"💸 <b>卖出: {diff:,.1f}</b>\n"
                        f"📦 剩余: {current_size:,.1f}\n"
                        f"💵 <b>余值: ${current_value:,.2f}</b>\n"
                        f"<a href='https://polymarket.com/profile/{address}'>查看主页</a>"
                    )
                    log(f"🔔 推送卖出: {alias} {diff:.1f}")
                    send_telegram_message(msg)

            # 更新快照 (仅保留非零持仓)
            if current_size > 0.01:
                new_snapshot[address][asset_id] = current_size

    save_snapshot(new_snapshot)

if __name__ == "__main__":
    print("\n========================================")
    print("🤖 Polymarket 监控 (本地代理版)")
    print(f"🔌 代理地址: 127.0.0.1:{PROXY_PORT}")
    print("✅ 功能: 增量监控 + 卖出推送 + 市值")
    print("========================================\n")

    # 连接测试
    print("正在测试 TG 连接 (通过代理)...", end="")
    try:
        # ✅ 这里加入了 proxies 参数
        requests.get(f"https://api.telegram.org/bot{TG_BOT_TOKEN}/getMe", proxies=PROXIES, timeout=5)
        print(" [OK]")
    except Exception as e:
        print(f"\n[失败] 无法连接 TG，请检查 VPN 是否开启，以及端口是否为 {PROXY_PORT}")
        print(f"错误信息: {e}")
        exit() # 连接失败直接退出，防止空跑

    try:
        while True:
            process_monitor()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        print("\n停止")