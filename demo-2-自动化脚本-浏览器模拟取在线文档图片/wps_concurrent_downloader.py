import os
import re
import time
import requests
import hashlib
import threading
from queue import Queue
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

def download_worker(q, download_dir, headers, cookies_dict):
    """后台下载线程工作函数：持续从队列读取新链接并直接下载"""
    while True:
        task = q.get()
        if task is None:  # 如果收到 None 任务代表主程序告诉我们要结束了
            q.task_done()
            break
            
        idx, orig_url = task
        print(f"\n⬇️ 开始下载第 {idx} 张图片...")
        try:
            resp = requests.get(orig_url, headers=headers, cookies=cookies_dict, timeout=15)
            # 根据大小判断是否是有效原图
            if resp.status_code == 200 and len(resp.content) > 1000:
                filename = f"image_{idx}.jpg"
                filepath = os.path.join(download_dir, filename)
                with open(filepath, 'wb') as img_file:
                    img_file.write(resp.content)
                print(f"  ✅ 成功本地保存: {filename}")
            else:
                print(f"  ❌ 跳过下载: {orig_url[:60]}... (状态码 {resp.status_code}，大小 {len(resp.content)} 字节)")
        except Exception as e:
            print(f"  ❌ 第 {idx} 张图网络报错: {e}")
            
        # 标记该任务已完成
        q.task_done()

def main():
    print("=" * 50)
    print("WPS 文档一键抓图下载器（边截边下并发增强版）")
    print("=" * 50)
    
    url = input("请输入 WPS 文档链接地址: ").strip()
    if not url:
        print("未输入地址，退出。")
        return

    # 设置目录
    user_data_dir = os.path.join(os.getcwd(), 'playwright_data')
    download_dir = "downloads_concurrent"
    os.makedirs(download_dir, exist_ok=True)
    
    # 使用集合去重拦截，使用多线程安全队列进行通信
    captured_urls = set()
    download_queue = Queue()
    
    # 下载所需头信息和全页面的 Cookie（为了通过反爬验证）
    req_cookies = {}
    headers = {
        'Referer': 'https://www.kdocs.cn/',
        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # 将图片计数提出来以便跨线程分配连续编号
    global_img_counter = [0] 

    # 启动后台常驻下载线程
    dl_thread = threading.Thread(target=download_worker, args=(download_queue, download_dir, headers, req_cookies))
    dl_thread.daemon = True
    dl_thread.start()

    def handle_response(response):
        """后台静默网络拦截处理，每次捕获瞬间立即让后线程开始下载"""
        req_url = response.url
        if req_url.startswith('blob:') or req_url.startswith('data:'): 
            return
        
        is_target = False
        if ('/api/file/' in req_url and 'thumbnail' not in req_url) or \
           ('img.qwps.cn' in req_url and 'thumbnail' not in req_url):
            is_target = True
        elif re.search(r'\.(jpg|jpeg|png|webp|bmp)(\?|$)', req_url, re.IGNORECASE):
            if 'thumbnail' not in req_url and 'avatar' not in req_url and 'icon' not in req_url:
                is_target = True
                
        # 兼容 ks3 加密链接的旧类型
        if 'weboffice-temporary.ks3-cn-beijing.wpscdn.cn/thumbnail' in req_url:
            is_target = True

        if is_target and req_url not in captured_urls:
            captured_urls.add(req_url)
            global_img_counter[0] += 1
            idx = global_img_counter[0]
            
            print(f"\n📸 [实时捕获第 {idx} 张]: 放入下载队列并发处理中！")
            
            # 使用 try-except 以防 frame / context 拿不到 cookie 时报错崩溃
            try:
                context_cookies = response.frame.page.context.cookies()
                req_cookies.clear()
                req_cookies.update({c['name']: c['value'] for c in context_cookies})
            except Exception:
                pass

            # 通知后台线程进行异步下载
            download_queue.put((idx, req_url))

    print("\n🚀 正在启动浏览器...")
    with sync_playwright() as p:
        browser_context = p.chromium.launch_persistent_context(
            user_data_dir, 
            headless=False,
            viewport={"width": 1280, "height": 800}
        )
        
        page = browser_context.pages[0] if len(browser_context.pages) > 0 else browser_context.new_page()
        page.on("response", handle_response)
        
        print(f"👉 导航至 {url} ...")
        page.goto(url)
        
        print("\n" + "!" * 50)
        print("请在浏览器中做如下操作：")
        print("1. 网页登录您的账号并保证加载出第一页。")
        print("2. 进入文档并在图片上【手工双击图片】开启“大图浏览/下一张”。")
        print("!" * 50)
        input("\n准备好大图环境之后，请在这里按【回车键】让脚本自动狂扫并发下载...\n> ")
        
        print("\n✅ 开始自动翻页拉取，并直接让后台进行并发提速下载！")
        
        prev_count = 0
        no_change_count = 0
        MAX_NO_CHANGE = 3
        
        try:
            while no_change_count < MAX_NO_CHANGE:
                next_btn = page.locator(".icons-24-image_next")
                if next_btn.count() > 0:
                    try:
                        next_btn.first.click()
                    except Exception:
                        pass
                else:
                    print("⚠️ 找不到页面的 '.icons-24-image_next' 下一张按钮。是没进入大图模式吗？")
                    
                time.sleep(2.5) 
                
                curr_count = len(captured_urls)
                if curr_count > prev_count:
                    prev_count = curr_count
                    no_change_count = 0
                else:
                    no_change_count += 1
                    print(f"⏳ 翻页尚未捕获到新图片 ({no_change_count}/{MAX_NO_CHANGE})，可能已经翻至最后一页。")
                    
        except KeyboardInterrupt:
            print("\n🛑 用户中途停止了寻找翻页操作。")
            
        print(f"\n✅ 主浏览器的自动翻页巡更探测已经完毕。(共截获 {len(captured_urls)} 条链接)")
        print("耐心等待后台进程将队列中最后几张图片处理完全毕...")
        
        # 通知且等待下载队列中的最后一个任务彻底完成
        download_queue.put(None)
        dl_thread.join()
        
    # --- 第最后一步：由于并发下载可能会有重复图片，在此执行去重和编号补齐 ---
    print(f"\n🔄 下载队列清空完毕！执行校验、去重清理与顺序重命名操作 ...")
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
                print(f"🗑️ 删除重复的多余内容: {filename}")
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
                    print(f"📝 自动填补并重命名: {filename} -> {new_filename}")
                    try:
                        os.rename(filepath, new_filepath)
                    except Exception:
                        pass
                new_index += 1
                
    print("=" * 50)
    print("🎉 并发获取+下载清算大版本 任务圆满完成！")
    print(f"最终在名为 '{download_dir}' 的文件夹结构内为您保留了 {len(seen_hashes)} 张去重排序完善的图片。")

if __name__ == "__main__":
    main()
