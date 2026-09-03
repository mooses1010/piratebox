// Lightweight theme system (round 8). Runs immediately, NOT inside the
// DOMContentLoaded handler below, specifically so it executes before
// <body> is parsed/painted - this script tag loads synchronously in
// <head> on every page, so document.documentElement (<html>) already
// exists by the time this runs, but nothing has been drawn yet. That
// ordering is what avoids a flash of the default theme before
// switching to a saved one.
//
// 100% client-side and privacy-preserving by construction: the only
// state is one localStorage key, in this browser, on this device -
// there is no cookie, no server-side render branch, no account, and a
// choice made here can never affect what any other visitor sees. An
// invalid, missing, or inaccessible (private-browsing / storage
// disabled) value simply leaves no data-theme attribute set, which
// means the plain :root tokens in styles.css apply - the default
// PirateBox appearance is always the safe fallback, never a broken or
// blank page. See docs/OPERATIONAL-DECISIONS.md "Lightweight Theme
// System" for the full design.
var PIRATEBOX_THEMES = ['default', 'terminal', 'amber', 'lowlight', 'pirate'];
var PIRATEBOX_THEME_KEY = 'piratebox_theme';

(function () {
    try {
        var saved = localStorage.getItem(PIRATEBOX_THEME_KEY);
        if (saved && PIRATEBOX_THEMES.indexOf(saved) !== -1 && saved !== 'default') {
            document.documentElement.setAttribute('data-theme', saved);
        }
    } catch (e) {
        // Fall back to the default theme silently - never break the page
        // over a cosmetic preference.
    }
})();

