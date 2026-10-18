// ── Message Rendering ─────────────────────────────────────────

function createAudioPlayer(file, autoPlay = false) {
    const container = document.createElement("div");
    container.className = "custom-audio-player";
    
    const audio = document.createElement("audio");
    bindAuthedMedia(audio, file.url);
    audio.preload = "metadata";
    container.appendChild(audio);
    
    const playBtn = document.createElement("button");
    playBtn.className = "audio-play-btn";
    playBtn.innerHTML = '<span class="material-icons-round">play_arrow</span>';
    container.appendChild(playBtn);
    
    const progressContainer = document.createElement("div");
    progressContainer.className = "audio-progress-container";
    
    const progress = document.createElement("input");
    progress.type = "range";
    progress.className = "audio-progress-slider";
    progress.min = 0;
    progress.max = 100;
    progress.value = 0;
    progressContainer.appendChild(progress);
    container.appendChild(progressContainer);
    
    const timeLabel = document.createElement("span");
    timeLabel.className = "audio-time-label";
    timeLabel.textContent = "0:00 / 0:00";
    container.appendChild(timeLabel);
    
    function formatTime(secs) {
        if (isNaN(secs)) return "0:00";
        const m = Math.floor(secs / 60);
        const s = Math.floor(secs % 60);
        return `${m}:${s < 10 ? '0' : ''}${s}`;
    }
    
    audio.addEventListener("loadedmetadata", () => {
        timeLabel.textContent = `0:00 / ${formatTime(audio.duration)}`;
    });
    
    audio.addEventListener("timeupdate", () => {
        if (!audio.duration) return;
        const pct = (audio.currentTime / audio.duration) * 100;
        progress.value = pct;
        timeLabel.textContent = `${formatTime(audio.currentTime)} / ${formatTime(audio.duration)}`;
    });
    
    progress.addEventListener("input", (e) => {
        if (!audio.duration) return;
        const seekTo = (e.target.value / 100) * audio.duration;
        audio.currentTime = seekTo;
    });
    
    playBtn.addEventListener("click", () => {
        if (audio.paused) {
            document.querySelectorAll("audio").forEach(otherAudio => {
                if (otherAudio !== audio) otherAudio.pause();
            });
            audio.play().catch(err => console.debug("Play error:", err));
            playBtn.innerHTML = '<span class="material-icons-round">pause</span>';
        } else {
            audio.pause();
            playBtn.innerHTML = '<span class="material-icons-round">play_arrow</span>';
        }
    });
    
    audio.addEventListener("ended", () => {
        playBtn.innerHTML = '<span class="material-icons-round">play_arrow</span>';
        progress.value = 0;
    });
    
    if (autoPlay) {
        audio.addEventListener("canplaythrough", () => {
            const ttsToggle = document.getElementById("tts-toggle");
            if (ttsToggle && ttsToggle.checked) {
                if (window.speechTTS) window.speechTTS.stop();
                document.querySelectorAll("audio").forEach(otherAudio => {
                    if (otherAudio !== audio) otherAudio.pause();
                });
                audio.play().catch(err => console.debug("Autoplay blocked by browser policy"));
                playBtn.innerHTML = '<span class="material-icons-round">pause</span>';
            }
        }, { once: true });
    }
    
    return container;
}

async function downloadAttachment(url, fileName) {
    try {
        const res = await authFetch(url);
        if (!res.ok) throw new Error("Network response was not ok");
        const blob = await res.blob();
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = fileName || "download";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(a.href);
    } catch (e) {
        console.error("Download failed:", e);
    }
}

