(function () {
    const modalBackdrops = new WeakMap();

    function resolveElement(targetOrElement) {
        if (!targetOrElement) return null;
        if (targetOrElement instanceof Element) return targetOrElement;
        if (typeof targetOrElement !== 'string') return null;

        const selector = targetOrElement.startsWith('#') ? targetOrElement : `#${targetOrElement}`;
        try {
            return document.querySelector(selector);
        } catch (_error) {
            return null;
        }
    }

    function getFocusableElement(modalElement) {
        return modalElement.querySelector(
            '[autofocus], button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled])'
        );
    }

    function openModal(targetOrElement) {
        const modalElement = resolveElement(targetOrElement);
        if (!modalElement || modalElement.classList.contains('show')) return;

        const backdrop = document.createElement('div');
        backdrop.className = 'modal-backdrop';
        modalBackdrops.set(modalElement, backdrop);
        document.body.appendChild(backdrop);

        modalElement.style.display = 'block';
        modalElement.removeAttribute('aria-hidden');
        modalElement.classList.add('show');
        document.body.classList.add('modal-open');

        getFocusableElement(modalElement)?.focus();
    }

    function closeModal(targetOrElement) {
        const modalElement = resolveElement(targetOrElement);
        if (!modalElement || !modalElement.classList.contains('show')) return;

        modalElement.classList.remove('show');
        modalElement.style.display = 'none';
        modalElement.setAttribute('aria-hidden', 'true');

        const backdrop = modalBackdrops.get(modalElement);
        if (backdrop) {
            backdrop.remove();
            modalBackdrops.delete(modalElement);
        }

        if (!document.querySelector('.modal.show')) {
            document.body.classList.remove('modal-open');
        }
    }

    function closeAllDropdowns(exceptToggle = null) {
        document.querySelectorAll('[data-ui-dropdown-toggle][aria-expanded="true"]').forEach((toggle) => {
            if (toggle === exceptToggle) return;
            toggle.setAttribute('aria-expanded', 'false');
            const menu = toggle.parentElement?.querySelector('.dropdown-menu');
            menu?.classList.remove('show');
        });
    }

    function toggleDropdown(toggleButton) {
        const menu = toggleButton.parentElement?.querySelector('.dropdown-menu');
        if (!menu) return;

        const willShow = !menu.classList.contains('show');
        closeAllDropdowns(willShow ? toggleButton : null);
        toggleButton.setAttribute('aria-expanded', String(willShow));
        menu.classList.toggle('show', willShow);
    }

    document.addEventListener('click', (event) => {
        const modalTrigger = event.target.closest('[data-ui-modal-target]');
        if (modalTrigger) {
            event.preventDefault();
            const target = modalTrigger.getAttribute('data-ui-modal-target');
            openModal(target);
            return;
        }

        const modalDismiss = event.target.closest('[data-ui-dismiss="modal"]');
        if (modalDismiss) {
            event.preventDefault();
            closeModal(modalDismiss.closest('.modal'));
            return;
        }

        const dropdownToggle = event.target.closest('[data-ui-dropdown-toggle]');
        if (dropdownToggle) {
            event.preventDefault();
            toggleDropdown(dropdownToggle);
            return;
        }

        if (event.target.closest('.dropdown-item')) {
            closeAllDropdowns();
            return;
        }

        const toastDismiss = event.target.closest('[data-ui-dismiss="toast"]');
        if (toastDismiss) {
            event.preventDefault();
            const toast = toastDismiss.closest('.toast');
            toast?.remove();
            return;
        }

        const visibleModal = event.target.classList?.contains('modal') ? event.target : null;
        if (visibleModal && visibleModal.classList.contains('show')) {
            closeModal(visibleModal);
            return;
        }

        if (!event.target.closest('.dropdown')) {
            closeAllDropdowns();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            const topModal = Array.from(document.querySelectorAll('.modal.show')).pop();
            if (topModal) {
                closeModal(topModal);
                return;
            }
            closeAllDropdowns();
        }
    });

    window.AppUI = {
        openModal,
        closeModal,
        closeAllDropdowns,
        toggleDropdown,
    };
})();
