const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '../web/index.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];

function app(initial) {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, {
      innerHTML: '', textContent: '', value: '', disabled: false,
      reset() {}, focus() {},
    });
    return elements.get(id);
  };
  const responses = [initial];
  const timers = [];
  const context = vm.createContext({
    document: { getElementById: element },
    localStorage: { getItem: () => null, setItem() {} },
    fetch: async () => {
      const next = responses.shift();
      if (next instanceof Error) throw next;
      return { ok: true, json: async () => next };
    },
    setInterval: callback => timers.push(callback),
    Date, console,
  });
  vm.runInContext(script, context);
  return {
    element, responses, timers,
    async flush() { await new Promise(resolve => setImmediate(resolve)); },
    async poll() { await timers[0](); },
    context,
  };
}

const reminder = (id, overrides = {}) => ({
  id: String(id), title: 'Read chapter', details: null, remind_at: null,
  completed: false, updated_at: '2026-11-10T00:00:00Z', ...overrides,
});

test('shows an in-page notification for changes by another visitor, not on first load', async () => {
  const page = app([reminder(1)]);
  await page.flush();
  assert.equal(page.element('notifications').textContent, '');
  assert.equal(page.timers.length, 1);

  page.responses.push([reminder(1), reminder(2, { title: 'Exam' })]);
  await page.poll();
  assert.match(page.element('notifications').textContent, /Exam.*added/);
});

test('announces edits, completion, reopening and deletion, but not unchanged polls', async () => {
  const page = app([reminder(1)]);
  await page.flush();
  page.responses.push([reminder(1, { details: 'Chapter 2' })]);
  await page.poll();
  assert.match(page.element('notifications').textContent, /Read chapter updated/);
  page.element('notifications').textContent = '';
  page.responses.push([reminder(1, { details: 'Chapter 2' })]);
  await page.poll();
  assert.equal(page.element('notifications').textContent, '');
  page.responses.push([reminder(1, { details: 'Chapter 2', completed: true })]);
  await page.poll();
  assert.match(page.element('notifications').textContent, /Read chapter completed/);
  page.responses.push([reminder(1, { details: 'Chapter 2', completed: false })]);
  await page.poll();
  assert.match(page.element('notifications').textContent, /Read chapter reopened/);
  page.responses.push([]);
  await page.poll();
  assert.match(page.element('notifications').textContent, /Read chapter deleted/);
});

test('local changes do not notify the visitor who made them', async () => {
  const page = app([reminder(1)]);
  await page.flush();
  page.responses.push(reminder(2), [reminder(1), reminder(2)]);
  page.element('reminder-title').value = 'Read chapter';
  await page.element('reminder-form').onsubmit({ preventDefault() {}, target: { reset() {} } });
  assert.equal(page.element('notifications').textContent, '');
  page.responses.push([reminder(1), reminder(2)]);
  await page.poll();
  assert.equal(page.element('notifications').textContent, '');
});
