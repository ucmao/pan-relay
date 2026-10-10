// 通用工具函数

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function formatModalMessage(message) {
    return escapeHtml(message).replace(/\n/g, '<br>');
}

/**
 * 健壮的剪贴板复制函数（支持现代 Clipboard API 与 execCommand 降级）
 * 兼容 HTTP、非 localhost、局域网 IP、Safari 等受限上下文
 * @param {string} text - 要复制的文本内容
 * @returns {Promise<boolean>} 是否复制成功
 */
async function copyTextToClipboard(text) {
    if (text === undefined || text === null) return false;
    const str = String(text);

    // 1. 优先尝试现代 Clipboard API（需在安全上下文 HTTPS 或 localhost 下）
    if (navigator.clipboard && window.isSecureContext) {
        try {
            await navigator.clipboard.writeText(str);
            return true;
        } catch (err) {
            console.warn('navigator.clipboard.writeText 失败，转入 fallback 方案:', err);
        }
    }

    // 2. 降级方案：创建临时不可见 textarea 执行 document.execCommand('copy')
    try {
        const textArea = document.createElement('textarea');
        textArea.value = str;
        textArea.style.position = 'fixed';
        textArea.style.top = '-9999px';
        textArea.style.left = '-9999px';
        textArea.style.width = '2em';
        textArea.style.height = '2em';
        textArea.style.padding = '0';
        textArea.style.border = 'none';
        textArea.style.outline = 'none';
        textArea.style.boxShadow = 'none';
        textArea.style.background = 'transparent';
        textArea.setAttribute('readonly', '');
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        textArea.setSelectionRange(0, textArea.value.length);
        const successful = document.execCommand('copy');
        document.body.removeChild(textArea);
        return Boolean(successful);
    } catch (err) {
        console.error('document.execCommand 复制失败:', err);
        return false;
    }
}

/**
 * 显示提示消息（现代化 Toast 气泡弹窗）
 * @param {string} message - 消息内容
 * @param {string} type - 消息类型：success, danger, warning, info
 * @param {number} delay - 自动关闭延迟时间（毫秒）
 */
function showToast(message, type = 'success', delay = 3000) {
    let toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toastContainer';
        document.body.appendChild(toastContainer);
    }

    // 防重复提示：若已有相同内容的激活提示，避免重复堆叠
    const existing = Array.from(toastContainer.querySelectorAll('.admin-toast:not(.admin-toast-hiding) .admin-toast-message'))
        .find(el => el.textContent === message);
    if (existing) return;

    const iconMap = {
        success: 'fas fa-check-circle',
        danger: 'fas fa-times-circle',
        warning: 'fas fa-exclamation-triangle',
        info: 'fas fa-info-circle'
    };
    const iconClass = iconMap[type] || iconMap.info;

    const toast = document.createElement('div');
    toast.className = `admin-toast admin-toast-${type}`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');

    toast.innerHTML = `
        <i class="${iconClass} admin-toast-icon"></i>
        <div class="admin-toast-message">${escapeHtml(message)}</div>
        <button type="button" class="admin-toast-close" aria-label="关闭">
            <i class="fas fa-times"></i>
        </button>
    `;

    toastContainer.appendChild(toast);

    const hideToast = () => {
        toast.classList.add('admin-toast-hiding');
        setTimeout(() => {
            toast.remove();
        }, 220);
    };

    const autoHideTimer = setTimeout(hideToast, delay);
    const closeButton = toast.querySelector('.admin-toast-close');
    closeButton?.addEventListener('click', () => {
        clearTimeout(autoHideTimer);
        hideToast();
    }, { once: true });
}

/**
 * 显示提示对话框：替代浏览器原生 alert 的统一模态框
 * @param {string} message - 提示内容
 * @param {string} type - 对话框类型：primary, danger, warning, success, info
 * @param {string} title - 对话框标题
 * @param {string} confirmText - 确认按钮文案
 * @returns {Promise<void>}
 */
