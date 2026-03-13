/**
 * RS Histogram Dashboard — Google Apps Script
 * ============================================
 * Paste this entire file into Extensions > Apps Script, then run buildDashboard().
 *
 * What it builds:
 *   • "Data"      — backend sheet: GOOGLEFINANCE price history for every ticker
 *                   (~25 trading days), fetched via spill formula starting at col E.
 *   • "Dashboard" — main view with: Ticker | Name | RS Sparkline | RS Now |
 *                   1D Δ | 5D Δ | 20D Δ, grouped with separators and
 *                   conditional formatting.
 */

// ─── Configuration ────────────────────────────────────────────────────────────

const BENCHMARK = 'SPY';
const TRADING_DAYS = 25;   // history window (≈ 1 month)

/**
 * Ticker groups.  Each group produces a labelled separator row in the dashboard.
 * The benchmark ticker (SPY) must be in the first group so its price series is
 * always available when RS values are computed.
 */
const TICKER_GROUPS = [
  {
    label: 'INDEX',
    tickers: [
      { symbol: 'SPY',  name: 'SPDR S&P 500 ETF' },
      { symbol: 'QQQ',  name: 'Invesco Nasdaq-100 ETF' },
      { symbol: 'IWM',  name: 'iShares Russell 2000 ETF' },
    ],
  },
  {
    label: 'SECTOR ETF',
    tickers: [
      { symbol: 'XLK',  name: 'Technology Select Sector' },
      { symbol: 'XLY',  name: 'Consumer Discretionary Sel.' },
      { symbol: 'XLF',  name: 'Financial Select Sector' },
      { symbol: 'XLV',  name: 'Health Care Select Sector' },
      { symbol: 'XLE',  name: 'Energy Select Sector' },
      { symbol: 'XLI',  name: 'Industrial Select Sector' },
      { symbol: 'XLB',  name: 'Materials Select Sector' },
      { symbol: 'XLC',  name: 'Comm. Services Select Sector' },
      { symbol: 'XLRE', name: 'Real Estate Select Sector' },
      { symbol: 'XLU',  name: 'Utilities Select Sector' },
    ],
  },
  {
    label: 'STOCK',
    tickers: [
      { symbol: 'NVDA',  name: 'NVIDIA Corporation' },
      { symbol: 'AAPL',  name: 'Apple Inc.' },
      { symbol: 'MSFT',  name: 'Microsoft Corporation' },
      { symbol: 'AMZN',  name: 'Amazon.com Inc.' },
      { symbol: 'GOOGL', name: 'Alphabet Inc.' },
      { symbol: 'META',  name: 'Meta Platforms Inc.' },
      { symbol: 'TSLA',  name: 'Tesla Inc.' },
    ],
  },
];

// Flatten to a single ordered list (used throughout)
const ALL_TICKERS = TICKER_GROUPS.flatMap(g => g.tickers);

// Dashboard column indices (1-based)
const COL = {
  TICKER:     1,
  NAME:       2,
  SPARKLINE:  3,
  RS_NOW:     4,
  DELTA_1D:   5,
  DELTA_5D:   6,
  DELTA_20D:  7,
};

// Colours
const CLR = {
  HEADER_BG:     '#1a1a2e',   // dark navy
  HEADER_FG:     '#e0e0e0',   // light grey text
  SEP_BG:        '#2d2d44',   // slightly lighter navy for group separators
  SEP_FG:        '#a0a8c0',
  ROW_EVEN:      '#f8f9fc',
  ROW_ODD:       '#ffffff',
  GREEN:         '#1e8e3e',
  GREEN_LIGHT:   '#e6f4ea',
  YELLOW:        '#e37400',
  YELLOW_LIGHT:  '#fef7e0',
  RED:           '#c5221f',
  RED_LIGHT:     '#fce8e6',
  BORDER:        '#d0d4e0',
};

// ─── Entry point ──────────────────────────────────────────────────────────────

function buildDashboard() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  // Build back-end first so formulas are in place
  const dataSheet = buildDataSheet(ss);
  SpreadsheetApp.flush();  // let GOOGLEFINANCE start loading

  const dashSheet = buildDashboardSheet(ss, dataSheet);

  // Make Dashboard the active (visible) sheet
  ss.setActiveSheet(dashSheet);
  SpreadsheetApp.getUi().alert(
    '✅ RS Dashboard built!\n\n' +
    'Note: GOOGLEFINANCE data may take 30–60 seconds to fully populate.\n' +
    'Sparklines and RS values will update automatically once prices load.'
  );
}

