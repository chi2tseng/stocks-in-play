const fs = require('fs');
const data = JSON.parse(fs.readFileSync('D:/SIPs/dashboard/data/2026-05-18.json', 'utf8'));
const stocks = data.stocks;
console.log('Total:', Object.keys(stocks).length);
Object.entries(stocks).sort((a,b) => (b[1].chgPct||0) - (a[1].chgPct||0)).forEach(([sym, info]) => {
  const cat = typeof info.catalyst === 'string' ? info.catalyst.substring(0, 80).replace(/\n/g, ' ') : 'N/A';
  console.log(`${sym.padEnd(5)} | Gap ${String(info.chgPct).padStart(6)}% | Vol ${String(info.volume).padStart(10)} | ${cat}`);
});
