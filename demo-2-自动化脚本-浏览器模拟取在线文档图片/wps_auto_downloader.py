import os
import re
import time
import requests
import hashlib
from playwright.sync_api import sync_playwright

def calculate_md5(filepath):
    """计算文件的 MD5 哈希值以判断内容是否一致"""
    hash_md5 = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return None

def main():
    print("=" * 50)
    print("WPS 文档一键抓图下载器")
    print("=" * 50)
    
    url = input("请输入 WPS 文档链接地址: ").strip()
    if not url:
        print("未输入地址，退出。")
        return

    # 设置一个持久化的用户数据目录，用于保存登录凭证
    user_data_dir = os.path.join(os.getcwd(), 'playwright_data')
    
    # 运用集合自动去重下载链接
    captured_urls = set()
    
    def handle_response(response):
        """后台静默网络拦截处理，捕捉原图链接"""
        req_url = response.url
        if req_url.startswith('blob:') or req_url.startswith('data:'): 
            return
        
        is_target = False
        # 特征 1：包含 /api/file/ 且不包含 thumbnail（如果是签名的话）
        if ('/api/file/' in req_url and 'thumbnail' not in req_url) or \
           ('img.qwps.cn' in req_url and 'thumbnail' not in req_url):
            is_target = True
        # 特征 2：或者直接根据常见图片扩展名正则判断
        elif re.search(r'\.(jpg|jpeg|png|webp|bmp)(\?|$)', req_url, re.IGNORECASE):
            # 过滤掉明显的 UI 小图标
            if 'thumbnail' not in req_url and 'avatar' not in req_url and 'icon' not in req_url:
                is_target = True
                
        # 也可以放行之前那种 weboffice-temporary... 的缩略图并靠大小过滤
        if 'weboffice-temporary.ks3-cn-beijing.wpscdn.cn/thumbnail' in req_url:
            is_target = True

        if is_target and req_url not in captured_urls:
            captured_urls.add(req_url)
            print(f"📸 [捕获第 {len(captured_urls)} 张]: {req_url[:80]}...")

    print("\n🚀 正在启动浏览器...")
    with sync_playwright() as p:
        # launch_persistent_context 可以用来保存你的登录 Cookie 等。
        # 这样您就不需要每次使用都去重新登录。
        browser_context = p.chromium.launch_persistent_context(
            user_data_dir, 
            headless=False, # 可以看到浏览器界面
            viewport={"width": 1280, "height": 800}
        )
        
        page = browser_context.pages[0] if len(browser_context.pages) > 0 else browser_context.new_page()
        # 挂载拦截器
        page.on("response", handle_response)
        
        print(f"👉 导航至 {url} ...")
        page.goto(url)
        
        print("\n" + "!" * 50)
        print("请在弹出的浏览器中做以下准备：")
        print("1. 登录账号密码（如果需要的话，后续会自动保持在这个目录里）。")
        print("2. 进入文档并在图片上【手工双击图片】切入“大图浏览/下一张”那个模式。")
        print("!" * 50)
        input("\n准备好之后，请在这里按【回车键】让脚本接管帮你自动翻页...\n> ")
        
        print("\n✅ 开始自动翻页 (若需中途停止可按 Ctrl+C)。")
        
        prev_count = 0
        no_change_count = 0
        MAX_NO_CHANGE = 3
        
        try:
            while no_change_count < MAX_NO_CHANGE:
                # 定位浏览器里的大图下一页按钮
                next_btn = page.locator(".icons-24-image_next")
                if next_btn.count() > 0:
                    try:
                        next_btn.first.click()
                        print("👉 点了【下一张】")
                    except Exception as e:
                        print(f"⚠️ 点击下一张发生异常: {e}")
                else:
                    print("⚠️ 好像找不到 .icons-24-image_next 这个下一页按钮了，是当前没在大图模式吗？")
                    
                # 给予网络请求及页面加载响应时间
                time.sleep(2.5) 
                
                curr_count = len(captured_urls)
                if curr_count > prev_count:
                    prev_count = curr_count
                    no_change_count = 0
                else:
                    no_change_count += 1
                    print(f"⏳ 这次没发现新图片连接呀 ({no_change_count}/{MAX_NO_CHANGE})，是不是到最后一张了...")
                    
        except KeyboardInterrupt:
            print("\n🛑 用户中途停止了翻页。")
            
        print(f"\n✅ 自动翻页宣告结束，总计捕捉到 {len(captured_urls)} 个网络图片链接。")
        
        # 为了降低下载失败率，收集浏览器目前的所有的 Cookie 当鉴权传给 request
        cookies = browser_context.cookies()
        req_cookies = {c['name']: c['value'] for c in cookies}
        
    # --- 流程第二步：下载 ---
    print("\n⬇️ 开始把捕捉到的链接进行本地下载...")
    download_dir = "downloads"
    os.makedirs(download_dir, exist_ok=True)
    
    headers = {
        'Referer': 'https://www.kdocs.cn/',
        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for idx, orig_url in enumerate(captured_urls):
        try:
            resp = requests.get(orig_url, headers=headers, cookies=req_cookies, timeout=15)
            # 根据大小判断是否是有效原图 (抛弃极小的 404 图标或者损坏 SVG)
            if resp.status_code == 200 and len(resp.content) > 1000:
                filename = f"image_{idx+1}.jpg"
                filepath = os.path.join(download_dir, filename)
                with open(filepath, 'wb') as img_file:
                    img_file.write(resp.content)
                print(f"  ✅ 成功本地保存: {filename}")
            else:
                print(f"  ❌ 跳过下载，状态码 {resp.status_code}，大小 {len(resp.content)} 字节")
        except Exception as e:
            print(f"  ❌ 网络报错: {e}")
            
    # --- 流程第三步：运行图片清理与无缝继位重命名 (复用刚才的设计) ---
    print(f"\n🔄 对 {download_dir} 文件夹内的结果执行去重清理与顺序重命名 ...")
    seen_hashes = set()
    removed_count = 0
    
    files = []
    for f in os.listdir(download_dir):
        if re.match(r'^image_\d+\.(png|jpg|jpeg|webp|bmp|gif)$', f.lower()):
            files.append(f)
            
    def sort_key(filename):
        nums = re.findall(r'\d+', filename)
        return int(nums[0]) if nums else 0
        
    files.sort(key=sort_key)
    
    new_index = 1
    for filename in files:
        filepath = os.path.join(download_dir, filename)
        if os.path.isfile(filepath):
            file_hash = calculate_md5(filepath)
            
            if not file_hash:
                continue
                
            if file_hash in seen_hashes:
                print(f"🗑️ 删除相同的重复内容: {filename}")
                try:
                    os.remove(filepath)
                    removed_count += 1
                except Exception:
                    pass
            else:
                seen_hashes.add(file_hash)
                
                ext = os.path.splitext(filename)[1]
                new_filename = f"image_{new_index}{ext}"
                new_filepath = os.path.join(download_dir, new_filename)
                
                if filename != new_filename:
                    print(f"📝 排列重命名: {filename} -> {new_filename}")
                    try:
                        os.rename(filepath, new_filepath)
                    except Exception:
                        pass
                new_index += 1
                
    print("=" * 50)
    print("🎉 全流程任务完成！")
    print(f"剔除重复图后，最终在 '{download_dir}' 里为您保留了 {len(seen_hashes)} 张按顺序重排的图片。")

if __name__ == "__main__":
    main()