function showAlertModal(message, type = 'primary', title = '提示', confirmText = '我知道了') {
    return new Promise((resolve) => {
        const modalContainer = document.createElement('div');
        modalContainer.className = 'modal fade';
        modalContainer.setAttribute('tabindex', '-1');

        const iconMap = {
            danger: '<i class="fas fa-circle-xmark text-danger me-2"></i>',
            warning: '<i class="fas fa-triangle-exclamation text-warning me-2"></i>',
            success: '<i class="fas fa-circle-check text-success me-2"></i>',
            info: '<i class="fas fa-circle-info text-primary me-2"></i>',
            primary: '<i class="fas fa-circle-info text-primary me-2"></i>'
        };

        modalContainer.innerHTML = `
            <div class="modal-dialog modal-dialog-centered alert-modal-dialog">
                <div class="modal-content shadow border-0">
                    <div class="modal-header border-0 pb-0">
                        <h5 class="modal-title" style="font-size: 1.1rem; font-weight: 600;">
                            ${iconMap[type] || iconMap.primary}${escapeHtml(title)}
                        </h5>
                        <button type="button" class="btn-close" data-ui-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body py-3 text-secondary" style="line-height: 1.7; word-break: break-word;">
                        ${formatModalMessage(message)}
                    </div>
                    <div class="modal-footer border-0 pt-0">
                        <button type="button" class="btn btn-${type === 'info' ? 'primary' : type} btn-sm px-3" data-ui-dismiss="modal">${escapeHtml(confirmText)}</button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modalContainer);
        const dismissButtons = modalContainer.querySelectorAll('[data-ui-dismiss="modal"]');

        let settled = false;
        const cleanup = () => {
            if (settled) return;
            settled = true;
            document.removeEventListener('keydown', onKeyDown);
            window.AppUI.closeModal(modalContainer);
            modalContainer.remove();
            resolve();
        };

        const onKeyDown = (event) => {
            if (event.key === 'Escape') {
                cleanup();
            }
        };
        document.addEventListener('keydown', onKeyDown);

        dismissButtons.forEach((button) => {
            button.addEventListener('click', cleanup, { once: true });
        });

        modalContainer.addEventListener('click', (event) => {
            if (event.target === modalContainer) {
                cleanup();
            }
        }, { once: true });

        window.AppUI.openModal(modalContainer);
    });
}

/**
 * 显示确认对话框：支持异步与样式的通用确认对话框
 * @param {string} message - 确认消息内容
 * @param {string} type - 对话框类型：primary, danger, warning（可选，默认"primary"）
 * @param {string} title - 对话框标题（可选，默认"确认操作"）
 * @returns {Promise<boolean>} - 确认返回true，取消返回false
 */
function showConfirm(message, type = 'primary', title = '确认操作') {
    return new Promise((resolve) => {
        let confirmed = false;
        let settled = false;
        
        // 创建模态框容器
        const modalContainer = document.createElement('div');
        modalContainer.className = 'modal fade';
        modalContainer.setAttribute('tabindex', '-1');

        // 映射图标样式
        const iconMap = {
            danger: '<i class="fas fa-exclamation-circle text-danger me-2"></i>',
            warning: '<i class="fas fa-exclamation-triangle text-warning me-2"></i>',
            primary: '<i class="fas fa-info-circle text-primary me-2"></i>'
        };

        modalContainer.innerHTML = `
            <div class="modal-dialog modal-dialog-centered modal-sm">
                <div class="modal-content shadow border-0">
                    <div class="modal-header border-0 pb-0">
                        <h5 class="modal-title" style="font-size: 1.1rem; font-weight: 600;">
                            ${iconMap[type] || ''}${escapeHtml(title)}
                        </h5>
                        <button type="button" class="btn-close" data-ui-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body py-3 text-secondary">
                        ${formatModalMessage(message)}
                    </div>
                    <div class="modal-footer border-0 pt-0">
                        <button type="button" class="btn btn-light btn-sm px-3" data-ui-dismiss="modal">取消</button>
                        <button type="button" class="btn btn-${type} btn-sm px-3" id="confirmActionBtn">确认</button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modalContainer);
        const confirmBtn = modalContainer.querySelector('#confirmActionBtn');
        const cancelButtons = modalContainer.querySelectorAll('[data-ui-dismiss="modal"]');

        const cleanup = (result) => {
            if (settled) return;
            settled = true;
            document.removeEventListener('keydown', onKeyDown);
            if (typeof result === 'boolean') {
                resolve(result);
            }
            window.AppUI.closeModal(modalContainer);
            modalContainer.remove();
        };

        const onKeyDown = (event) => {
            if (event.key === 'Escape') {
                cleanup(false);
            }
        };
        document.addEventListener('keydown', onKeyDown);

        // 核心逻辑：点击确认返回 true
        confirmBtn.onclick = () => {
            confirmed = true;
            cleanup(true);
        };

        cancelButtons.forEach((button) => {
            button.addEventListener('click', () => {
                cleanup(confirmed ? true : false);
            }, { once: true });
        });

        modalContainer.addEventListener('click', (event) => {
            if (event.target === modalContainer) {
                cleanup(confirmed ? true : false);
            }
        }, { once: true });

        window.AppUI.openModal(modalContainer);
    });
}

