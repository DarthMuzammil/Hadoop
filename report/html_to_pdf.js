// Prints report/WikiTrend_Report.html to report/WikiTrend_Report.pdf with headless Chromium (Playwright).
const path = require('path');
const { chromium } = require('playwright');

(async () => {
  const dir = __dirname;
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + path.join(dir, 'WikiTrend_Report.html'), { waitUntil: 'load' });
  await page.pdf({
    path: path.join(dir, 'WikiTrend_Report.pdf'),
    format: 'A4',
    printBackground: true,
    displayHeaderFooter: true,
    headerTemplate: '<span></span>',
    footerTemplate: '<div style="font-size:8px;width:100%;text-align:center;color:#777">' +
      'WikiTrend - Real-Time Breaking-News Detection using Hadoop &middot; page <span class="pageNumber"></span> of <span class="totalPages"></span></div>',
    margin: { top: '16mm', bottom: '18mm', left: '15mm', right: '15mm' },
  });
  await browser.close();
  console.log('wrote', path.join(dir, 'WikiTrend_Report.pdf'));
})();
