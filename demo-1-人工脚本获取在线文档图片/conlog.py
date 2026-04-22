import re
import requests
from urllib.parse import urlparse


def convert_to_original(thumbnail_url):
    # 处理类型 A
    if 'imageMogr2/thumbnail' in thumbnail_url:
        return thumbnail_url.split('?')[0]
    # 处理类型 B
    elif '/api/thumbnail/' in thumbnail_url:
        return re.sub(r'/api/thumbnail/(.+?)/compatible', r'/api/file/\1', thumbnail_url)
    else:
        return thumbnail_url

# 读取缩略图链接
with open('thumbnails.txt', 'r') as f:
    urls = [line.strip() for line in f if line.strip()]

# 转换并尝试下载
for idx, thumb_url in enumerate(urls):
    orig_url = convert_to_original(thumb_url)
    print(f"尝试下载: {orig_url}")
    try:
        resp = requests.get(orig_url, timeout=10)
        # headers = {'Referer': 'https://www.kdocs.cn/'}
        # resp = requests.get(orig_url, headers=headers, timeout=10)
        if resp.status_code == 200 and len(resp.content) > 1000:
            with open(f'image_{idx+1}.jpg', 'wb') as img_file:
                img_file.write(resp.content)
            print(f"  成功保存 image_{idx+1}.jpg")
        else:
            print(f"  失败，状态码 {resp.status_code}，可能不是原图")
    except Exception as e:
        print(f"  出错: {e}")