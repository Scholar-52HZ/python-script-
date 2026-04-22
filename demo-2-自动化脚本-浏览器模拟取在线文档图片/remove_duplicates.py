import os
import hashlib
import re

def calculate_md5(file_path):
    """计算文件的 MD5 哈希值以判断内容是否完全一致"""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        print(f"读取文件 {file_path} 失败: {e}")
        return None

def remove_duplicate_images(directory="./images"):
    """遍历目录并删除字节完全相同的重复图片，并重新编号填补空缺"""
    seen_hashes = set()
    removed_count = 0
    
    # 获取所有的 image_数字 图片文件
    files = []
    for f in os.listdir(directory):
        if re.match(r'^image_\d+\.(png|jpg|jpeg|webp|bmp|gif)$', f.lower()):
            files.append(f)
            
    # 按照文件名中的数字进行排序
    def sort_key(filename):
        nums = re.findall(r'\d+', filename)
        return int(nums[0]) if nums else 0
    
    files.sort(key=sort_key)
    
    print(f"开始扫描目录 '{directory}' 下的 {len(files)} 张图片...")
    
    new_index = 1
    for filename in files:
        filepath = os.path.join(directory, filename)
        if os.path.isfile(filepath):
            file_hash = calculate_md5(filepath)
            
            if not file_hash:
                continue
                
            if file_hash in seen_hashes:
                print(f"删除重复图片: {filename}")
                try:
                    os.remove(filepath)
                    removed_count += 1
                except Exception as e:
                    print(f"删除文件 {filename} 失败: {e}")
            else:
                seen_hashes.add(file_hash)
                
                # 获取原后缀名
                ext = os.path.splitext(filename)[1]
                # 构造新的文件名
                new_filename = f"image_{new_index}{ext}"
                new_filepath = os.path.join(directory, new_filename)
                
                # 如果新文件名和旧文件名不一样，则重命名以填补空缺
                if filename != new_filename:
                    print(f"重命名图片: {filename} -> {new_filename}")
                    try:
                        os.rename(filepath, new_filepath)
                    except Exception as e:
                        print(f"重命名文件 {filename} 失败: {e}")
                        
                new_index += 1
                
    print("-" * 30)
    print(f"清理并重命名完毕！共删除了 {removed_count} 张重复图片。")
    print(f"保留并重新编号了 {len(seen_hashes)} 张唯一图片（已重新编号到 image_{new_index-1}）。")

if __name__ == "__main__":
    # 执行清理当前目录下的重复图片
    remove_duplicate_images()