// ─── DATA SHEET ───────────────────────────────────────────────────────────────

function buildDataSheet(ss) {
  let sheet = ss.getSheetByName('Data');
  if (sheet) {
    sheet.clearContents();
    sheet.clearFormats();
  } else {
    sheet = ss.insertSheet('Data');
  }

  // ── Row 1: config header ──
  sheet.getRange('A1').setValue('Config');
  sheet.getRange('B1').setValue('Value');
  sheet.getRange('A2').setValue('TRADING_DAYS');
  sheet.getRange('B2').setValue(TRADING_DAYS);
  sheet.getRange('A3').setValue('BENCHMARK');
  sheet.getRange('B3').setValue(BENCHMARK);

  // ── Column headers for ticker price block ──
  // Layout: col A=ticker, col B=name, col C=row index (for formula reference),
  //         col D=blank spacer, col E onward = spilled GOOGLEFINANCE history
  sheet.getRange('A5').setValue('Ticker');
  sheet.getRange('B5').setValue('Name');
  sheet.getRange('C5').setValue('DataRow');
  sheet.getRange('D5').setValue('NumDays');
  sheet.getRange('E5').setValue('← Price history starts here (spill →)');

  const headerRange = sheet.getRange('A5:E5');
  headerRange.setFontWeight('bold');
  headerRange.setBackground('#d0d8f0');

  // ── One row per ticker ──
  ALL_TICKERS.forEach((t, i) => {
    const row = 6 + i;   // data rows start at row 6
    sheet.getRange(row, 1).setValue(t.symbol);
    sheet.getRange(row, 2).setValue(t.name);
    sheet.getRange(row, 3).setValue(row);   // self-referential row number
    sheet.getRange(row, 4).setValue(TRADING_DAYS);

    // GOOGLEFINANCE spill formula in col E:
    // Returns a 2-col table: [Date, Close].  We only need the Close column.
    // The formula fetches the last TRADING_DAYS trading sessions.
    const formula =
      `=IFERROR(` +
        `TRANSPOSE(` +
          `INDEX(` +
            `GOOGLEFINANCE("${t.symbol}","close",TODAY()-40,TODAY(),"DAILY"),` +
            `,2` +
          `)` +
        `)` +
      `,"")`;
    sheet.getRange(row, 5).setFormula(formula);
  });

  // ── Named ranges for easy dashboard reference ──
  // We'll reference data by absolute row/col in dashboard formulas rather than
  // named ranges, since spill size varies.  But we store the block bounds here.
  const dataStartRow = 6;
  const dataEndRow   = 5 + ALL_TICKERS.length;
  sheet.getRange(`A${dataStartRow}:A${dataEndRow}`).setFontFamily('Courier New');

  // ── Light formatting ──
  sheet.setColumnWidth(1, 60);
  sheet.setColumnWidth(2, 200);
  sheet.setColumnWidth(3, 60);
  sheet.setColumnWidth(4, 60);
  sheet.setColumnWidths(5, 35, 55);  // price columns

  sheet.setFrozenRows(5);
  return sheet;
}

// ─── DASHBOARD SHEET ──────────────────────────────────────────────────────────

function buildDashboardSheet(ss, dataSheet) {
  let sheet = ss.getSheetByName('Dashboard');
  if (sheet) {
    sheet.clearContents();
    sheet.clearFormats();
    sheet.clearConditionalFormatRules();
  } else {
    sheet = ss.insertSheet('Dashboard', 0);
  }

  // ── Column widths ──
  sheet.setColumnWidth(COL.TICKER,    72);
  sheet.setColumnWidth(COL.NAME,      200);
  sheet.setColumnWidth(COL.SPARKLINE, 180);
  sheet.setColumnWidth(COL.RS_NOW,    80);
  sheet.setColumnWidth(COL.DELTA_1D,  70);
  sheet.setColumnWidth(COL.DELTA_5D,  70);
  sheet.setColumnWidth(COL.DELTA_20D, 70);

  // ── Header row ──
  buildDashboardHeader(sheet);

  // ── Content rows ──
  let currentRow = 2;

  TICKER_GROUPS.forEach((group, gi) => {
    // Group separator
    currentRow = addGroupSeparator(sheet, currentRow, group.label);

    // Ticker rows
    group.tickers.forEach(t => {
      const tickerIndex = ALL_TICKERS.findIndex(x => x.symbol === t.symbol);
      addTickerRow(sheet, currentRow, t, tickerIndex, dataSheet.getName());
      currentRow++;
    });
  });

  const lastDataRow = currentRow - 1;

  // ── Freeze header ──
  sheet.setFrozenRows(1);

  // ── Alternating row backgrounds (excluding separator rows) ──
  applyAlternatingRows(sheet, lastDataRow);

  // ── Conditional formatting ──
  applyConditionalFormatting(sheet, lastDataRow);

  return sheet;
}

