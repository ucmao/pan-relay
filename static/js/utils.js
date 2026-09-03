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
