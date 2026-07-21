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
        // NFD \u015f/\u011f/\u00fc/\u00f6/\u00e7'yi ayr\u0131\u015ft\u0131r\u0131r; noktas\u0131z "\u0131" ayr\u0131\u015fmad\u0131\u011f\u0131 i\u00e7in ayr\u0131ca
        // "i"ye indirgenir ki "pinar" aramas\u0131 "P\u0131nar"\u0131 bulsun.
        return (value || '')
            .toString()
            .toLowerCase()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .replace(/\u0131/g, 'i');
    }

    // Typeahead for selects with many options
    document.querySelectorAll('select.js-searchable-select').forEach(function(select) {
        if (select.dataset.searchReady === '1') {
            return;
        }

        var placeholder = select.dataset.searchPlaceholder || 'Yazarak ara...';
        var options = Array.from(select.options).filter(function(opt) {
            return opt.value;
        });

        var wrapper = document.createElement('div');
        wrapper.className = 'typeahead-wrapper';

        var input = document.createElement('input');
        input.type = 'text';
        input.className = 'form-control mb-2';
        input.placeholder = placeholder;
        input.autocomplete = 'off';

        var list = document.createElement('div');
        list.className = 'typeahead-list list-group shadow-sm';

        // Set initial value in input
        if (select.value) {
            var selectedOption = options.find(function(opt) { return opt.value === select.value; });
            if (selectedOption) {
                input.value = selectedOption.textContent.trim();
            }
        }

        // Hide the original select (but keep id, name, and option elements intact!)
        select.classList.add('d-none');

        // Insert wrapper before select
        select.parentNode.insertBefore(wrapper, select);
        wrapper.appendChild(input);
        wrapper.appendChild(list);
        wrapper.appendChild(select); // move select inside wrapper for tidy hierarchy

        function renderList(query) {
            var nq = normalizeText(query);
            var matches = options.filter(function(opt) {
                return !nq || normalizeText(opt.textContent).indexOf(nq) !== -1;
            }).slice(0, 100);

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
                    select.value = opt.value;
                    input.value = opt.textContent.trim();
                    list.style.display = 'none';
                    // Dispatch change event on the original select so page scripts trigger
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                });
                list.appendChild(btn);
            });

            list.style.display = 'block';
        }

        input.addEventListener('input', function() {
            select.value = ''; // clear select until an item is explicitly clicked
            select.dispatchEvent(new Event('change', { bubbles: true }));
            renderList(input.value);
        });

        input.addEventListener('focus', function() {
            renderList(input.value);
        });

        input.addEventListener('blur', function() {
            window.setTimeout(function() {
                list.style.display = 'none';
                // If user blurs without picking an item and has typed something that doesn't match, or cleared it
                if (!select.value) {
                    input.value = '';
                } else {
                    var selectedOption = options.find(function(opt) { return opt.value === select.value; });
                    if (selectedOption) {
                        input.value = selectedOption.textContent.trim();
                    }
                }
            }, 120);
        });

        select.dataset.searchReady = '1';
    });

    // Server-side search for paginated lists: debounced auto-submit.
    // A client-only row filter can only see the current page's rows, so
    // typing "ö" would never reveal matches sitting on other pages. Instead
    // we submit the GET form (Turkish-aware search across the whole table)
    // shortly after the user stops typing, and restore focus + caret after
    // the reload so typing continues uninterrupted.
    document.querySelectorAll('input.js-table-filter').forEach(function(input) {
        var form = input.closest('form');
        if (!form) {
            return;
        }

        var delay = parseInt(input.getAttribute('data-autosubmit-delay'), 10) || 400;
        var timer = null;
        input.addEventListener('input', function() {
            clearTimeout(timer);
            timer = setTimeout(function() {
                if (form.requestSubmit) {
                    form.requestSubmit();
                } else {
                    form.submit();
                }
            }, delay);
        });

        // After an auto-submit reload the page comes back with the query in
        // the box; return focus and place the caret at the end.
        if (input.value) {
            input.focus();
            var value = input.value;
            input.value = '';
            input.value = value;
        }
    });

    // Generic checkbox list filter
    document.querySelectorAll('input.js-checkbox-filter').forEach(function(input) {
        var targetSelector = input.getAttribute('data-target');
        if (!targetSelector) {
            return;
        }

        var items = document.querySelectorAll(targetSelector);
        input.addEventListener('input', function() {
            var q = normalizeText(input.value.trim());
            items.forEach(function(item) {
                var text = normalizeText(item.textContent || '');
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
    // Theme toggle click handler
    var themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        var themeToggleIcon = document.getElementById('theme-toggle-icon');
        
        function updateIcon(theme) {
            if (themeToggleIcon) {
                if (theme === 'dark') {
                    themeToggleIcon.className = 'bi bi-sun';
                    themeToggle.setAttribute('aria-label', 'Açık temaya geç');
                } else {
                    themeToggleIcon.className = 'bi bi-moon-stars';
                    themeToggle.setAttribute('aria-label', 'Koyu temaya geç');
                }
            }
        }
        
        // Initial icon state
        var currentTheme = document.documentElement.getAttribute('data-bs-theme') || 'light';
        updateIcon(currentTheme);
        
        themeToggle.addEventListener('click', function() {
            var activeTheme = document.documentElement.getAttribute('data-bs-theme');
            var nextTheme = activeTheme === 'dark' ? 'light' : 'dark';
            
            document.documentElement.setAttribute('data-bs-theme', nextTheme);
            localStorage.setItem('theme', nextTheme);
            updateIcon(nextTheme);
        });
    }
});
