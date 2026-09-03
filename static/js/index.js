// --- 全局状态管理和 DOM 元素 ---
let allResults = [];
let isSearchRunning = false;
let currentPage = 1;
const itemsPerPage = 20;
let isLoadingNextBatch = false;
let isFullyLoaded = false;

let currentFilter = '全部';
let includeKeywords = [];
let excludeKeywords = [];
const isViewModeEnabled = window.SEARCH_LINK_MODE === 'view';

const filterBar = document.getElementById('netdisk-filter-bar');
const advancedFilterBar = document.getElementById('advanced-filter-bar');
const includeFilterInput = document.getElementById('includeFilter');
const excludeFilterInput = document.getElementById('excludeFilter');
const applyFilterButton = document.getElementById('applyFilter');

const scrollableResultsDiv = document.getElementById('scrollableResults');
const searchButton = document.getElementById('searchButton');
const searchInput = document.getElementById('searchInput');
const resultContainer = document.getElementById('resultContainer');
const loadingMore = document.getElementById('loadingMore');
const resultsStarGuide = document.getElementById('resultsStarGuide');
const resultCountText = document.getElementById('resultCountText');
const statusBar = document.getElementById('statusBar');
const advancedFilterToggle = document.getElementById('advancedFilterToggle');
const advancedFilterPanel = document.getElementById('advancedFilterPanel');
const viewResultModalElement = document.getElementById('viewResultModal');
const viewResultLoadingState = document.getElementById('viewResultLoadingState');
const viewResultContentState = document.getElementById('viewResultContentState');
const viewResultTitle = document.getElementById('viewResultTitle');
const viewResultLink = document.getElementById('viewResultLink');
const copyViewResultButton = document.getElementById('copyViewResultButton');
const openViewResultButton = document.getElementById('openViewResultButton');
const viewResultModal = viewResultModalElement ? {
    show: () => window.AppUI.openModal(viewResultModalElement),
    hide: () => window.AppUI.closeModal(viewResultModalElement),
} : null;
let currentResolvedViewResult = null;
let isAdvancedFilterOpen = false;

function setAdvancedFilterOpen(isOpen) {
    isAdvancedFilterOpen = isOpen;
    if (!advancedFilterPanel || !advancedFilterToggle) return;

    advancedFilterPanel.classList.toggle('d-none', !isOpen);
    advancedFilterToggle.setAttribute('aria-expanded', String(isOpen));
    advancedFilterToggle.innerHTML = isOpen
        ? '<i class="fas fa-times me-1"></i> 收起筛选'
        : '<i class="fas fa-sliders-h me-1"></i> 筛选';
}

advancedFilterToggle?.addEventListener('click', function () {
    setAdvancedFilterOpen(!isAdvancedFilterOpen);
});


// --- 辅助函数：网盘颜色区分 (保持不变) ---
function getNetdiskColorClass(netdiskName) {
    let badgeClass = 'bg-secondary';
    let badgeTextClass = 'text-white';

    // 映射规则：
    if (netdiskName.includes('百度网盘')) badgeClass = 'bg-mid-blue';
    else if (netdiskName.includes('夸克网盘')) badgeClass = 'bg-terracotta';
    else if (netdiskName.includes('悟空网盘')) badgeClass = 'bg-navy-blue';
    else if (netdiskName.includes('快兔网盘')) badgeClass = 'bg-coral';
    else if (netdiskName.includes('115网盘')) badgeClass = 'bg-orange';
    else if (netdiskName.includes('迅雷网盘')) badgeClass = 'bg-teal';
    else if (netdiskName.includes('UC网盘')) badgeClass = 'bg-warm-gold';
    else if (netdiskName.includes('移动云盘')) badgeClass = 'bg-light-green';
    else if (netdiskName.includes('天翼云盘')) badgeClass = 'bg-deep-violet';
    else if (netdiskName.includes('123云盘')) badgeClass = 'bg-purple';
    else if (netdiskName.includes('阿里云盘')) badgeClass = 'bg-dark-mint';
    else if (netdiskName.includes('联通云盘')) badgeClass = 'bg-olive';
    else if (netdiskName.includes('PikPak')) badgeClass = 'bg-salmon';
    // 链接类型
    else if (netdiskName.includes('磁力链接') || netdiskName.includes('迅雷链接') || netdiskName.includes('电驴链接')) badgeClass = 'bg-dark';

    // Fallback to text-white if not explicitly set for warning (yellow)
    if (badgeClass !== 'bg-warning') {
        badgeTextClass = 'text-white';
    }

    return { badgeClass, badgeTextClass };
}