/**
 * 判断当前客户端是否为移动端设备/浏览器
 * @returns {boolean}
 */
function isMobileDevice() {
    const userAgent = navigator.userAgent || navigator.vendor || window.opera || '';
    const isMobileUA = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile|mobile|CriOS|FxiOS/i.test(userAgent);
    const isTouchDevice = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
    const isSmallScreen = window.innerWidth <= 768;
    return isMobileUA || (isSmallScreen && isTouchDevice);
}

/**
 * ==========================================================================
 * 现代化自定义下拉选择框增强器 (Custom Select Component)
 * 自动识别并美化页面上所有的 <select> 标签，支持双向同步、响应式事件触发、动态 DOM 监听与键盘无障碍导航
 * ==========================================================================
 */

function setupCustomSelect(select) {
    if (!select || select.dataset.customSelectReady === 'true') return;
    if (select.dataset.nativeSelect !== undefined || select.dataset.noCustom !== undefined) return;
    select.dataset.customSelectReady = 'true';

    // 创建外层包装容器
    const wrapper = document.createElement('div');
    wrapper.className = 'custom-select-wrapper';
    
    // 继承相关类名与尺寸
    if (select.classList.contains('form-select-sm') || select.classList.contains('input-sm') || select.classList.contains('text-xs')) {
        wrapper.classList.add('form-select-sm');
    }
    if (select.classList.contains('w-full')) {
        wrapper.classList.add('w-full');
    }
    if (select.classList.contains('flex-1')) {
        wrapper.classList.add('flex-1');
    }
    // 拷贝所有以 w-、min-w-、max-w-、sm:w- 等开头的布局类名
    Array.from(select.classList).forEach(cls => {
        if (/^(w-|sm:w-|md:w-|lg:w-|min-w-|max-w-)/.test(cls)) {
            wrapper.classList.add(cls);
        }
    });

    if (select.disabled) {
        wrapper.classList.add('is-disabled');
    }
    // 继承行内宽度或特殊样式
    if (select.style.width) wrapper.style.width = select.style.width;
    if (select.style.minWidth) wrapper.style.minWidth = select.style.minWidth;
    if (select.style.maxWidth) wrapper.style.maxWidth = select.style.maxWidth;

    // 创建 Trigger 触发按钮
    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'custom-select-trigger';
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    if (select.disabled) trigger.disabled = true;

    const label = document.createElement('span');
    label.className = 'custom-select-label';

    const arrow = document.createElement('i');
    arrow.className = 'fas fa-chevron-down custom-select-arrow';

    trigger.appendChild(label);
    trigger.appendChild(arrow);

    // 创建下拉菜单浮层
    const dropdown = document.createElement('div');
    dropdown.className = 'custom-select-dropdown';
    dropdown.setAttribute('role', 'listbox');

    // 组装 DOM
    select.parentNode.insertBefore(wrapper, select);
    select.classList.add('custom-select-native-hidden');
    wrapper.appendChild(select);
    wrapper.appendChild(trigger);
    wrapper.appendChild(dropdown);

    // 同步选项与显示
    function syncFromNative() {
        const selectedOption = select.options[select.selectedIndex];
        label.textContent = selectedOption ? selectedOption.text : (select.getAttribute('placeholder') || '请选择');
        if (!selectedOption || !selectedOption.value) {
            label.classList.toggle('is-placeholder', !selectedOption?.text);
        } else {
            label.classList.remove('is-placeholder');
        }

        wrapper.classList.toggle('is-disabled', Boolean(select.disabled));
        trigger.disabled = Boolean(select.disabled);

        // 重建下拉选项
        dropdown.innerHTML = '';
        Array.from(select.options).forEach((opt, idx) => {
            const optEl = document.createElement('div');
            optEl.className = 'custom-select-option';
            if (idx === select.selectedIndex) {
                optEl.classList.add('is-selected');
            }
            if (opt.disabled) {
                optEl.classList.add('is-disabled');
            }
            optEl.dataset.value = opt.value;
            optEl.dataset.index = String(idx);

            const optText = document.createElement('span');
            optText.className = 'custom-select-option-text';
            optText.textContent = opt.text;

            const optCheck = document.createElement('i');
            optCheck.className = 'fas fa-check custom-select-option-check';

            optEl.appendChild(optText);
            optEl.appendChild(optCheck);

            optEl.addEventListener('click', (e) => {
                e.stopPropagation();
                if (opt.disabled || select.disabled) return;
                
                const changed = select.selectedIndex !== idx;
                select.selectedIndex = idx;
                select.value = opt.value;
                syncFromNative();
                closeDropdown();

                if (changed) {
                    select.dispatchEvent(new Event('input', { bubbles: true }));
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                }
            });

            dropdown.appendChild(optEl);
        });
    }

    // 计算并更新浮层绝对视口定位 (Fixed) 彻底解决 parent card overflow:hidden 裁切问题
    function updateDropdownPosition() {
        const rect = trigger.getBoundingClientRect();
        // 下拉框宽度至少与 trigger 等宽，若 trigger 较窄则给予至少 240px 宽度以防选项文字被挤压
        const dropdownWidth = Math.max(rect.width, 240);
        const spaceBelow = window.innerHeight - rect.bottom;
        const spaceAbove = rect.top;
        const isDropUp = (spaceBelow < 220 && spaceAbove > spaceBelow);

        // 左右位置防溢出
        let leftPos = rect.left;
        if (leftPos + dropdownWidth > window.innerWidth - 10) {
            leftPos = Math.max(10, window.innerWidth - dropdownWidth - 10);
        }
        dropdown.style.left = `${Math.max(10, leftPos)}px`;
        dropdown.style.width = `${Math.max(rect.width, dropdownWidth)}px`;
        dropdown.style.minWidth = `${rect.width}px`;

        if (isDropUp) {
            dropdown.style.top = 'auto';
            dropdown.style.bottom = `${window.innerHeight - rect.top + 4}px`;
            wrapper.classList.add('drop-up');
        } else {
            dropdown.style.bottom = 'auto';
            dropdown.style.top = `${rect.bottom + 4}px`;
            wrapper.classList.remove('drop-up');
        }
    }

    // 打开/关闭下拉
    function openDropdown() {
        if (select.disabled || wrapper.classList.contains('is-disabled')) return;
        
        // 先关闭页面上其他所有打开的下拉
        document.querySelectorAll('.custom-select-wrapper.is-open').forEach(w => {
            if (w !== wrapper) {
                w.classList.remove('is-open', 'drop-up');
                w.querySelector('.custom-select-trigger')?.setAttribute('aria-expanded', 'false');
            }
        });

        updateDropdownPosition();
        wrapper.classList.add('is-open');
        trigger.setAttribute('aria-expanded', 'true');
    }

    function closeDropdown() {
        wrapper.classList.remove('is-open', 'drop-up');
        trigger.setAttribute('aria-expanded', 'false');
    }

    function toggleDropdown() {
        if (wrapper.classList.contains('is-open')) {
            closeDropdown();
        } else {
            openDropdown();
        }
    }

    trigger.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        toggleDropdown();
    });

    // 监听键盘事件 (Enter, Space, ArrowUp, ArrowDown, Escape)
    trigger.addEventListener('keydown', (e) => {
        if (select.disabled) return;
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            toggleDropdown();
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (!wrapper.classList.contains('is-open')) {
                openDropdown();
            } else if (select.selectedIndex < select.options.length - 1) {
                select.selectedIndex += 1;
                syncFromNative();
                select.dispatchEvent(new Event('input', { bubbles: true }));
                select.dispatchEvent(new Event('change', { bubbles: true }));
            }
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (!wrapper.classList.contains('is-open')) {
                openDropdown();
            } else if (select.selectedIndex > 0) {
                select.selectedIndex -= 1;
                syncFromNative();
                select.dispatchEvent(new Event('input', { bubbles: true }));
                select.dispatchEvent(new Event('change', { bubbles: true }));
            }
        } else if (e.key === 'Escape') {
            closeDropdown();
        }
    });

    // 拦截 select 的 value 与 selectedIndex 的原生 setter，确保 JS 动态赋值时实时同步 UI
    try {
        const proto = HTMLSelectElement.prototype;
        const origValueDescriptor = Object.getOwnPropertyDescriptor(proto, 'value');
        const origIndexDescriptor = Object.getOwnPropertyDescriptor(proto, 'selectedIndex');

        Object.defineProperty(select, 'value', {
            get: function () {
                return origValueDescriptor.get.call(this);
            },
            set: function (val) {
                origValueDescriptor.set.call(this, val);
                syncFromNative();
            },
            configurable: true
        });

        Object.defineProperty(select, 'selectedIndex', {
            get: function () {
                return origIndexDescriptor.get.call(this);
            },
            set: function (idx) {
                origIndexDescriptor.set.call(this, idx);
                syncFromNative();
            },
            configurable: true
        });
    } catch (e) {
        console.warn('CustomSelect setter intercept warning:', e);
    }

    // 监听原生 select 的变更事件
    select.addEventListener('change', syncFromNative);

    // MutationObserver 监听属性 (disabled, class) 及子元素 (<option>) 动态变更
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.type === 'childList' || mutation.type === 'attributes') {
                syncFromNative();
            }
        });
    });
    observer.observe(select, { attributes: true, childList: true, subtree: true });

    // 初始化渲染
    syncFromNative();
}

