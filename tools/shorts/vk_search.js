// Поиск видео в ВК Видео через headless Chromium (без токена).
//   node vk_search.js "GTA 6 трейлер" "GTA 6 геймплей"  > links.txt
// Выводит ссылки vk.com/video-<owner>_<id>, по одной на строку.
// Метаданные: yt-dlp --skip-download --print "%(duration)s|%(uploader)s|%(title)s" <ссылка>
const { chromium } = require('playwright');
(async () => {
  const queries = process.argv.slice(2);
  if (!queries.length) { console.error('usage: node vk_search.js "<запрос>" [...]'); process.exit(1); }
  const browser = await chromium.launch();
  const page = await browser.newPage({ locale: 'ru-RU', viewport: { width: 1280, height: 1600 } });
  const out = new Set();
  for (const q of queries) {
    await page.goto('https://vkvideo.ru/search?q=' + encodeURIComponent(q), { waitUntil: 'networkidle', timeout: 60000 }).catch(() => {});
    for (let i = 0; i < 3; i++) { await page.mouse.wheel(0, 3000); await page.waitForTimeout(1500); }
    const hrefs = await page.$$eval('a', as => as.map(a => a.href));
    hrefs.filter(h => /vkvideo\.ru\/video-?\d+_\d+/.test(h))
         .forEach(h => out.add(h.split('?')[0].replace('vkvideo.ru', 'vk.com')));
  }
  console.log([...out].join('\n'));
  await browser.close();
})();
