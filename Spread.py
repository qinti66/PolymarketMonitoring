import requests

def find_missing_game():
    url = "https://gamma-api.polymarket.com/events"
    
    print("--- 正在全量扫描 NBA 比赛，寻找消失的第 8 场 ---")
    
    # 扩大 limit 确保抓取所有活跃比赛
    params = {
        "limit": 100,
        "active": "true",
        "closed": "false",
        "tag_slug": "nba",
        "order": "startDate",
        "ascending": "true"
    }
    
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, params=params, headers=headers, timeout=10)
    events = r.json()
    
    target_date = "2026-01-24"
    
    captured = []
    suspicious = []
    
    for event in events:
        title = event.get('title')
        slug = event.get('slug')
        
        # 分类：包含目标日期的 vs 不包含的
        if target_date in slug:
            captured.append(f"✅ [已捕获] {title}\n   URL: .../{slug}")
        else:
            # 这里面很可能藏着那第8场比赛
            suspicious.append(f"⚠️ [漏网之鱼?] {title}\n   URL: .../{slug}")

    # --- 输出结果 ---
    print(f"\n一共扫描到 {len(events)} 场活跃 NBA 比赛。\n")
    
    print(f"--- 匹配到 '{target_date}' 的比赛 ({len(captured)} 场) ---")
    # for item in captured: print(item) #这部分不打印了，节省屏幕空间
    print("(已隐藏 7 场匹配的比赛...)")
    
    print(f"\n--- ❌ 没有匹配该日期的比赛 (共 {len(suspicious)} 场) ---")
    print(">>> 请在这里面找那第 8 场比赛，看看它的 URL 长什么样：\n")
    
    for item in suspicious:
        print(item)
        print("-" * 40)

if __name__ == "__main__":
    find_missing_game()