// ── Dashboard header row ──────────────────────────────────────────────────────

function buildDashboardHeader(sheet) {
  const labels = ['Ticker', 'Name', 'RS Histogram (25D)', 'RS Now', '1D Δ', '5D Δ', '20D Δ'];
  const hdr = sheet.getRange(1, 1, 1, labels.length);
  hdr.setValues([labels]);
  hdr.setBackground(CLR.HEADER_BG);
  hdr.setFontColor(CLR.HEADER_FG);
  hdr.setFontWeight('bold');
  hdr.setFontSize(10);
  hdr.setVerticalAlignment('middle');
  hdr.setHorizontalAlignment('center');
  sheet.setRowHeight(1, 32);
  hdr.setBorder(false, false, true, false, false, false, CLR.BORDER, SpreadsheetApp.BorderStyle.SOLID_MEDIUM);
}

// ── Group separator row ───────────────────────────────────────────────────────

function addGroupSeparator(sheet, row, label) {
  sheet.setRowHeight(row, 22);
  const sepRange = sheet.getRange(row, 1, 1, 7);
  sepRange.merge();
  sepRange.setValue('▸  ' + label);
  sepRange.setBackground(CLR.SEP_BG);
  sepRange.setFontColor(CLR.SEP_FG);
  sepRange.setFontWeight('bold');
  sepRange.setFontSize(9);
  sepRange.setVerticalAlignment('middle');
  // Tag so alternating-row logic can skip it
  sheet.getRange(row, 8).setValue('__sep__');
  return row + 1;
}

// ── Single ticker row ─────────────────────────────────────────────────────────

/**
 * dataRow: 0-based index into ALL_TICKERS → maps to sheet row (6 + index) in Data sheet.
 * SPY is always index 0, sheet row 6.
 */