// 提取规范化网盘资源唯一键 (与后端对齐，防止误杀同名不同链接)
function extractCanonicalResourceKeyFront(url) {
    if (!url) return '';
    const str = String(url).trim();

    const quarkMatch = str.match(/pan\.quark\.cn\/s\/([a-zA-Z0-9_-]+)/i);
    if (quarkMatch) return `quark:${quarkMatch[1]}`;

    const baiduMatch = str.match(/(?:pan\.baidu\.com|bdpan\.com|baiduyun\.com)\/s\/([a-zA-Z0-9_-]+)/i);
    if (baiduMatch) return `baidu:${baiduMatch[1]}`;

    const aliyunMatch = str.match(/(?:alipan\.com|aliyundrive\.com|drive\.aliyun\.com)\/s\/([a-zA-Z0-9_-]+)/i);
    if (aliyunMatch) return `aliyun:${aliyunMatch[1]}`;

    const ucMatch = str.match(/(?:drive\.uc\.cn|pan\.uc\.cn)\/s\/([a-zA-Z0-9_-]+)/i);
    if (ucMatch) return `uc:${ucMatch[1]}`;

    const xunleiMatch = str.match(/pan\.xunlei\.com\/s\/([a-zA-Z0-9_-]+)/i);
    if (xunleiMatch) return `xunlei:${xunleiMatch[1]}`;

    const pan123Match = str.match(/(?:123pan\.com|123\d{3}\.(?:com|cn))\/s\/([a-zA-Z0-9_-]+)/i);
    if (pan123Match) return `123pan:${pan123Match[1]}`;

    const tianyiMatch = str.match(/cloud\.189\.cn\/(?:t\/|web\/share\?code=)([a-zA-Z0-9_-]+)/i);
    if (tianyiMatch) return `tianyi:${tianyiMatch[1]}`;

    const pan115Match = str.match(/(?:115\.com|115pan\.com|115cdn\.com|anxia\.com)\/s\/([a-zA-Z0-9_-]+)/i);
    if (pan115Match) return `115:${pan115Match[1]}`;

    const mobileMatch = str.match(/(?:yun\.139\.com\/shareweb\/#\/w\/i\/|caiyun\.139\.com\/w\/i\/|caiyun\.139\.com\/m\/i\?|pan\.10086\.cn\/s\/)([a-zA-Z0-9_-]+)/i);
    if (mobileMatch) return `mobile:${mobileMatch[1]}`;

    const magnetMatch = str.match(/magnet:\?xt=urn:btih:([a-zA-Z0-9]+)/i);
    if (magnetMatch) return `magnet:${magnetMatch[1].toLowerCase()}`;

    try {
        const u = new URL(str);
        return `url:${u.hostname.toLowerCase()}${u.pathname.replace(/\/$/, '')}`;
    } catch (e) {
        return `raw:${str}`;
    }
}

// 前端去重辅助函数 (支持同名多链接并存，同一资源择优保留)
function filterUnique2ndDomainFront(lst) {
    const itemMap = new Map();
    const order = [];

    for (const subList of lst) {
        if (!Array.isArray(subList) || subList.length < 4) continue;
        const source = subList[0];
        const title = subList[1] || '';
        const url = subList[2] || '';

        const key = extractCanonicalResourceKeyFront(url);
        if (!key) continue;

        if (!itemMap.has(key)) {
            itemMap.set(key, subList);
            order.push(key);
        } else {
            // 对比已有项与新项，优先保留 source === 'hot' 或标题更完整或带密码的
            const existing = itemMap.get(key);
            let existingScore = (existing[0] === 'hot' ? 1000 : 0) + (existing[1]?.length || 0);
            if (existing[2]?.includes('pwd=') || existing[2]?.includes('password=')) existingScore += 100;

            let newScore = (source === 'hot' ? 1000 : 0) + (title.length || 0);
            if (url.includes('pwd=') || url.includes('password=')) newScore += 100;

            if (newScore > existingScore) {
                itemMap.set(key, subList);
            }
        }
    }
    return order.map(k => itemMap.get(k));
}

/**
 * 根据内容高度动态切换滚动条
 */
function toggleScrollbarBasedOnContent() {
    // 确保DOM已经渲染完成
    setTimeout(() => {
        if (!scrollableResultsDiv) return;
        const contentHeight = scrollableResultsDiv.scrollHeight;
        const containerHeight = scrollableResultsDiv.clientHeight;

        // 如果内容高度超过容器高度，显示滚动条；否则隐藏
        if (contentHeight > containerHeight) {
            scrollableResultsDiv.style.overflowY = 'auto';
        } else {
            scrollableResultsDiv.style.overflowY = 'hidden';
        }
    }, 100); // 给一点延迟确保渲染完成
}

// --- 搜索和结果管理 (已修改) ---
searchButton.addEventListener('click', performSearch);
searchInput.addEventListener('keydown', function (event) {
    if (event.key === 'Enter') {
        performSearch();
    }
});

/**
 * 动态创建网盘过滤按钮。（保持不变）
 */
function updateFilterButtons() {
    const netdiskNames = new Set(allResults.map(item => item[3]));
    // 确保移除所有非 '全部' 的按钮，以便重新排序
    const buttonsToRemove = Array.from(filterBar.querySelectorAll('.filter-btn')).filter(btn => btn.getAttribute('data-netdisk') !== '全部');
    buttonsToRemove.forEach(btn => btn.remove());

    if (allResults.length > 0) {
        filterBar.classList.remove('d-none');
    } else {
        filterBar.classList.add('d-none');
    }

    // 1. 过滤出需要动态添加的网盘名称，并排除“全部”和“其他”
    const dynamicNames = Array.from(netdiskNames).filter(name => name !== '全部' && name !== '其他');

    // 2. 动态添加其他网盘名称
    dynamicNames.forEach(name => {
        const button = document.createElement('button');
        button.className = 'filter-btn';
        button.textContent = name;
        button.setAttribute('data-netdisk', name);

        if (name === currentFilter) {
            button.classList.add('active');
        }
        filterBar.appendChild(button);
    });

    // 3. 确保“其他”在最后（如果存在）
    const hasOther = netdiskNames.has('其他');
    if (hasOther) {
        const otherButton = document.createElement('button');
        otherButton.className = 'filter-btn';
        otherButton.textContent = '其他';
        otherButton.setAttribute('data-netdisk', '其他');

        if ('其他' === currentFilter) {
            otherButton.classList.add('active');
        }
        filterBar.appendChild(otherButton);
    }

    // 4. 确保“全部”按钮的 active 状态正确
    const allButton = filterBar.querySelector('[data-netdisk="全部"]');
    if (allButton) {
        if (currentFilter === '全部') {
            allButton.classList.add('active');
        } else {
            allButton.classList.remove('active');
        }
    }
}

/**
 * 执行流式搜索（SSE）
 */
function performSearch() {
    if (isSearchRunning) return;

    const keyword = searchInput.value;
    if (!keyword) {
        showAlertModal('请输入搜索关键词', 'warning', '搜索提示');
        return;
    }

    // 1. 初始化状态和界面
    isSearchRunning = true;
    isFullyLoaded = false;
    searchButton.disabled = true;

    // 开始时隐藏滚动条
    scrollableResultsDiv.style.overflowY = 'hidden';

    // 启动纸飞机动画
    searchButton.classList.add('is-flying');
    searchButton.classList.add('searching');

    statusBar.classList.remove('d-none');
    statusBar.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span> 正在持续搜索更多资源...';

    resultCountText.classList.add('d-none');
    loadingMore.classList.add('d-none');
    resultsStarGuide?.classList.add('d-none');

    allResults = [];
    currentPage = 1;
    currentFilter = '全部';
    filterBar.classList.add('d-none');

    // 重置筛选框
    includeFilterInput.value = '';
    excludeFilterInput.value = '';
    includeKeywords = [];
    excludeKeywords = [];

    resultContainer.innerHTML = '<p class="text-center text-muted p-4">资源正在路上，马上就来啦...</p > ';
    scrollableResultsDiv.removeEventListener('scroll', infiniteScrollHandler);

    // 2. 创建 EventSource 连接
    const eventSource = new EventSource(`/api/search_stream?keyword=${encodeURIComponent(keyword)}`);

    eventSource.onmessage = function (event) {
        try {
            const data = JSON.parse(event.data);

            if (data.type === 'end') {
                eventSource.close();
                finalizeSearch();
            } else if (data.results && data.results.length > 0) {
                const currentLength = allResults.length;
                allResults.push(...data.results);
                allResults = filterUnique2ndDomainFront(allResults);

                if (allResults.length > currentLength) {
                    updateFilterButtons();
                    if (allResults.length <= itemsPerPage) {
                        renderResults(true);
                        // 有结果时，根据内容高度决定是否显示滚动条
                        toggleScrollbarBasedOnContent();
                    }
                }
            }
        } catch (error) {
            console.error('解析流数据出错:', error);
        }
    };

    eventSource.onerror = function (error) {
        console.error('EventSource 错误:', error);
        eventSource.close();
        resultContainer.innerHTML = '<p class="text-center text-danger p-4">❌ 搜索连接出错或服务器异常。</p>';
        finalizeSearch(true);
    };
}

/**
 * 搜索完成或出错时的清理工作
 */
function finalizeSearch(hasError = false) {
    isSearchRunning = false;
    searchButton.disabled = false;

    // 停止纸飞机动画
    searchButton.classList.remove('is-flying');
    searchButton.classList.remove('searching');

    statusBar.classList.add('d-none');

    if (allResults.length === 0 && !hasError) {
        // 恢复初始提示
        resultContainer.innerHTML = `
            <div class="text-center initial-prompt-area">
                <div class="initial-icon-wrapper">
                    <i class="fas fa-cloud-upload-alt"></i>
                </div>
                <h3 class="mt-3 text-muted">未找到相关结果，请尝试其他关键词</h3>
            </div>`;
        loadingMore.classList.add('d-none');
        resultsStarGuide?.classList.add('d-none');
        // 即使没有结果也显示计数
        document.querySelector('.filter-and-count-container').classList.remove('d-none');
        resultCountText.textContent = `共找到 0 个结果 (${currentFilter})`;

        // 没有结果时，保持隐藏滚动条
        scrollableResultsDiv.style.overflowY = 'hidden';
    } else if (!hasError) {
        updateFilterButtons();
        // 显示筛选和计数容器
        document.querySelector('.filter-and-count-container').classList.remove('d-none');
        renderResults(true);

        // 搜索完成时，根据内容高度决定是否显示滚动条
        toggleScrollbarBasedOnContent();

        scrollableResultsDiv.addEventListener('scroll', infiniteScrollHandler);
    }
}

// 前端综合智能评分函数 (对齐后端模型与 pansou 排序)
function calculateRankScoreFront(item, keyword = '') {
    let score = 0;
    const source = item[0] || '';
    const title = (item[1] || '').trim();
    const url = (item[2] || '').trim();
    const netdisk = (item[3] || '').trim();

    // 1. 数据源层级分 (hot 自有收益盘绝对优先)
    if (source === 'hot') {
        score += 1000;
    } else if (source === 'tg') {
        score += 150;
    } else {
        score += 50;
    }

    // 2. 特征关键词质量分 (合集/系列/全集/4K/完结)
    const lowerTitle = title.toLowerCase();
    const keywordsWeight = [
        ['合集', 420],
        ['系列', 350],
        ['全集', 280],
        ['全', 280],
        ['完结', 210],
        ['完', 210],
        ['4k', 180],
        ['2160p', 180],
        ['原盘', 180],
        ['最新', 140],
        ['1080p', 140],
        ['高清', 140],
        ['国粤双语', 70],
    ];

    let kwCount = 0;
    for (const [kw, w] of keywordsWeight) {
        if (lowerTitle.includes(kw)) {
            score += w;
            kwCount++;
            if (kwCount >= 3) break;
        }
    }

    // 3. 密码与完整度分
    if (url.includes('pwd=') || url.includes('password=')) {
        score += 100;
    }
    if (netdisk && netdisk !== '其他') {
        score += 20;
    }
    if (!title || title === 'Telegram 频道资源') {
        score -= 300;
    }

    // 4. 搜索词相关性分
    if (keyword) {
        const lowerKw = keyword.toLowerCase();
        if (lowerTitle === lowerKw) {
            score += 300;
        } else if (lowerTitle.startsWith(lowerKw)) {
            score += 150;
        } else if (lowerTitle.includes(lowerKw)) {
            score += 80;
        }
    }

    return score;
}

/**
 * 渲染搜索结果到页面 (修改过滤逻辑)
 */
function renderResults(reset = false) {
    let filteredResults = allResults.filter(result => {
        // 云盘过滤
        const matchesNetdisk = currentFilter === '全部' || result[3] === currentFilter;

        // 筛选关键词过滤
        const title = result[1].toLowerCase();
        const matchesInclude = includeKeywords.length === 0 ||
            includeKeywords.every(keyword => title.toLowerCase().includes(keyword.toLowerCase()));

        // 排除关键词过滤
        const matchesExclude = excludeKeywords.length === 0 ||
            !excludeKeywords.some(keyword => title.includes(keyword.toLowerCase()));

        return matchesNetdisk && matchesInclude && matchesExclude;
    });

    // 智能综合排序：根据得分降序排列
    const currentKw = (searchInput.value || '').trim();
    filteredResults.sort((a, b) => calculateRankScoreFront(b, currentKw) - calculateRankScoreFront(a, currentKw));

    if (reset) {
        currentPage = 1;
        resultContainer.innerHTML = '';
    }

    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    const currentBatch = filteredResults.slice(startIndex, endIndex);

    // 总是显示结果计数，即使为0
    resultCountText.textContent = `共找到 ${filteredResults.length} 个结果 (${currentFilter})`;
    resultCountText.classList.remove('d-none');

    if (filteredResults.length > 0) {
        resultContainer.querySelector('p.text-center.text-muted')?.remove();
    } else if (!isSearchRunning && reset) {
        resultContainer.innerHTML = `<div class="text-center p-5"><p class="text-muted">在 ${currentFilter} 中未找到相关结果</p></div>`;
    }

    // 渲染当前批次
    currentBatch.forEach((result, index) => {
        // 假设 result 结构：[source, title, url, netdisk_name]
        const source = result[0];
        const titleText = result[1];
        const urlLink = result[2];
        const netdiskName = result[3];

        const { badgeClass, badgeTextClass } = getNetdiskColorClass(netdiskName);
        const hotClass = source === 'hot' ? 'hot-result' : '';

        // Link Icon Logic: Change link icon to a larger 🔥 for hot results
        let linkIconHtml = '<i class="fas fa-link me-2" style="font-size:0.7rem;"></i>';
        if (source === 'hot') {
            // Larger fire icon for the link line (1.1rem as requested to be larger)
            linkIconHtml = '<span class="me-2" style="font-size: 1.1rem;">🔥</span>';
        }

        // Use default netdisk badge class (no hot override)
        const finalBadgeClass = `${badgeClass} ${badgeTextClass}`;

        const fullItem = document.createElement('div');

        const itemHtml = `
            <div class="result-item ${hotClass}">
                <div class="result-info">
                    <span class="result-title" title="${titleText}">${titleText}</span>
                    <div class="result-url-line ${isViewModeEnabled ? 'd-none' : ''}">
                        ${linkIconHtml}
                        <a href="${urlLink}" target="_blank" title="${urlLink}">${urlLink}</a>
                    </div>
                </div>
                <div class="result-actions">
                    <span class="netdisk-badge ${finalBadgeClass}">${netdiskName}</span>
                    <button class="btn btn-sm ${isViewModeEnabled ? 'view-button btn-outline-secondary' : 'copy-button btn-outline-secondary'}" data-title="${titleText}" data-url="${urlLink}" data-netdisk="${netdiskName}">
                        ${isViewModeEnabled ? '<i class="fas fa-eye"></i> 查看' : '<i class="far fa-copy"></i> 复制'}
                    </button>
                </div>
            </div>
            ${(startIndex + index) < filteredResults.length - 1 ? '<hr class="result-divider">' : ''}
        `;
        fullItem.innerHTML = itemHtml;
        resultContainer.appendChild(fullItem);
    });

    // 绑定复制按钮事件
    resultContainer.querySelectorAll('.copy-button').forEach(button => {
        button.addEventListener('click', function () {
            const title = this.getAttribute('data-title');
            const url = this.getAttribute('data-url');
            const netdisk = this.getAttribute('data-netdisk');
            const textToCopy = `标题: ${title}
分享链接: ${url}
云盘名称: ${netdisk}`;

            copyTextToClipboard(textToCopy).then(success => {
                if (success) {
                    this.innerHTML = '<i class="fas fa-check"></i> 已复制';
                    setTimeout(() => { this.innerHTML = '<i class="far fa-copy"></i> 复制'; }, 1500);
                } else {
                    showAlertModal(`复制失败，请手动复制：\n\n${textToCopy}`, 'warning', '复制失败', '关闭');
                }
            });
        });
    });

    resultContainer.querySelectorAll('.view-button').forEach(button => {
        button.addEventListener('click', function () {
            handleViewButtonClick(this);
        });
    });

    // 更新分页状态和加载提示
    if (endIndex >= filteredResults.length) {
        isFullyLoaded = true;
        loadingMore.classList.add('d-none');
        loadingMore.textContent = '已加载全部结果。';
        if (filteredResults.length > 0) {
            resultsStarGuide?.classList.remove('d-none');
        } else {
            resultsStarGuide?.classList.add('d-none');
        }
    } else {
        isFullyLoaded = false;
        loadingMore.classList.remove('d-none');
        loadingMore.innerHTML = '<div class="spinner-border spinner-border-sm me-2" role="status"><span class="visually-hidden">Loading...</span></div>加载更多结果...';
        resultsStarGuide?.classList.add('d-none');
    }

    if (currentBatch.length > 0) {
        currentPage++;
    }
    isLoadingNextBatch = false;
}

// --- 无限滚动逻辑 (保持不变) ---
const infiniteScrollHandler = () => {
    const container = scrollableResultsDiv;
    if ((container.scrollTop + container.clientHeight) >= (container.scrollHeight - 50) && !isSearchRunning && !isFullyLoaded && !isLoadingNextBatch) {
        loadNextPage();
    }
};

function loadNextPage() {
    isLoadingNextBatch = true;
    loadingMore.classList.remove('d-none');

    setTimeout(() => {
        renderResults(false);
        // 加载更多后，重新判断是否需要滚动条
        toggleScrollbarBasedOnContent();
    }, 300);
}

async function handleViewButtonClick(button) {
    const title = button.getAttribute('data-title');
    const url = button.getAttribute('data-url');
    const netdiskName = button.getAttribute('data-netdisk');

    if (viewResultModal) {
        showViewResultLoading(title);
        viewResultModal.show();
    }

    button.disabled = true;

    try {
        const response = await fetch('/api/view-link', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: title,
                url: url,
                netdisk_name: netdiskName
            })
        });

        let finalUrl = url;
        if (response.ok) {
            const data = await response.json();
            finalUrl = data.url || url;
        }

        showViewResultContent(title, finalUrl, netdiskName);
    } catch (error) {
        console.error('查看模式生成链接失败:', error);
        showViewResultContent(title, url, netdiskName);
    } finally {
        button.disabled = false;
    }
}