function initCustomSelects(root = document) {
    if (!root || !root.querySelectorAll) return;

    const selects = root.querySelectorAll('select:not([data-custom-select-ready]):not([data-native-select]):not([data-no-custom])');
    selects.forEach(select => {
        setupCustomSelect(select);
    });
}

window.initCustomSelects = initCustomSelects;
window.setupCustomSelect = setupCustomSelect;

// 全局点击空白处关闭所有自定义下拉菜单
document.addEventListener('click', (e) => {
    if (!e.target.closest('.custom-select-wrapper')) {
        document.querySelectorAll('.custom-select-wrapper.is-open').forEach(w => {
            w.classList.remove('is-open', 'drop-up');
            w.querySelector('.custom-select-trigger')?.setAttribute('aria-expanded', 'false');
        });
    }
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.custom-select-wrapper.is-open').forEach(w => {
            w.classList.remove('is-open', 'drop-up');
            w.querySelector('.custom-select-trigger')?.setAttribute('aria-expanded', 'false');
        });
    }
});

// 全局滚动/缩放时动态更新打开下拉框的位置（或视口超出时自动关闭）
window.addEventListener('scroll', () => {
    const openWrapper = document.querySelector('.custom-select-wrapper.is-open');
    if (openWrapper) {
        const trigger = openWrapper.querySelector('.custom-select-trigger');
        const dropdown = openWrapper.querySelector('.custom-select-dropdown');
        if (trigger && dropdown) {
            const rect = trigger.getBoundingClientRect();
            if (rect.bottom < 0 || rect.top > window.innerHeight) {
                openWrapper.classList.remove('is-open', 'drop-up');
                trigger.setAttribute('aria-expanded', 'false');
            } else {
                dropdown.style.left = `${Math.max(10, rect.left)}px`;
                if (openWrapper.classList.contains('drop-up')) {
                    dropdown.style.bottom = `${window.innerHeight - rect.top + 4}px`;
                } else {
                    dropdown.style.top = `${rect.bottom + 4}px`;
                }
            }
        }
    }
}, { passive: true, capture: true });

