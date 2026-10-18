import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

function pull(src, name) {
    const start = src.indexOf(`function ${name}(`);
    if (start < 0) throw new Error(`missing ${name}`);
    let i = src.indexOf("{", start);
    let depth = 0;
    let state = "code";
    for (; i < src.length; i += 1) {
        const c = src[i];
        const nxt = src[i + 1] || "";
        if (state === "code") {
            if (c === "{") depth += 1;
            else if (c === "}") {
                depth -= 1;
                if (depth === 0) return src.slice(start, i + 1);
            } else if (c === "/" && nxt === "/") {
                state = "line";
                i += 1;
            } else if (c === "/" && nxt === "*") {
                state = "block";
                i += 1;
            } else if (c === "'" || c === '"') state = c;
            else if (c === "`") state = "`";
        } else if (state === "line") {
            if (c === "\n") state = "code";
        } else if (state === "block") {
            if (c === "*" && nxt === "/") {
                state = "code";
                i += 1;
            }
        } else if (state === "'" || state === '"') {
            if (c === "\\") i += 1;
            else if (c === state) state = "code";
        } else if (state === "`") {
            if (c === "\\") i += 1;
            else if (c === "`") state = "code";
        }
    }
    throw new Error(`unclosed ${name}`);
}

const chat = fs.readFileSync(new URL("../frontend/js/chat.js", import.meta.url), "utf8");
const ctx = {};
vm.createContext(ctx);
vm.runInContext(
    `${pull(chat, "splitStreamText")}\n${pull(chat, "_isHtmlDocument")}\n${pull(chat, "_htmlCardMarkup")}`,
    ctx,
);

test("closed lines render, the open tail waits", () => {
    const split = ctx.splitStreamText("Hello\n**bo");
    assert.equal(split.stable, "Hello\n");
    assert.equal(split.tail, "**bo");
});

test("an open fence stays in the tail", () => {
    const split = ctx.splitStreamText("See\n```js\nconst x = 1");
    assert.equal(split.stable, "See\n");
    assert.equal(split.tail, "```js\nconst x = 1");
});

test("a closed fence joins the stable text after the next line", () => {
    const split = ctx.splitStreamText("See\n```js\nconst x = 1\n```\nNext\n");
    assert.equal(split.stable, "See\n```js\nconst x = 1\n```\nNext\n");
    assert.equal(split.tail, "");
});

test("only a real html document becomes a card", () => {
    assert.equal(ctx._isHtmlDocument("<!DOCTYPE html><html></html>"), true);
    assert.equal(ctx._isHtmlDocument("Use <html> in prose"), false);
    const markup = ctx._htmlCardMarkup("<html><script>alert(1)</script></html>");
    assert.match(markup, /^<div class="html-card" data-html="[A-Za-z0-9+/=]+"><\/div>$/);
    assert.equal(markup.includes("<script"), false);
});