function showViewResultLoading(title) {
    currentResolvedViewResult = null;
    if (viewResultTitle) {
        viewResultTitle.textContent = title || '';
    }
    if (viewResultLink) {
        viewResultLink.textContent = '';
        viewResultLink.href = '#';
    }
    viewResultLoadingState?.classList.remove('d-none');
    viewResultContentState?.classList.add('d-none');
    copyViewResultButton?.setAttribute('disabled', 'disabled');
    openViewResultButton?.setAttribute('disabled', 'disabled');
}

function showViewResultContent(title, url, netdiskName) {
    currentResolvedViewResult = { title, url, netdiskName };
    if (viewResultTitle) {
        viewResultTitle.textContent = title;
    }
    if (viewResultLink) {
        viewResultLink.textContent = url;
        viewResultLink.href = url;
        viewResultLink.title = url;
    }
    viewResultLoadingState?.classList.add('d-none');
    viewResultContentState?.classList.remove('d-none');
    copyViewResultButton?.removeAttribute('disabled');
    openViewResultButton?.removeAttribute('disabled');
}

copyViewResultButton?.addEventListener('click', async function () {
    if (!currentResolvedViewResult) return;

    const textToCopy = `标题: ${currentResolvedViewResult.title}
分享链接: ${currentResolvedViewResult.url}`;

    try {
        await navigator.clipboard.writeText(textToCopy);
        const originalHtml = this.innerHTML;
        this.innerHTML = '<i class="fas fa-check me-1"></i> 已复制';
        setTimeout(() => {
            this.innerHTML = originalHtml;
        }, 1500);
    } catch (error) {
        showAlertModal(`复制失败，请手动复制：\n\n${textToCopy}`, 'warning', '复制失败', '关闭');
    }
});

