(async function autoCollectImages() {
    // ---------- 1. 设置请求拦截，捕获原图 URL ----------
    const imageUrls = new Set();
    const originalFetch = window.fetch;
    const originalXHROpen = XMLHttpRequest.prototype.open;
    const originalXHRSend = XMLHttpRequest.prototype.send;

    function isOriginalImageUrl(url) {
        if (!url || typeof url !== 'string') return false;
        // 排除 blob、data 和明显的缩略图
        if (url.startsWith('blob:') || url.startsWith('data:')) return false;
        // 原图特征：包含 /api/file/ 但不包含 thumbnail，或者 img.qwps.cn 且不含 thumbnail
        if ((url.includes('/api/file/') && !url.includes('thumbnail')) ||
            (url.includes('img.qwps.cn') && !url.includes('thumbnail'))) {
            return true;
        }
        // 也可以根据扩展名判断
        return /\.(jpg|jpeg|png|webp|bmp)(\?|$)/i.test(url);
    }

    function recordUrl(url) {
        if (isOriginalImageUrl(url) && !imageUrls.has(url)) {
            imageUrls.add(url);
            console.log(`[捕获原图 ${imageUrls.size}] ${url}`);
        }
    }

    // 拦截 fetch
    window.fetch = function (...args) {
        const url = args[0];
        recordUrl(url);
        return originalFetch.apply(this, args);
    };

    // 拦截 XMLHttpRequest
    XMLHttpRequest.prototype.open = function (method, url, ...rest) {
        this._url = url;
        recordUrl(url);
        return originalXHROpen.apply(this, [method, url, ...rest]);
    };
    XMLHttpRequest.prototype.send = function (body) {
        this.addEventListener('load', () => {
            if (this.responseURL) recordUrl(this.responseURL);
        });
        return originalXHRSend.call(this, body);
    };

    console.log('✅ 请求拦截已启动，将自动记录原图 URL');

    // ---------- 2. 自动翻页 ----------
    const nextBtn = document.querySelector('.icons-24-image_next');
    if (!nextBtn) {
        console.error('❌ 未找到 .icons-24-image_next 按钮，请确认 class 名称是否正确');
        return;
    }
    console.log('✅ 找到“下一张”按钮，开始自动翻页...');

    // 辅助函数：等待一段时间
    const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

    let prevCount = 0;
    let noChangeCount = 0;
    const MAX_NO_CHANGE = 3;  // 连续 3 次没有新图片则结束

    while (noChangeCount < MAX_NO_CHANGE) {
        // 点击下一张
        nextBtn.click();
        console.log('👉 已点击“下一张”');

        // 等待图片加载（网络请求完成 + DOM 更新）
        await wait(2000);  // 可根据网速调整，2 秒一般足够

        // 检查是否有新的原图被捕获
        const currentCount = imageUrls.size;
        if (currentCount > prevCount) {
            console.log(`📸 已捕获 ${currentCount} 张原图`);
            prevCount = currentCount;
            noChangeCount = 0;
        } else {
            noChangeCount++;
            console.log(`⚠️ 未捕获到新图片 (${noChangeCount}/${MAX_NO_CHANGE})，可能已到最后一张`);
        }
    }

    console.log('🛑 自动翻页结束。');

    // ---------- 3. 输出结果 ----------
    const urlsArray = Array.from(imageUrls);
    console.log(`\n📋 共捕获到 ${urlsArray.length} 张原图：`);
    urlsArray.forEach((url, i) => console.log(`${i + 1}: ${url}`));

    // 复制到剪贴板
    if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(urlsArray.join('\n'));
        console.log('✅ 所有原图链接已复制到剪贴板，可直接粘贴到下载工具中');
    } else {
        console.log('⚠️ 当前环境不支持自动复制，请手动复制上面的链接');
    }

    // 恢复原始函数（可选）
    window.fetch = originalFetch;
    XMLHttpRequest.prototype.open = originalXHROpen;
    XMLHttpRequest.prototype.send = originalXHRSend;

    return urlsArray;
})();