function _renderMessageBubble(content, attachments = [], autoPlayAudio = false) {
    const bubble = document.createElement("div");
    bubble.className = "message-bubble";

    if (content) {
        bubble.innerHTML = renderMarkdown(content);
        try { bubble.setAttribute("data-raw-content", typeof content === "string" ? content : JSON.stringify(content)); } catch (e) { }
        enhanceCodeBlocks(bubble);
    }

    attachments.forEach(file => {
        const isImage = typeof file.type === "string" && file.type.startsWith("image/");
        const isAudio = typeof file.type === "string" && file.type.startsWith("audio/");
        if (isImage) {
            const img = document.createElement("img");
            bindAuthedMedia(img, file.url);
            img.onload = () => { if (typeof scrollToBottom === 'function') scrollToBottom(); };
            img.onclick = () => openAuthedMedia(file.url);
            bubble.appendChild(img);
        } else if (isAudio) {
            const player = createAudioPlayer(file, autoPlayAudio);
            bubble.appendChild(player);
        } else {
            const link = buildFileAttachmentLink(file, () => {
                downloadAttachment(file.url, file.name || "attachment");
            });
            bubble.appendChild(link);
        }
    });

    return bubble;
}

function addUserMessage(content, attachments = []) {
    activateChat();
    const group = createMessageGroup("user");
    const bubble = _renderMessageBubble(content, attachments, false);
    group.querySelector(".message-content").appendChild(bubble);
    addTimestamp(group);
    chatHistory.appendChild(group);
    scrollToBottom();
}

function addAgentMessage(id, content, attachments = []) {
    activateChat();
    const group = createMessageGroup("agent");
    const bubble = _renderMessageBubble(content, attachments, true);
    group.querySelector(".message-content").appendChild(bubble);
    addTimestamp(group);
    chatHistory.appendChild(group);
    scrollToBottom();
}


// ── Process Groups (collapsible thinking/tool steps) ──────────
function addProcessStep(_msgId, _content, _badge) {
    // Tool names stay out of the chat. Typing dots cover the wait.
}

function updateProcessGroupTime(msgId) {
    const pg = state.processGroups[msgId];
    if (!pg) return;
    const elapsed = Math.round((Date.now() - pg.startTime) / 1000);
    const min = Math.floor(elapsed / 60);
    const sec = elapsed % 60;
    pg.headerEl.querySelector(".pg-time").textContent =
        min > 0 ? `${min}:${String(sec).padStart(2, "0")}` : `${sec}s`;
}

function collapseProcessGroup(msgId) {
    const pg = state.processGroups[msgId];
    if (!pg) return;
    clearInterval(pg.timer);

    updateProcessGroupTime(msgId);

    const title = pg.headerEl.querySelector(".pg-title");
    title.classList.remove("shiny-text");

    pg.el.classList.remove("expanded");
    pg.el.classList.add("completed");

    const badgeEl = pg.headerEl.querySelector(".step-badge");
    badgeEl.className = "step-badge END";
    badgeEl.textContent = "END";

    const summaryParts = [];
    if (pg.genCount > 0) summaryParts.push(`${pg.genCount} thinking`);
    if (pg.exeCount > 0) summaryParts.push(`${pg.exeCount} tool`);
    if (summaryParts.length > 0) {
        let summaryEl = pg.headerEl.querySelector(".pg-summary");
        if (!summaryEl) {
            summaryEl = document.createElement("span");
            summaryEl.className = "pg-summary";
            pg.headerEl.querySelector(".pg-metrics").appendChild(summaryEl);
        }
        summaryEl.textContent = summaryParts.join(" · ");
    }

    pg.collapsed = true;
    delete state.processGroups[msgId];
}


function renderProcessGroupFromHistory(_turnId, _steps, _targetContainer = chatHistory) {
    // Old sessions keep tool rows in the transcript file. The chat does not draw them.
}

// Owner Telegram ids from channels.telegram.allowFrom (cached).
let _telegramOwnerIds = null;
let _telegramOwnerIdsLoading = null;