openViewResultButton?.addEventListener('click', function () {
    if (!currentResolvedViewResult) return;
    window.open(currentResolvedViewResult.url, '_blank', 'noopener');
});


// --- 网盘过滤事件监听器 (保持不变) ---
filterBar.addEventListener('click', (event) => {
    const button = event.target.closest('.filter-btn');
    if (button) {
        const netdisk = button.getAttribute('data-netdisk');

        if (netdisk === currentFilter) return;

        currentFilter = netdisk;
        filterBar.querySelectorAll('.filter-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        button.classList.add('active');

        renderResults(true);
        scrollableResultsDiv.scrollTop = 0;
        // 过滤后重新判断是否需要滚动条
        toggleScrollbarBasedOnContent();
    }
});

// --- 高级筛选事件监听器 (新增) ---
applyFilterButton.addEventListener('click', applyAdvancedFilter);

// 添加回车键支持
includeFilterInput.addEventListener('keydown', function (event) {
    if (event.key === 'Enter') {
        applyAdvancedFilter();
    }
});

excludeFilterInput.addEventListener('keydown', function (event) {
    if (event.key === 'Enter') {
        applyAdvancedFilter();
    }
});

/**
 * 应用高级筛选条件
 */
function applyAdvancedFilter() {
    // 获取并处理筛选关键词
    includeKeywords = includeFilterInput.value
        .split(/\s+/)
        .map(kw => kw.trim())
        .filter(kw => kw.length > 0);

    // 获取并处理排除关键词
    excludeKeywords = excludeFilterInput.value
        .split(/\s+/)
        .map(kw => kw.trim())
        .filter(kw => kw.length > 0);

    // 重新渲染结果
    renderResults(true);
    scrollableResultsDiv.scrollTop = 0;

    // 筛选后重新判断是否需要滚动条
    toggleScrollbarBasedOnContent();
}
