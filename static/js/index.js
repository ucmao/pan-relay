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
const viewResultModal = viewResultModalElement ? new bootstrap.Modal(viewResultModalElement) : null;
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

// 前端去重辅助函数 (保持不变)
function filterUnique2ndDomainFront(lst) {
    const seenCombinations = new Set();
    const result = [];
    for (const subList of lst) {
        if (subList.length >= 4) {
            const title = subList[1];
            const url = subList[2];
            try {
                const domain = new URL(url).hostname;
                const combination = `${title}|${domain}`;
                if (!seenCombinations.has(combination)) {
                    seenCombinations.add(combination);
                    result.push(subList);
                }
            } catch (e) { continue; }
        }
    }
    return result;
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
        alert('请输入搜索关键词');
        return;
    }

    // 1. 初始化状态和界面
    isSearchRunning = true;
    isFullyLoaded = false;
    searchButton.disabled = true;

    // 启动纸飞机动画
    searchButton.classList.add('is-flying');
    searchButton.classList.add('searching');

    statusBar.classList.remove('d-none');
    statusBar.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span> 正在持续搜索更多资源...';

    resultCountText.classList.add('d-none');
    loadingMore.classList.add('d-none');

    allResults = [];
    currentPage = 1;
    currentFilter = '全部';
    filterBar.classList.add('d-none');
    
    // 重置筛选框
    includeFilterInput.value = '';
    excludeFilterInput.value = '';
    includeKeywords = [];
    excludeKeywords = [];

    resultContainer.innerHTML = '<p class="text-center text-muted p-4">正在连接并等待结果流...</p>';
    scrollableResultsDiv.removeEventListener('scroll', infiniteScrollHandler);

    // 2. 创建 EventSource 连接
    const eventSource = new EventSource(`/api/search_stream?keyword=${encodeURIComponent(keyword)}`);

    eventSource.onmessage = function(event) {
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
                    }
                }
            }
        } catch (error) {
            console.error('解析流数据出错:', error);
        }
    };

    eventSource.onerror = function(error) {
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
        // 即使没有结果也显示计数
        document.querySelector('.filter-and-count-container').classList.remove('d-none');
        resultCountText.textContent = `共找到 0 个结果 (${currentFilter})`;
    } else if (!hasError) {
        updateFilterButtons();
        // 显示筛选和计数容器
        document.querySelector('.filter-and-count-container').classList.remove('d-none');
        renderResults(true);
        scrollableResultsDiv.addEventListener('scroll', infiniteScrollHandler);
    }
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
                    <button class="btn btn-sm ${isViewModeEnabled ? 'view-button btn-primary' : 'copy-button btn-outline-secondary'}" data-title="${titleText}" data-url="${urlLink}" data-netdisk="${netdiskName}">
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
        button.addEventListener('click', function() {
            const title = this.getAttribute('data-title');
            const url = this.getAttribute('data-url');
            const netdisk = this.getAttribute('data-netdisk');
            const textToCopy = `标题: ${title}
分享链接: ${url}
云盘名称: ${netdisk}`;

            navigator.clipboard.writeText(textToCopy)
                .then(() => {
                    this.innerHTML = '<i class="fas fa-check"></i> 已复制';
                    setTimeout(() => { this.innerHTML = '<i class="far fa-copy"></i> 复制'; }, 1500);
                })
                .catch(() => {
                    alert('复制失败，请手动复制:\n\n' + textToCopy);
                });
        });
    });

    resultContainer.querySelectorAll('.view-button').forEach(button => {
        button.addEventListener('click', function() {
            handleViewButtonClick(this);
        });
    });

    // 更新分页状态和加载提示
    if (endIndex >= filteredResults.length) {
        isFullyLoaded = true;
        loadingMore.classList.add('d-none');
        loadingMore.textContent = '已加载全部结果。';
    } else {
        isFullyLoaded = false;
        loadingMore.classList.remove('d-none');
        loadingMore.innerHTML = '<div class="spinner-border spinner-border-sm me-2" role="status"><span class="visually-hidden">Loading...</span></div>加载更多结果...';
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
    }, 300);
}

async function handleViewButtonClick(button) {
    const title = button.getAttribute('data-title');
    const url = button.getAttribute('data-url');
    const netdiskName = button.getAttribute('data-netdisk');
    const originalHtml = button.innerHTML;

    if (viewResultModal) {
        showViewResultLoading(title);
        viewResultModal.show();
    }

    button.disabled = true;
    button.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> 获取中';

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
        button.innerHTML = originalHtml;
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
        alert('复制失败，请手动复制:\n\n' + textToCopy);
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
    }
});

// --- 高级筛选事件监听器 (新增) ---
applyFilterButton.addEventListener('click', applyAdvancedFilter);

// 添加回车键支持
includeFilterInput.addEventListener('keydown', function(event) {
    if (event.key === 'Enter') {
        applyAdvancedFilter();
    }
});

excludeFilterInput.addEventListener('keydown', function(event) {
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
}