window.addEventListener('resize', () => {
    const openWrapper = document.querySelector('.custom-select-wrapper.is-open');
    if (openWrapper) {
        const trigger = openWrapper.querySelector('.custom-select-trigger');
        const dropdown = openWrapper.querySelector('.custom-select-dropdown');
        if (trigger && dropdown) {
            const rect = trigger.getBoundingClientRect();
            const dropdownWidth = Math.max(rect.width, 240);
            let leftPos = rect.left;
            if (leftPos + dropdownWidth > window.innerWidth - 10) {
                leftPos = Math.max(10, window.innerWidth - dropdownWidth - 10);
            }
            dropdown.style.left = `${Math.max(10, leftPos)}px`;
            dropdown.style.width = `${Math.max(rect.width, dropdownWidth)}px`;
            if (openWrapper.classList.contains('drop-up')) {
                dropdown.style.bottom = `${window.innerHeight - rect.top + 4}px`;
            } else {
                dropdown.style.top = `${rect.bottom + 4}px`;
            }
        }
    }
}, { passive: true });

// 页面加载及监听动态插入的 DOM 元素
if (typeof MutationObserver !== 'undefined') {
    const globalSelectObserver = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            for (const node of mutation.addedNodes) {
                if (node.nodeType === Node.ELEMENT_NODE) {
                    if (node.matches && node.matches('select')) {
                        setupCustomSelect(node);
                    } else if (node.querySelectorAll) {
                        initCustomSelects(node);
                    }
                }
            }
        }
    });

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            initCustomSelects(document);
            if (document.body) {
                globalSelectObserver.observe(document.body, { childList: true, subtree: true });
            }
        });
    } else {
        initCustomSelects(document);
        if (document.body) {
            globalSelectObserver.observe(document.body, { childList: true, subtree: true });
        }
    }
}


