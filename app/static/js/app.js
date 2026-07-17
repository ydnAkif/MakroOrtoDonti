document.addEventListener('DOMContentLoaded', function() {
    var csrfMeta = document.querySelector('meta[name="csrf-token"]');
    var csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : null;

    if (csrfToken) {
        document.querySelectorAll('form[method="POST"], form[method="post"]').forEach(function(form) {
            if (!form.querySelector('input[name="csrf_token"]')) {
                var input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'csrf_token';
                input.value = csrfToken;
                form.appendChild(input);
            }
        });
    }

    function normalizeText(value) {
        return (value || '')
            .toString()
            .toLowerCase()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '');
    }

    // Typeahead for selects with many options
    document.querySelectorAll('select.js-searchable-select').forEach(function(select) {
        if (select.dataset.searchReady === '1') {
            return;
        }

        var placeholder = select.dataset.searchPlaceholder || 'Yazdikca ara...';
        var options = Array.from(select.options).filter(function(opt) {
            return opt.value;
        });

        var wrapper = document.createElement('div');
        wrapper.className = 'typeahead-wrapper';

        var hiddenInput = document.createElement('input');
        hiddenInput.type = 'hidden';
        hiddenInput.name = select.name;
        if (select.id) {
            hiddenInput.id = select.id;
        }

        var input = document.createElement('input');
        input.type = 'text';
        input.className = 'form-control mb-2';
        input.placeholder = placeholder;
        input.autocomplete = 'off';

        var list = document.createElement('div');
        list.className = 'typeahead-list list-group shadow-sm';

        if (select.required) {
            hiddenInput.required = true;
            select.required = false;
        }

        if (select.value) {
            var selectedOption = options.find(function(opt) { return opt.value === select.value; });
            if (selectedOption) {
                hiddenInput.value = selectedOption.value;
                input.value = selectedOption.textContent.trim();
            }
        }

        select.removeAttribute('name');
        select.classList.add('d-none');

        select.parentNode.insertBefore(wrapper, select);
        wrapper.appendChild(input);
        wrapper.appendChild(hiddenInput);
        wrapper.appendChild(list);
        wrapper.appendChild(select);

        function renderList(query) {
            var nq = normalizeText(query);
            var matches = options.filter(function(opt) {
                return !nq || normalizeText(opt.textContent).indexOf(nq) !== -1;
            }).slice(0, 12);

            list.innerHTML = '';
            if (!matches.length) {
                list.style.display = 'none';
                return;
            }

            matches.forEach(function(opt) {
                var btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'list-group-item list-group-item-action';
                btn.textContent = opt.textContent.trim();
                btn.addEventListener('mousedown', function() {
                    hiddenInput.value = opt.value;
                    input.value = opt.textContent.trim();
                    list.style.display = 'none';
                    hiddenInput.dispatchEvent(new Event('change', { bubbles: true }));
                });
                list.appendChild(btn);
            });

            list.style.display = 'block';
        }

        input.addEventListener('input', function() {
            hiddenInput.value = '';
            renderList(input.value);
        });

        input.addEventListener('focus', function() {
            renderList(input.value);
        });

        input.addEventListener('blur', function() {
            window.setTimeout(function() {
                list.style.display = 'none';
            }, 120);
        });

        select.dataset.searchReady = '1';
    });

    // Generic table row filter
    document.querySelectorAll('input.js-table-filter').forEach(function(input) {
        var targetSelector = input.getAttribute('data-target');
        if (!targetSelector) {
            return;
        }

        var rows = document.querySelectorAll(targetSelector);
        input.addEventListener('input', function() {
            var q = input.value.trim().toLowerCase();
            rows.forEach(function(row) {
                var text = (row.textContent || '').toLowerCase();
                row.style.display = !q || text.indexOf(q) !== -1 ? '' : 'none';
            });
        });
    });

    // Generic checkbox list filter
    document.querySelectorAll('input.js-checkbox-filter').forEach(function(input) {
        var targetSelector = input.getAttribute('data-target');
        if (!targetSelector) {
            return;
        }

        var items = document.querySelectorAll(targetSelector);
        input.addEventListener('input', function() {
            var q = input.value.trim().toLowerCase();
            items.forEach(function(item) {
                var text = (item.textContent || '').toLowerCase();
                item.style.display = !q || text.indexOf(q) !== -1 ? '' : 'none';
            });
        });
    });

    // Auto-dismiss alerts after 5 seconds
    document.querySelectorAll('.alert-dismissible').forEach(function(alert) {
        setTimeout(function() {
            var bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            bsAlert.close();
        }, 5000);
    });
});