async function ensureTelegramOwnerIds() {
    if (_telegramOwnerIds) return _telegramOwnerIds;
    if (_telegramOwnerIdsLoading) return _telegramOwnerIdsLoading;
    _telegramOwnerIdsLoading = (async () => {
        try {
            const res = await authFetch("/api/settings");
            if (!res.ok) return (_telegramOwnerIds = new Set());
            const cfg = await res.json();
            const tg = (cfg.channels && cfg.channels.telegram) || {};
            const raw = tg.allowFrom || tg.allow_from || [];
            _telegramOwnerIds = new Set(
                (Array.isArray(raw) ? raw : []).map(String).filter((id) => id && id !== "*")
            );
        } catch {
            _telegramOwnerIds = new Set();
        }
        return _telegramOwnerIds;
    })();
    return _telegramOwnerIdsLoading;
}

function classifySessionMessage(msg, sessionKey) {
    const meta = (msg && msg.metadata) || {};
    if (meta.is_bot_sender) {
        return { type: "agent", label: meta.first_name || "Shiba" };
    }
    const uid = meta.user_id != null ? String(meta.user_id) : "";
    const sk = sessionKey || (typeof state !== "undefined" ? state.sessionId : "") || "";
    // Telegram multi-speaker: non-allowFrom speakers on the left.
    if (sk.startsWith("telegram:") && uid) {
        const owners = _telegramOwnerIds;
        if (owners && owners.size) {
            if (!owners.has(uid)) {
                return { type: "peer", label: meta.first_name || meta.username || uid };
            }
            return { type: "user", label: null };
        }
        // Settings not loaded yet: heuristic for multi-party chats only.
        const chatPart = (sk.split(":")[1] || "");
        const multiParty = sk.includes(":guest:") || chatPart.startsWith("-")
            || meta.business_connection_id || meta.is_group || meta.is_guest;
        if (multiParty) {
            return { type: "peer", label: meta.first_name || meta.username || uid };
        }
    }
    return { type: "user", label: null };
}

function createMessageGroup(type, targetContainer = chatHistory, opts = {}) {
    state.messageCount++;
    const group = document.createElement("div");
    group.className = `message-group ${type}`;

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    if (type === "user" || type === "peer") {
        avatar.style.display = "none";
    } else {
        const img = document.createElement("img");
        const avatarSrc = state.profileAvatar || DEFAULT_AVATAR;
        img.src = avatarSrc;
        img.alt = "Shiba";
        img.className = "agent-avatar-img";
        img.onerror = function() {
            if (this.src.includes("/static/")) {
                this.src = "/shibaclaw_logo.webp";
            } else {
                this.src = "/static/shibaclaw_logo.webp";
            }
        };
        avatar.appendChild(img);
    }
    group.appendChild(avatar);

    const prev = targetContainer ? targetContainer.lastElementChild : null;
    const prevIsProcessGroup = prev && prev.classList.contains("process-group");
    const prevGroup = prevIsProcessGroup ? targetContainer.children[targetContainer.children.length - 2] : prev;
    const sameType = prevGroup && prevGroup.classList.contains("message-group") && prevGroup.classList.contains(type);
    const labelText = (opts && opts.label) || (type === "agent" ? "Shiba" : "");
    if (labelText) group.dataset.senderLabel = labelText;
    const prevLabel = prevGroup && prevGroup.dataset ? (prevGroup.dataset.senderLabel || "") : "";
    if (!sameType || (labelText && labelText !== prevLabel)) group.classList.add("show-avatar");

    const content = document.createElement("div");
    content.className = "message-content";
    if (labelText && (type === "peer" || type === "agent")) {
        const lab = document.createElement("div");
        lab.className = "message-sender-label";
        lab.textContent = labelText;
        content.appendChild(lab);
    }
    group.appendChild(content);

    return group;
}

function addTimestamp(group, dateStr) {
    const d = dateStr ? new Date(dateStr) : new Date();
    const time = document.createElement("div");
    time.className = "message-time";
    time.textContent = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    const meta = document.createElement("div");
    meta.className = "message-meta";
    meta.appendChild(time);

    const copyBtn = document.createElement("button");
    copyBtn.className = "btn-copy-msg";
    copyBtn.type = "button";
    copyBtn.setAttribute('aria-label', 'Copy message');
    copyBtn.title = typeof t === "function" ? t("chat.copy_message") : "Copy message";
    copyBtn.innerHTML = '<span class="material-icons-round" style="font-size:14px">content_copy</span>';
    copyBtn.addEventListener('click', (e) => { e.stopPropagation(); window.copyMessage(copyBtn); });
    meta.appendChild(copyBtn);

    const contentEl = group.querySelector(".message-content");
    contentEl.appendChild(meta);
}