function addTickerRow(sheet, dashRow, ticker, tickerIndex, dataSheetName) {
  sheet.setRowHeight(dashRow, 36);

  // Data sheet rows are 1-based; ticker data starts at row 6.
  const dataRowNum    = 6 + tickerIndex;          // this ticker's row in Data sheet
  const spyRowNum     = 6;                         // SPY is always row 6

  // In the Data sheet, price history spills from col E (col 5) rightward.
  // We don't know the exact number of columns returned, but we fetched up to 40
  // calendar days to get ~25 trading days.  We reference the last TRADING_DAYS
  // values using OFFSET from the right edge of the spill.
  //
  // Helper formula snippet — returns an array of the last N closing prices
  // for a given row in the Data sheet:
  //   OFFSET(dataSheet!E<row>, 0, COUNTA(dataSheet!E<row>:AZ<row>)-N, 1, N)

  const priceArray = (row, n) =>
    `OFFSET(${dataSheetName}!E${row},0,COUNTA(${dataSheetName}!E${row}:AZ${row})-${n},1,${n})`;

  const spyPrices  = priceArray(spyRowNum,  TRADING_DAYS);
  const tickPrices = priceArray(dataRowNum, TRADING_DAYS);

  // ── Col A: Ticker ──
  const tickerCell = sheet.getRange(dashRow, COL.TICKER);
  tickerCell.setValue(ticker.symbol);
  tickerCell.setFontFamily('Courier New');
  tickerCell.setFontWeight('bold');
  tickerCell.setFontSize(10);
  tickerCell.setHorizontalAlignment('center');
  tickerCell.setVerticalAlignment('middle');

  // ── Col B: Name ──
  const nameCell = sheet.getRange(dashRow, COL.NAME);
  nameCell.setValue(ticker.name);
  nameCell.setFontSize(9);
  nameCell.setVerticalAlignment('middle');

  // ── Col C: RS Histogram Sparkline ──
  // RS series = ticker_close / spy_close for each day, then normalised to 1.0
  // Sparkline bar chart: green bars above 1, red below.  Sheets SPARKLINE
  // doesn't support per-bar colouring; we use a workaround with two stacked
  // bar series (positive delta and negative delta) coloured separately.
  //
  // Approach:
  //   rsValues  = ARRAYFORMULA(tickPrices / spyPrices)
  //   We show the series relative to its own first value so the chart's
  //   baseline is the starting RS level.
  //   pos_delta = MAX(0, rs - rs_baseline)   → green series
  //   neg_delta = MIN(0, rs - rs_baseline)   → red series   (shown as negative bar)
  //
  // We normalise so baseline = rs on day 1.

  const rsFormula =
    `=IFERROR(` +
      `LET(` +
        `tick,${tickPrices},` +
        `spy,${spyPrices},` +
        `rs,ARRAYFORMULA(tick/spy),` +
        `base,INDEX(rs,1),` +
        `delta,ARRAYFORMULA(rs-base),` +
        `pos,ARRAYFORMULA(MAX(0,delta)),` +   // <-- won't work element-wise; fix below
        // ARRAYFORMULA(MAX(…)) doesn't apply MAX element-wise in LET; use IF instead:
        `posArr,ARRAYFORMULA(IF(delta>0,delta,0)),` +
        `negArr,ARRAYFORMULA(IF(delta<0,delta,0)),` +
        `SPARKLINE(` +
          `TRANSPOSE(CHOOSE({1,2},posArr,negArr)),` +
          `{"charttype","bar";` +
           `"color1","${CLR.GREEN}";` +
           `"color2","${CLR.RED}";` +
           `"negativecolor","${CLR.RED}";` +
           `"min",-0.05;` +
           `"max",0.05}` +
        `)` +
      `)` +
    `,"")`;

  const sparkCell = sheet.getRange(dashRow, COL.SPARKLINE);
  sparkCell.setFormula(rsFormula);
  sparkCell.setVerticalAlignment('middle');

  // ── Col D: RS Now ──
  // Current RS = last ticker close / last SPY close
  const rsNowFormula =
    `=IFERROR(` +
      `LET(` +
        `tick,${tickPrices},` +
        `spy,${spyPrices},` +
        `ROUND(INDEX(tick,COUNTA(tick))/INDEX(spy,COUNTA(spy)),4)` +
      `)` +
    `,"")`;

  const rsNowCell = sheet.getRange(dashRow, COL.RS_NOW);
  rsNowCell.setFormula(rsNowFormula);
  rsNowCell.setNumberFormat('0.0000');
  rsNowCell.setHorizontalAlignment('center');
  rsNowCell.setVerticalAlignment('middle');
  rsNowCell.setFontWeight('bold');
  rsNowCell.setFontSize(10);

  // ── Helper: RS at offset N days ago ──
  // rs(n) = close[end-n] / spy[end-n]
  const rsAtOffset = (n) =>
    `LET(tick,${tickPrices},spy,${spyPrices},` +
    `INDEX(tick,COUNTA(tick)-${n})/INDEX(spy,COUNTA(spy)-${n}))`;

  const rsNow    = `(${rsAtOffset(0)})`;
  const rs1DAgo  = `(${rsAtOffset(1)})`;
  const rs5DAgo  = `(${rsAtOffset(5)})`;
  const rs20DAgo = `(${rsAtOffset(Math.min(20, TRADING_DAYS - 1))})`;

  // ── Col E: 1D Δ ──
  const d1Cell = sheet.getRange(dashRow, COL.DELTA_1D);
  d1Cell.setFormula(`=IFERROR(ROUND(${rsNow}-${rs1DAgo},4),"")`);
  d1Cell.setNumberFormat('+0.0000;-0.0000;0.0000');
  d1Cell.setHorizontalAlignment('center');
  d1Cell.setVerticalAlignment('middle');
  d1Cell.setFontSize(9);

  // ── Col F: 5D Δ ──
  const d5Cell = sheet.getRange(dashRow, COL.DELTA_5D);
  d5Cell.setFormula(`=IFERROR(ROUND(${rsNow}-${rs5DAgo},4),"")`);
  d5Cell.setNumberFormat('+0.0000;-0.0000;0.0000');
  d5Cell.setHorizontalAlignment('center');
  d5Cell.setVerticalAlignment('middle');
  d5Cell.setFontSize(9);

  // ── Col G: 20D Δ ──
  const d20Cell = sheet.getRange(dashRow, COL.DELTA_20D);
  d20Cell.setFormula(`=IFERROR(ROUND(${rsNow}-${rs20DAgo},4),"")`);
  d20Cell.setNumberFormat('+0.0000;-0.0000;0.0000');
  d20Cell.setHorizontalAlignment('center');
  d20Cell.setVerticalAlignment('middle');
  d20Cell.setFontSize(9);

  // Bottom border for every row
  sheet.getRange(dashRow, 1, 1, 7)
    .setBorder(false, false, true, false, false, false, CLR.BORDER, SpreadsheetApp.BorderStyle.SOLID);
}

