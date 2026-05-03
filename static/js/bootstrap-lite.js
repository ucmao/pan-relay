(function () {
    const modalInstances = new WeakMap();
    const toastInstances = new WeakMap();
    const dropdownPortals = new Map();

    function dispatchEvent(element, name) {
        element.dispatchEvent(new CustomEvent(name, { bubbles: true }));
    }

    function getTargetSelector(trigger) {
        return trigger.getAttribute('data-bs-target') || trigger.getAttribute('href');
    }

    function getTargetElement(trigger) {
        const selector = getTargetSelector(trigger);
        if (!selector || selector === '#') return null;
        try {
            return document.querySelector(selector);
        } catch (error) {
            return null;
        }
    }

    class Modal {
        constructor(element) {
            this.element = element;
            this.backdrop = null;
            modalInstances.set(element, this);
            this.bindEvents();
        }

        bindEvents() {
            if (this.element.dataset.modalBound === 'true') return;
            this.element.dataset.modalBound = 'true';

            this.element.addEventListener('click', (event) => {
                if (event.target === this.element) {
                    this.hide();
                }
            });
        }

        show() {
            dispatchEvent(this.element, 'show.bs.modal');
            this.backdrop = document.createElement('div');
            this.backdrop.className = 'modal-backdrop';
            document.body.appendChild(this.backdrop);
            document.body.classList.add('modal-open');
            this.element.style.display = 'block';
            this.element.removeAttribute('aria-hidden');
            this.element.classList.add('show');
            const autofocusTarget = this.element.querySelector('[autofocus], .btn, .form-control, .form-select, .btn-close');
            autofocusTarget?.focus();
            dispatchEvent(this.element, 'shown.bs.modal');
        }

        hide() {
            if (!this.element.classList.contains('show')) return;
            dispatchEvent(this.element, 'hide.bs.modal');
            this.element.classList.remove('show');
            this.element.style.display = 'none';
            this.element.setAttribute('aria-hidden', 'true');
            if (this.backdrop) {
                this.backdrop.remove();
                this.backdrop = null;
            }
            if (!document.querySelector('.modal.show')) {
                document.body.classList.remove('modal-open');
            }
            dispatchEvent(this.element, 'hidden.bs.modal');
        }

        static getInstance(element) {
            return modalInstances.get(element) || null;
        }

        static getOrCreateInstance(element) {
            return Modal.getInstance(element) || new Modal(element);
        }
    }

    class Toast {
        constructor(element, options = {}) {
            this.element = element;
            this.delay = options.delay || 3000;
            this.timer = null;
            toastInstances.set(element, this);
        }

        show() {
            this.element.style.display = 'block';
            this.element.classList.add('show');
            clearTimeout(this.timer);
            this.timer = window.setTimeout(() => this.hide(), this.delay);
        }

        hide() {
            clearTimeout(this.timer);
            this.element.classList.remove('show');
            this.element.style.display = 'none';
            dispatchEvent(this.element, 'hidden.bs.toast');
        }
    }

    function closeAllDropdowns(exceptToggle) {
        document.querySelectorAll('[data-bs-toggle="dropdown"][aria-expanded="true"]').forEach((toggle) => {
            if (exceptToggle && toggle === exceptToggle) return;
            toggle.setAttribute('aria-expanded', 'false');
            const menu = getDropdownMenu(toggle);
            if (menu) {
                resetDropdownMenu(menu);
                restoreDropdownMenu(toggle, menu);
            }
        });
    }

    function getDropdownMenu(toggle) {
        return dropdownPortals.get(toggle)?.menu || toggle.closest('.dropdown')?.querySelector('.dropdown-menu');
    }

    function portalDropdownMenu(toggle, menu) {
        if (dropdownPortals.has(toggle)) return;
        dropdownPortals.set(toggle, {
            menu,
            parent: menu.parentNode,
            nextSibling: menu.nextSibling,
        });
        document.body.appendChild(menu);
    }

    function restoreDropdownMenu(toggle, menu) {
        const portal = dropdownPortals.get(toggle);
        if (!portal) return;
        portal.parent.insertBefore(menu, portal.nextSibling);
        dropdownPortals.delete(toggle);
    }

    function resetDropdownMenu(menu) {
        menu.classList.remove('show');
        menu.style.removeProperty('position');
        menu.style.removeProperty('top');
        menu.style.removeProperty('left');
        menu.style.removeProperty('right');
    }

    function positionDropdownMenu(toggle, menu) {
        const viewportPadding = 12;
        const gap = 8;
        const toggleRect = toggle.getBoundingClientRect();

        menu.style.position = 'fixed';
        menu.style.top = '0px';
        menu.style.left = '0px';
        menu.style.right = 'auto';
        menu.classList.add('show');

        const menuRect = menu.getBoundingClientRect();
        let top = toggleRect.bottom + gap;
        if (top + menuRect.height > window.innerHeight - viewportPadding) {
            const flippedTop = toggleRect.top - menuRect.height - gap;
            if (flippedTop >= viewportPadding) {
                top = flippedTop;
            }
        }

        let left = menu.classList.contains('dropdown-menu-end')
            ? toggleRect.right - menuRect.width
            : toggleRect.left;
        left = Math.max(viewportPadding, Math.min(left, window.innerWidth - menuRect.width - viewportPadding));

        menu.style.top = `${Math.max(viewportPadding, top)}px`;
        menu.style.left = `${left}px`;
    }

    document.addEventListener('click', (event) => {
        const modalToggle = event.target.closest('[data-bs-toggle="modal"]');
        if (modalToggle) {
            event.preventDefault();
            const target = getTargetElement(modalToggle);
            if (target) {
                Modal.getOrCreateInstance(target).show();
            }
            return;
        }

        const dismissButton = event.target.closest('[data-bs-dismiss="modal"]');
        if (dismissButton) {
            event.preventDefault();
            dismissButton.closest('.modal') && Modal.getOrCreateInstance(dismissButton.closest('.modal')).hide();
            return;
        }

        const dismissToast = event.target.closest('[data-bs-dismiss="toast"]');
        if (dismissToast) {
            event.preventDefault();
            const toastElement = dismissToast.closest('.toast');
            const toast = toastInstances.get(toastElement);
            toast?.hide();
            return;
        }

        const dropdownToggle = event.target.closest('[data-bs-toggle="dropdown"]');
        if (dropdownToggle) {
            event.preventDefault();
            const menu = getDropdownMenu(dropdownToggle);
            if (!menu) return;
            const willShow = !menu.classList.contains('show');
            closeAllDropdowns(willShow ? dropdownToggle : null);
            dropdownToggle.setAttribute('aria-expanded', String(willShow));
            if (willShow) {
                portalDropdownMenu(dropdownToggle, menu);
                positionDropdownMenu(dropdownToggle, menu);
            } else {
                resetDropdownMenu(menu);
                restoreDropdownMenu(dropdownToggle, menu);
            }
            return;
        }

        if (!event.target.closest('.dropdown') && !event.target.closest('.dropdown-menu.show')) {
            closeAllDropdowns();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            closeAllDropdowns();
            const activeModal = document.querySelector('.modal.show');
            if (activeModal) {
                Modal.getOrCreateInstance(activeModal).hide();
            }
        }
    });

    window.addEventListener('resize', () => closeAllDropdowns());
    window.addEventListener('scroll', () => closeAllDropdowns(), true);

    document.addEventListener('click', (event) => {
        if (event.target.closest('.dropdown-item')) {
            closeAllDropdowns();
        }
    });

    window.bootstrap = {
        Modal,
        Toast
    };
})();