// ── Markdown Rendering ────────────────────────────────────────
function splitStreamText(text) {
    const src = String(text || "");
    let i = 0;
    let fence = false;
    let safe = 0;
    while (i < src.length) {
        if (src.startsWith("```", i)) {
            fence = !fence;
            i += 3;
            continue;
        }
        if (!fence && src[i] === "\n") safe = i + 1;
        i += 1;
    }
    return { stable: src.slice(0, safe), tail: src.slice(safe) };
}

function _isHtmlDocument(text) {
    const t = String(text || "").trim();
    return /^<!doctype\s+html\b/i.test(t) || /^<html[\s>]/i.test(t);
}

function _htmlCardMarkup(doc) {
    const bytes = new TextEncoder().encode(String(doc));
    let bin = "";
    for (let i = 0; i < bytes.length; i += 1) bin += String.fromCharCode(bytes[i]);
    return `<div class="html-card" data-html="${btoa(bin)}"></div>`;
}

function mountHtmlCards(container) {
    if (!container || !container.querySelectorAll) return;
    container.querySelectorAll(".html-card[data-html]").forEach((el) => {
        if (el.querySelector("iframe")) return;
        let html = "";
        try {
            const bin = atob(el.dataset.html || "");
            const bytes = Uint8Array.from(bin, (ch) => ch.charCodeAt(0));
            html = new TextDecoder().decode(bytes);
        } catch (e) {
            return;
        }
        el.removeAttribute("data-html");
        const label = document.createElement("div");
        label.className = "html-card-label";
        label.textContent = "HTML";
        const frame = document.createElement("iframe");
        frame.className = "html-card-frame";
        frame.setAttribute("sandbox", "");
        frame.referrerPolicy = "no-referrer";
        frame.title = "HTML";
        frame.srcdoc = html;
        el.replaceChildren(label, frame);
    });
}