// ─── Alternating row backgrounds ─────────────────────────────────────────────

function applyAlternatingRows(sheet, lastRow) {
  let colorToggle = false;
  for (let r = 2; r <= lastRow; r++) {
    const tagCell = sheet.getRange(r, 8).getValue();
    if (tagCell === '__sep__') {
      // Clear tag cell content (we only used it as a marker)
      sheet.getRange(r, 8).clearContent();
      continue;  // separator rows keep their own colour, skip toggle
    }
    const bg = colorToggle ? CLR.ROW_EVEN : CLR.ROW_ODD;
    sheet.getRange(r, COL.TICKER, 1, 7).setBackground(bg);
    colorToggle = !colorToggle;
  }
}

// ─── Conditional formatting ───────────────────────────────────────────────────

function applyConditionalFormatting(sheet, lastRow) {
  const rules = [];
  const sheetName = sheet.getName();

  // We apply conditional formatting to the RS Now column and the three delta cols.
  // Sheets CF can reference other cells, so we drive colour from the cell value itself.

  // ── RS Now column ──
  const rsRange = sheet.getRange(2, COL.RS_NOW, lastRow - 1, 1);

  // Green: RS > 1.02
  rules.push(
    SpreadsheetApp.newConditionalFormatRule()
      .whenNumberGreaterThan(1.02)
      .setBackground(CLR.GREEN_LIGHT)
      .setFontColor(CLR.GREEN)
      .setRanges([rsRange])
      .build()
  );
  // Yellow: 0.98 ≤ RS ≤ 1.02
  rules.push(
    SpreadsheetApp.newConditionalFormatRule()
      .whenNumberBetween(0.98, 1.02)
      .setBackground(CLR.YELLOW_LIGHT)
      .setFontColor(CLR.YELLOW)
      .setRanges([rsRange])
      .build()
  );
  // Red: RS < 0.98
  rules.push(
    SpreadsheetApp.newConditionalFormatRule()
      .whenNumberLessThan(0.98)
      .setBackground(CLR.RED_LIGHT)
      .setFontColor(CLR.RED)
      .setRanges([rsRange])
      .build()
  );

  // ── Delta columns (1D, 5D, 20D) ──
  const deltaRange = sheet.getRange(2, COL.DELTA_1D, lastRow - 1, 3);  // cols E–G

  // Positive delta → green text
  rules.push(
    SpreadsheetApp.newConditionalFormatRule()
      .whenNumberGreaterThan(0)
      .setFontColor(CLR.GREEN)
      .setRanges([deltaRange])
      .build()
  );
  // Negative delta → red text
  rules.push(
    SpreadsheetApp.newConditionalFormatRule()
      .whenNumberLessThan(0)
      .setFontColor(CLR.RED)
      .setRanges([deltaRange])
      .build()
  );

  sheet.setConditionalFormatRules(rules);
}

// ─── Utility: refresh / reset ─────────────────────────────────────────────────

/**
 * rebuildDashboard() — call this to wipe and regenerate both sheets.
 * Useful if you add tickers or change TRADING_DAYS.
 */
function rebuildDashboard() {
  buildDashboard();
}

/**
 * refreshData() — force GOOGLEFINANCE to re-fetch by temporarily clearing
 * and re-entering the formulas in the Data sheet.
 * Run this if prices look stale.
 */
function refreshData() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const dataSheet = ss.getSheetByName('Data');
  if (!dataSheet) {
    SpreadsheetApp.getUi().alert('Data sheet not found. Run buildDashboard() first.');
    return;
  }

  ALL_TICKERS.forEach((t, i) => {
    const row = 6 + i;
    const cell = dataSheet.getRange(row, 5);
    const formula = cell.getFormula();
    cell.clearContent();
    SpreadsheetApp.flush();
    cell.setFormula(formula);
  });

  SpreadsheetApp.flush();
  SpreadsheetApp.getUi().alert('✅ Data refresh triggered. Allow 30–60 s for GOOGLEFINANCE to update.');
}

// ─── Menu ─────────────────────────────────────────────────────────────────────

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('📊 RS Dashboard')
    .addItem('Build / Rebuild Dashboard', 'buildDashboard')
    .addSeparator()
    .addItem('Refresh Data Formulas', 'refreshData')
    .toUi();
}