document.addEventListener('DOMContentLoaded', function () {
    // Theme switcher (round 8) - the <select> itself is rendered by
    // includes/navbar.php (so its option labels go through the same
    // i18n as everything else in the navbar); this just syncs its
    // displayed value to whatever was applied above and wires changes
    // back into localStorage + the live data-theme attribute. No page
    // reload needed - the CSS custom properties re-cascade instantly.
    var themeSelect = document.getElementById('themeSelect');
    if (themeSelect) {
        var current = 'default';
        try {
            var savedTheme = localStorage.getItem(PIRATEBOX_THEME_KEY);
            if (savedTheme && PIRATEBOX_THEMES.indexOf(savedTheme) !== -1) {
                current = savedTheme;
            }
        } catch (e) {
            // Storage unavailable - leave the switcher on "default",
            // matching the appearance actually being shown.
        }
        themeSelect.value = current;

        themeSelect.addEventListener('change', function () {
            var choice = themeSelect.value;
            if (PIRATEBOX_THEMES.indexOf(choice) === -1) {
                choice = 'default';
            }
            if (choice === 'default') {
                document.documentElement.removeAttribute('data-theme');
            } else {
                document.documentElement.setAttribute('data-theme', choice);
            }
            try {
                localStorage.setItem(PIRATEBOX_THEME_KEY, choice);
            } catch (e) {
                // Can't persist (private browsing/storage disabled) - the
                // choice still applies for the rest of this page view,
                // it just won't be remembered on the next one.
            }
        });
    }

    // Username Persistence
    const nameInputs = document.querySelectorAll('input[name="name"]');
    const savedName = localStorage.getItem('piratebox_username');

    if (savedName) {
        nameInputs.forEach(input => input.value = savedName);
    }

    nameInputs.forEach(input => {
        input.addEventListener('input', (e) => localStorage.setItem('piratebox_username', e.target.value));
    });

    // Navbar toggle
    const toggler = document.querySelector('.navbar-toggler');
    const menu = document.querySelector('.navbar-menu');
    if (toggler && menu) {
        toggler.addEventListener('click', () => {
            menu.classList.toggle('active');
        });
    }

    // Upload Form Logic (index.php)
    // We select by enctype to specifically target the file upload form.
    // Submitted via XHR (instead of a plain form POST) purely so we can
    // show real upload progress (xhr.upload.onprogress) for what can be a
    // 120MB transfer over Wi-Fi - the actual request/response semantics
    // (redirect on success, HTML error page on failure) are unchanged
    // from what upload.php has always done.
    const uploadForm = document.querySelector('form[enctype="multipart/form-data"]');
    if (uploadForm) {
        const progressWrap = document.getElementById('upload-progress');
        const progressBar = document.getElementById('upload-progress-bar');
        const selectedFilename = document.getElementById('selected-filename');
        const uploadFileInput = uploadForm.querySelector('input[name="file"]');

        if (selectedFilename && uploadFileInput) {
            uploadFileInput.addEventListener('change', function () {
                selectedFilename.textContent = uploadFileInput.files.length > 0
                    ? uploadFileInput.files[0].name
                    : '';
            });
        }

        uploadForm.addEventListener('submit', function (e) {
            e.preventDefault();

            const btn = uploadForm.querySelector('button');
            const fileLabel = uploadForm.querySelector('label');
            const fileInput = uploadForm.querySelector('input[name="file"]');

            if (!fileInput || fileInput.files.length === 0) return;

            const maxSize = parseInt(fileInput.getAttribute('data-max-size'), 10);
            if (!isNaN(maxSize) && fileInput.files[0].size > maxSize) {
                alert('File is too large. Maximum size is ' + (maxSize / 1024 / 1024) + 'MiB.');
                return;
            }

            if (btn) {
                btn.disabled = true;
                btn.textContent = 'UPLOADING...';
                btn.classList.add('upload-animation');
            }
            if (fileInput) {
                fileInput.style.pointerEvents = 'none';
                fileInput.style.opacity = '0.5';
                fileInput.style.display = 'none';
                if (fileLabel) fileLabel.style.display = 'none';
            }
            if (progressWrap) progressWrap.hidden = false;

            const xhr = new XMLHttpRequest();
            xhr.open('POST', uploadForm.action, true);

            xhr.upload.addEventListener('progress', function (evt) {
                if (evt.lengthComputable && progressBar) {
                    progressBar.style.width = Math.round((evt.loaded / evt.total) * 100) + '%';
                }
            });

            xhr.addEventListener('load', function () {
                // upload.php redirects (302 -> followed by the browser's
                // XHR implementation) to "/" on success, and returns its
                // own HTML directly (still at upload.php, no redirect) on
                // any error - so responseURL tells us which happened
                // without needing to parse anything.
                const success = !/\/upload\.php(\?|$)/.test(xhr.responseURL);
                if (success) {
                    window.location.href = '/';
                } else {
                    // Show the server's actual error page/message rather
                    // than a generic one, then let the user try again.
                    document.open();
                    document.write(xhr.responseText);
                    document.close();
                }
            });

            xhr.addEventListener('error', function () {
                if (progressWrap) progressWrap.hidden = true;
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = 'Upload';
                    btn.classList.remove('upload-animation');
                }
                if (fileInput) {
                    fileInput.style.pointerEvents = '';
                    fileInput.style.opacity = '';
                    fileInput.style.display = '';
                    if (fileLabel) fileLabel.style.display = '';
                }
                alert('Upload failed - network error. Please try again.');
            });

            xhr.send(new FormData(uploadForm));
        });
    }

    // File Search Logic (index.php)
    const searchInput = document.getElementById('fileSearch');
    if (searchInput) {
        searchInput.addEventListener('keyup', function () {
            const filter = searchInput.value.toLowerCase();
            const rows = document.querySelectorAll('table tbody tr');

            rows.forEach(row => {
                // Filter only if 3 or more characters, otherwise show all
                if (filter.length >= 3 && !row.textContent.toLowerCase().includes(filter)) {
                    row.style.display = "none";
                } else {
                    row.style.display = "";
                }
            });
        });
    }

    // File Sort Logic (index.php) - progressive enhancement: the table is
    // already server-rendered newest-first, so without JS (or before this
    // runs) it's still a perfectly usable, correctly-sorted list. This just
    // lets the visitor re-sort it client-side from the data-* attributes
    // already on each row - no extra request, no server round-trip.
    const fileTable = document.getElementById('file-table');
    const fileSortSelect = document.getElementById('fileSort');
    if (fileTable) {
        const tbody = fileTable.querySelector('tbody');

        function sortFiles(key, ascending) {
            const rows = Array.from(tbody.querySelectorAll('tr'));
            const dir = ascending ? 1 : -1;
            rows.sort((a, b) => {
                if (key === 'name') {
                    return dir * a.dataset.name.localeCompare(b.dataset.name);
                }
                return dir * (parseInt(a.dataset[key], 10) - parseInt(b.dataset[key], 10));
            });
            rows.forEach(row => tbody.appendChild(row));
        }

        function applySortMode(mode) {
            switch (mode) {
                case 'oldest': sortFiles('uploaded', true); break;
                case 'name': sortFiles('name', true); break;
                case 'size': sortFiles('size', false); break;
                case 'newest':
                default: sortFiles('uploaded', false); break;
            }
        }

        if (fileSortSelect) {
            fileSortSelect.addEventListener('change', () => applySortMode(fileSortSelect.value));
        }

        // Clicking (or, via keyboard, focusing + Enter/Space) a column
        // header sorts by that column too, matching the dropdown's
        // equivalent option.
        fileTable.querySelectorAll('th.sortable').forEach(th => {
            th.setAttribute('tabindex', '0');
            th.setAttribute('role', 'button');
            const activate = () => {
                const key = th.dataset.sortKey;
                const mode = key === 'uploaded' ? 'newest' : key;
                if (fileSortSelect) fileSortSelect.value = mode;
                applySortMode(mode);
            };
            th.addEventListener('click', activate);
            th.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    activate();
                }
            });
        });
    }

    // Message Character Count Logic (messages.php)
    const messageInput = document.querySelector('textarea[name="message"]');
    const charCountDisplay = document.getElementById('char-count');

    if (messageInput && charCountDisplay) {
        const maxLength = messageInput.getAttribute('maxlength');
        messageInput.addEventListener('input', function () {
            charCountDisplay.textContent = `${messageInput.value.length} / ${maxLength}`;
        });
    }

    // Guard against a double-click double-posting a logbook entry before
    // the page navigates away (messages.php is a plain synchronous form
    // submit, unlike chat's fetch-based one).
    const messageForm = document.getElementById('message-form');
    if (messageForm) {
        messageForm.addEventListener('submit', function () {
            // A disabled button can't be clicked again, so simply
            // disabling it here is enough to stop a double-submit - the
            // page navigates away shortly after anyway.
            const submitBtn = messageForm.querySelector('button[type="submit"]');
            if (submitBtn) submitBtn.disabled = true;
        });
    }

    // Message Time Formatting (messages.php)
    document.querySelectorAll('.message-time[data-timestamp]').forEach(el => {
        const date = new Date(parseInt(el.dataset.timestamp) * 1000);
        el.textContent = Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
    });

    // Chat Time Formatting (chat.php)
    document.querySelectorAll('.chat-timestamp[data-timestamp]').forEach(el => {
        const date = new Date(parseInt(el.dataset.timestamp) * 1000);
        el.textContent = Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
    });

    // File Time Formatting (index.php)
    document.querySelectorAll('.file-timestamp[data-timestamp]').forEach(el => {
        const date = new Date(parseInt(el.dataset.timestamp) * 1000);
        el.textContent = Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
    });

    // Chat Logic (chat.php)
    const chatList = document.getElementById('chat');
    const chatForm = document.getElementById('chat-form');

    if (chatList && chatForm) {
        // Chat Character Counter
        const chatInput = chatForm.querySelector('input[name="message"]');
        const chatCharCount = document.getElementById('char-count');
        const chatError = document.getElementById('chat-post-error');

        if (chatInput && chatCharCount) {
            const maxLength = chatInput.getAttribute('maxlength');
            chatInput.addEventListener('input', () => {
                chatCharCount.textContent = `${chatInput.value.length} / ${maxLength}`;
            });
        }

        chatForm.addEventListener('submit', async event => {
            const form = event.target;
            let name = form.name.value;
            const message = form.message.value;
            const csrf_token = form.csrf_token.value;

            event.preventDefault();

            if (name == "")
                name = "Anonymous";

            if (message == "")
                return;

            // Guard against a double-tap/double-click firing two POSTs
            // before the first completes (this form's submit is async, so
            // nothing else stops that).
            const sendBtn = chatForm.querySelector('button[type="submit"]');
            if (sendBtn) {
                if (sendBtn.disabled) return;
                sendBtn.disabled = true;
            }

            let response;
            try {
                response = await fetch(form.action, { method: "POST", body: new URLSearchParams({ name, message, csrf_token }) });
            } finally {
                if (sendBtn) sendBtn.disabled = false;
            }

            // Stage 24: chat.php now returns 507 if there isn't enough free
            // storage to save the message (see its matching comment). Only
            // render the message optimistically once the server has
            // actually confirmed the write - otherwise this would lie to
            // the sender about whether their message was saved, and the
            // message text they typed would be lost for nothing.
            if (!response.ok) {
                if (chatError) {
                    chatError.textContent = response.status === 507
                        ? 'Not enough free storage space is available to save this message right now. Please try again later, or let the PirateBox operator know storage is running low.'
                        : 'Your message could not be sent. Please try again.';
                    chatError.hidden = false;
                }
                return;
            }

            if (chatError) chatError.hidden = true;

            const template = chatList.querySelector("template");
            if (template) {
                chatList.querySelector(".empty-state")?.remove();
                const messageElement = template.content.cloneNode(true);
                const small = messageElement.querySelector("small");
                const contentSpan = messageElement.querySelector("span");

                small.textContent = "";
                const nameSpan = document.createElement("span");
                nameSpan.className = "chat-name";
                nameSpan.textContent = name;
                small.appendChild(nameSpan);
                small.appendChild(document.createTextNode(" ("));
                const timeSpan = document.createElement("span");
                timeSpan.className = "chat-timestamp";
                timeSpan.textContent = Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date());
                small.appendChild(timeSpan);
                small.appendChild(document.createTextNode("): "));
                contentSpan.textContent = message;
                chatList.append(messageElement);
                chatList.scrollTop = chatList.scrollHeight;
            }

            form.message.value = "";
            form.message.focus();

            if (chatCharCount && chatInput) {
                chatCharCount.textContent = `0 / ${chatInput.getAttribute('maxlength')}`;
            }
        });

        async function poll_for_new_chat() {
            try {
                const response = await fetch("chat.php?fetch=1", { cache: "no-cache" });
                if (!response.ok) return;

                const chat = await response.json();
                const template = chatList.querySelector("template");
                if (!template) return;
                const messageTemplate = template.content.querySelector("li");

                const pixelDistanceFromListeBottom = chatList.scrollHeight - chatList.scrollTop - chatList.clientHeight;
                const scrollToBottom = (pixelDistanceFromListeBottom < 50);

                chatList.querySelectorAll("li.pending").forEach(li => li.remove());

                const lastMessageId = parseInt(chatList.dataset.lastMessageId ?? "-1");

                if (chat.length > 0) chatList.querySelector(".empty-state")?.remove();

                for (const msg of chat) {
                    if (msg.id > lastMessageId) {
                        const date = new Date(msg.timestamp * 1000);
                        const messageElement = messageTemplate.cloneNode(true);
                        messageElement.classList.remove("pending");
                        const small = messageElement.querySelector("small");
                        const contentSpan = messageElement.querySelector("span");

                        small.textContent = "";
                        const nameSpan = document.createElement("span");
                        nameSpan.className = "chat-name";
                        nameSpan.textContent = msg.name;
                        small.appendChild(nameSpan);
                        small.appendChild(document.createTextNode(" ("));
                        const timeSpan = document.createElement("span");
                        timeSpan.className = "chat-timestamp";
                        timeSpan.textContent = Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
                        small.appendChild(timeSpan);
                        small.appendChild(document.createTextNode("): "));
                        contentSpan.textContent = msg.message;
                        chatList.append(messageElement);
                        chatList.dataset.lastMessageId = msg.id;
                    }
                }

                Array.from(chatList.querySelectorAll("li")).slice(0, -1000).forEach(li => li.remove());

                if (scrollToBottom)
                    chatList.scrollTop = chatList.scrollHeight - chatList.clientHeight;
            } catch (e) {
                console.error("Chat polling error", e);
            }
        }

        poll_for_new_chat();
        setInterval(poll_for_new_chat, 1000);
    }

    // Navbar Badges Logic
    const badgeMessages = document.getElementById('badge-messages');
    const badgeChat = document.getElementById('badge-chat');
    const badgeBulletin = document.getElementById('badge-bulletin');

    const getMaxId = (items) => {
        if (!items || items.length === 0) return -1;
        return items.reduce((max, item) => Math.max(max, item.id), -1);
    };

    const updateBadges = async () => {
        const isMessagesPage = window.location.pathname.includes('messages.php');
        const isChatPage = window.location.pathname.includes('chat.php');
        const isBulletinPage = window.location.pathname.includes('bulletin.php');

        // Check Messages
        try {
            const res = await fetch('messages.php?fetch=1');
            if (res.ok) {
                const messages = await res.json();
                const lastSeenId = parseInt(localStorage.getItem('piratebox_last_message_id') || '-1');
                const maxId = getMaxId(messages);

                if (isMessagesPage) {
                    localStorage.setItem('piratebox_last_message_id', maxId);
                    if (badgeMessages) badgeMessages.style.display = 'none';
                } else {
                    const unread = messages.filter(m => m.id > lastSeenId).length;
                    if (badgeMessages) {
                        badgeMessages.textContent = unread > 0 ? unread : '';
                        badgeMessages.style.display = unread > 0 ? 'inline-block' : 'none';
                    }
                }
            }
        } catch (e) { console.error(e); }

        // Check Chat
        try {
            const res = await fetch('chat.php?fetch=1');
            if (res.ok) {
                const chats = await res.json();
                const lastSeenId = parseInt(localStorage.getItem('piratebox_last_chat_id') || '-1');
                const maxId = getMaxId(chats);

                if (isChatPage) {
                    localStorage.setItem('piratebox_last_chat_id', maxId);
                    if (badgeChat) badgeChat.style.display = 'none';
                } else {
                    const unread = chats.filter(c => c.id > lastSeenId).length;
                    if (badgeChat) {
                        badgeChat.textContent = unread > 0 ? unread : '';
                        badgeChat.style.display = unread > 0 ? 'inline-block' : 'none';
                    }
                }
            }
        } catch (e) { console.error(e); }

        // Check Bulletin Board
        try {
            const res = await fetch('bulletin.php?fetch=1');
            if (res.ok) {
                const posts = await res.json();
                const lastSeenId = parseInt(localStorage.getItem('piratebox_last_bulletin_id') || '-1');
                const maxId = getMaxId(posts);

                if (isBulletinPage) {
                    localStorage.setItem('piratebox_last_bulletin_id', maxId);
                    if (badgeBulletin) badgeBulletin.style.display = 'none';
                } else {
                    const unread = posts.filter(p => p.id > lastSeenId).length;
                    if (badgeBulletin) {
                        badgeBulletin.textContent = unread > 0 ? unread : '';
                        badgeBulletin.style.display = unread > 0 ? 'inline-block' : 'none';
                    }
                }
            }
        } catch (e) { console.error(e); }
    };

    if (badgeMessages || badgeChat || badgeBulletin) {
        updateBadges();
        setInterval(updateBadges, 3000);
    }

    // Radio Reference search/filter (utility/radio/index.php) - progressive
    // enhancement: every entry is already server-rendered and reachable via
    // native <details>/<summary> expansion with JS entirely off. This just
    // adds live text search + category chip filtering on top, matching the
    // existing fileSearch technique above (filter already-rendered elements
    // client-side - no extra request, no server round-trip).
    const radioSearch = document.getElementById('radioSearch');
    const radioChips = document.getElementById('radioChips');
    if (radioSearch && radioChips) {
        const entries = Array.from(document.querySelectorAll('.radio-entry'));
        const sections = Array.from(document.querySelectorAll('[data-group-section]'));
        const noResults = document.getElementById('radioNoResults');
        let activeGroup = 'all';

        function applyRadioFilter() {
            const query = radioSearch.value.trim().toLowerCase();
            let anyVisible = false;

            entries.forEach(entry => {
                const groupMatch = activeGroup === 'all' || entry.dataset.group === activeGroup;
                const textMatch = query === '' || (entry.dataset.search || '').includes(query);
                const visible = groupMatch && textMatch;
                entry.hidden = !visible;
                if (visible) anyVisible = true;
            });

            sections.forEach(section => {
                const hasVisible = section.querySelector('.radio-entry:not([hidden])') !== null;
                section.hidden = !hasVisible;
            });

            if (noResults) noResults.hidden = anyVisible;
        }

        radioSearch.addEventListener('input', applyRadioFilter);

        radioChips.querySelectorAll('.radio-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                radioChips.querySelectorAll('.radio-chip').forEach(c => c.classList.remove('active'));
                chip.classList.add('active');
                activeGroup = chip.dataset.group;
                applyRadioFilter();
            });
        });
    }

    // Deep-link support (Stage 8, Global Search): if the page was opened
    // with a URL fragment matching a reference entry's id (e.g.
    // /utility/radio/#noaa-weather-radio, as search results now link to),
    // open that entry and scroll to it. Works on every page that uses the
    // shared .radio-entry <details> component - no per-page wiring needed.
    // A no-op on any page without a matching id, and does nothing at all
    // if there's no fragment - plain in-page anchors still work normally.
    if (window.location.hash) {
        const target = document.getElementById(window.location.hash.slice(1));
        if (target && target.classList.contains('radio-entry')) {
            target.open = true;
            target.scrollIntoView({ block: 'start' });
        }
    }
});