function renderMarkdown(text) {
    if (!text) return "";

    let content = text;

    if (typeof content === "string" && content.trim().startsWith("[") && content.trim().endsWith("]")) {
        try {
            const parsed = JSON.parse(content);
            if (Array.isArray(parsed)) content = parsed;
        } catch (e) { }
    }

    if (Array.isArray(content)) {
        content = content
            .filter(block => block && block.type === "text")
            .map(block => block.text)
            .join("\n");
    }

    if (typeof content === "string") {
        content = content.replace(/\[image:\s*[^\]]+\]/gi, "").trim();
    }

    if (typeof content === "string" && _isHtmlDocument(content)) {
        return _htmlCardMarkup(content);
    }

    if (typeof marked !== "undefined") {
        try {
            let processedContent = content;
            const codeBlocks = [];
            const inlineCodes = [];
            const htmlCards = [];

            processedContent = processedContent.replace(/```(?:html|htm)\s*\n([\s\S]*?)```/gi, (match, body) => {
                if (!_isHtmlDocument(body)) return match;
                htmlCards.push(body.trim());
                return "\n\n%%HTMLCARD_" + (htmlCards.length - 1) + "%%\n\n";
            });

            processedContent = processedContent.replace(/```[\s\S]*?```/g, (match) => {
                codeBlocks.push(match);
                return `__CODE_BLOCK_PLACEHOLDER_${codeBlocks.length - 1}__`;
            });

            processedContent = processedContent.replace(/`[^`]+`/g, (match) => {
                inlineCodes.push(match);
                return `__INLINE_CODE_PLACEHOLDER_${inlineCodes.length - 1}__`;
            });

            // Preferences cached externally via refreshThoughtPrefs()
            let hideThoughts = _cachedHideThoughts;
            let collapseThoughts = _cachedCollapseThoughts;

            processedContent = processedContent.replace(/<think>([\s\S]*?)<\/think>/gi, (match, p1) => {
                let restoredP1 = p1;
                restoredP1 = restoredP1.replace(/__INLINE_CODE_PLACEHOLDER_(\d+)__/g, (m, idx) => inlineCodes[parseInt(idx, 10)]);
                restoredP1 = restoredP1.replace(/__CODE_BLOCK_PLACEHOLDER_(\d+)__/g, (m, idx) => codeBlocks[parseInt(idx, 10)]);
                if (hideThoughts) return "";
                const innerParsed = marked.parse(restoredP1.trim());
                const detailsOpen = collapseThoughts ? "" : " open";
                return `<details class="thought-block"${detailsOpen}><summary><span class="material-icons-round" style="font-size:14px">psychology</span>Ragionamento concluso</summary><div class="thought-content">${innerParsed}</div></details>\n\n`;
            });

            if (processedContent.match(/<think>([\s\S]*)$/i) && !processedContent.match(/<\/think>/i)) {
                processedContent = processedContent.replace(/<think>([\s\S]*)$/i, (match, p1) => {
                    if (hideThoughts) return "";
                    let restoredP1 = p1;
                    restoredP1 = restoredP1.replace(/__INLINE_CODE_PLACEHOLDER_(\d+)__/g, (m, idx) => inlineCodes[parseInt(idx, 10)]);
                    restoredP1 = restoredP1.replace(/__CODE_BLOCK_PLACEHOLDER_(\d+)__/g, (m, idx) => codeBlocks[parseInt(idx, 10)]);
                    const innerParsed = marked.parse(restoredP1.trim());
                    const detailsOpen = collapseThoughts ? "" : " open";
                    return `<details class="thought-block"${detailsOpen}><summary><span class="material-icons-round" style="font-size:14px">psychology</span>Ragionamento in corso...<span class="typing-dots-inline" style="margin-left:8px"><span></span><span></span><span></span></span></summary><div class="thought-content">${innerParsed}</div></details>\n\n`;
                });
            }

            const mentions = [];
            // Format mentions as beautiful chips
            processedContent = processedContent.replace(/@(kb|mcp|app):(?:"([^"]+)"|([^\s<]+))/gi, (match, type, name1, name2) => {
                const name = name1 || name2;
                let icon = "dns";
                let t = type.toLowerCase();
                let colorClass = "";
                if (t === "kb") { icon = "menu_book"; colorClass = "mention-kb"; }
                else if (t === "app" || t === "mcp") { icon = "apps"; colorClass = "mention-app"; }
                mentions.push(`<span class="mention-chip-inline ${colorClass}"><span class="material-icons-round">${icon}</span>${name}</span>`);
                return `@@MENTION_PLACEHOLDER_${mentions.length - 1}@@`;
            });

            processedContent = processedContent.replace(/__INLINE_CODE_PLACEHOLDER_(\d+)__/g, (match, p1) => {
                return inlineCodes[parseInt(p1, 10)];
            });

            processedContent = processedContent.replace(/__CODE_BLOCK_PLACEHOLDER_(\d+)__/g, (match, p1) => {
                return codeBlocks[parseInt(p1, 10)];
            });

            let finalHtml = marked.parse(processedContent);
            
            finalHtml = finalHtml.replace(/@@MENTION_PLACEHOLDER_(\d+)@@/g, (match, p1) => {
                return mentions[parseInt(p1, 10)];
            });
            
            if (typeof DOMPurify !== "undefined") {
                finalHtml = DOMPurify.sanitize(finalHtml, {
                    ADD_ATTR: ['target']
                });
            }

            finalHtml = finalHtml.replace(/%%HTMLCARD_(\d+)%%/g, (match, id) => {
                const doc = htmlCards[Number(id)];
                return doc ? _htmlCardMarkup(doc) : "";
            });

            return finalHtml;
        } catch (e) {
            console.error("Markdown parse error:", e);
        }
    }

    return escapeHtml(content).replace(/\n/g, "<br>");
}

function enhanceMarkdownTables(container) {
    container.querySelectorAll("table").forEach((table) => {
        if (table.parentElement && table.parentElement.classList.contains("table-scroll")) return;

        const wrapper = document.createElement("div");
        wrapper.className = "table-scroll";
        table.parentNode.insertBefore(wrapper, table);
        wrapper.appendChild(table);
    });
}

function enhanceCodeBlocks(container) {
    enhanceMarkdownTables(container);
    mountHtmlCards(container);

    container.querySelectorAll("pre").forEach((pre) => {
        const code = pre.querySelector("code");
        if (!code) return;

        const langClass = [...code.classList].find((c) => c.startsWith("language-"));
        const lang = langClass ? langClass.replace("language-", "") : "";

        if (typeof hljs !== "undefined" && !code.classList.contains("hljs")) {
            if (lang && hljs.getLanguage(lang)) {
                code.innerHTML = hljs.highlight(code.textContent, { language: lang }).value;
            } else {
                hljs.highlightElement(code);
            }
        }

        if (!pre.querySelector(".code-block-header")) {
            const header = document.createElement("div");
            header.className = "code-block-header";
            header.innerHTML = `
                <span>${lang || "code"}</span>
                <button class="btn-copy-code" onclick="copyCode(this)">Copy</button>
            `;
            pre.insertBefore(header, pre.firstChild);
        }
    });
}


// ── Typing Bubble: one live line, not a tool log ─────────────
function _statusRu() {
    const loc = window.i18n && window.i18n.getLocale && window.i18n.getLocale();
    return !loc || loc === "ru";
}

function workStatus(raw) {
    const ru = _statusRu();
    const idle = ru ? "Думаю" : "Thinking";
    const text = String(raw || "").trim();
    if (!text) return idle;
    const re = /([A-Za-z_][\w]*)(?:\("((?:[^"\\]|\\.)*)"\))?/g;
    let last = null;
    let match;
    while ((match = re.exec(text))) last = match;
    if (!last) return idle;
    const name = last[1];
    let arg = (last[2] || "").replace(/\\"/g, '"').replace(/\\n/g, " ").replace(/\s+/g, " ").trim();
    const verbs = ru
        ? { web_search: "Ищу", web_fetch: "Читаю", web_deep_search: "Копаю источники", exec: "Запускаю", read_file: "Открываю", write_file: "Пишу", edit_file: "Правлю", ask_user: "Жду выбор" }
        : { web_search: "Searching", web_fetch: "Reading", web_deep_search: "Digging", exec: "Running", read_file: "Opening", write_file: "Writing", edit_file: "Editing", ask_user: "Waiting" };
    const verb = verbs[name] || (ru ? "Работаю" : "Working");
    if (!arg) return verb;
    if (name === "exec") {
        const bin = arg.split(" ")[0].split("/").pop();
        return bin ? `${verb} ${bin}` : verb;
    }
    if (/^https?:\/\//i.test(arg)) {
        try { arg = new URL(arg).hostname.replace(/^www\./, ""); } catch { arg = ""; }
    } else if (arg.includes("/") && !arg.includes(" ")) {
        arg = arg.split("/").filter(Boolean).pop() || arg;
    }
    if (!arg) return verb;
    if (arg.length > 42) arg = arg.slice(0, 41) + "…";
    return `${verb} · ${arg}`;
}

function showTypingBubble(label) {
    const text = label || (_statusRu() ? "Думаю" : "Thinking");
    let group = document.getElementById("typing-bubble");
    if (!group) {
        activateChat();
        group = createMessageGroup("agent");
        group.id = "typing-bubble";
        const content = group.querySelector(".message-content");
        const bubble = document.createElement("div");
        bubble.className = "message-bubble typing-bubble";
        bubble.innerHTML = `<span class="typing-status"></span>`;
        content.appendChild(bubble);
        chatHistory.appendChild(group);
        scrollToBottom();
    }
    const status = group.querySelector(".typing-status");
    if (status) status.textContent = text;
}

function hideTypingBubble() {
    const el = document.getElementById("typing-bubble");
    if (el) el.remove();
}

function scrollToBottom(opts) {
    const force = !!(opts && opts.force);
    if (scrollToBottom._frame) {
        if (!force) return;
        cancelAnimationFrame(scrollToBottom._frame);
        scrollToBottom._frame = null;
    }

    // Do not force scroll if the user is scrolling up to read history
    if (!force) {
        const threshold = 150;
        const isNearBottom = chatHistory.scrollHeight - chatHistory.scrollTop - chatHistory.clientHeight < threshold;
        if (!isNearBottom && chatHistory.scrollTop > 0) return;
    }

    const snap = () => {
        chatHistory.scrollTop = chatHistory.scrollHeight;
    };
    if (force) {
        // Snap synchronously so an opened session starts at its latest messages.
        snap();
        requestAnimationFrame(() => {
            snap();
            requestAnimationFrame(snap);
        });
        setTimeout(snap, 120);
        setTimeout(snap, 400);
        return;
    }
    scrollToBottom._frame = requestAnimationFrame(() => {
        scrollToBottom._frame = null;
        snap();
    });
}

function updateSendButton() {
    const hasText = chatInput.value.trim().length > 0;
    btnSend.disabled = !hasText;
    
    const iconSpan = btnSend.querySelector(".material-icons-round");
    if (iconSpan) {
        if (state.processing) {
            iconSpan.textContent = "navigation";
            btnSend.title = typeof t === "function" ? t("chat.steer") : "Steer the agent";
        } else {
            iconSpan.textContent = "arrow_upward";
            btnSend.title = hasText
                ? (typeof t === "function" ? t("chat.send") : "Send message")
                : (typeof t === "function" ? t("chat.type_to_send") : "Type a message to send");
        }
    }
}
window.updateSendButton = updateSendButton;

function autoResizeInput() {
    chatInput.style.height = "auto";
    const maxHeight = parseFloat(window.getComputedStyle(chatInput).maxHeight) || 200;
    chatInput.style.height = Math.min(chatInput.scrollHeight, maxHeight) + "px";
    const area = chatInput.closest(".input-area");
    if (area) document.documentElement.style.setProperty("--mobile-composer-height", `${Math.ceil(area.getBoundingClientRect().height)}px`);
}


// ── Send Message ─────────────────────────────────────────────
function sendMessage() {
    const content = chatInput.value.trim();
    if (!content && state.stagedFiles.length === 0) return;

    if (!realtime.connected) {
        addAgentMessage("error", "⚠️ WebSocket disconnected. Wait for reconnect or reload the window.");
        if (!state.processing) {
            state.processing = false;
            updateSendButton();
        }
        return;
    }

    if (state.gatewayKnown && !state.gatewayUp) {
        addAgentMessage("error", typeof t === "function" ? t("chat.gateway_offline") : "⚠️ Gateway offline or unreachable. Restart the desktop app or the gateway.");
        if (!state.processing) {
            state.processing = false;
            updateSendButton();
        }
        return;
    }

    const wasProcessing = state.processing;
    state.processing = true;
    updateSendButton();

    try {
        const attachments = [...state.stagedFiles];
        addUserMessage(content, attachments);

        const sent = realtime.emit("message", {
            content,
            attachments: attachments.map(a => ({
                name: a.name,
                url: a.url,
                type: a.type,
                mode: a.mode
            }))
        });

        if (!sent) {
            throw new Error("Realtime connection is not open.");
        }

        chatInput.value = "";
        state.stagedFiles = [];
        updateStagingUI();
        autoResizeInput();
        updateSendButton();
    } catch (e) {
        console.error("Send error:", e);
        addAgentMessage("error", `⚠️ ${e.message || "Failed to send message."}`);
        if (!wasProcessing) {
            state.processing = false;
        }
        updateSendButton();
    }
}


