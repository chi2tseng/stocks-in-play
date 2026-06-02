const fs = require('fs');
const data = JSON.parse(fs.readFileSync('D:/SIPs/dashboard/data/2026-05-18.json', 'utf8'));
const symbols = ['AUUD', 'SLE', 'PIII', 'GEMI', 'MICC', 'FIG', 'TRT', 'QUCY', 'MOBX', 'VUZI', 'AIIO', 'GAMB', 'AARD'];
symbols.forEach(sym => {
    const stock = data.stocks[sym];
    if (stock && stock.tv) {
        console.log(`\n--- ${sym} ---`);
        console.log(`EPS Surprise: ${stock.tv.eps_surprise_percent}% | Rev Surprise: ${stock.tv.rev_surprise_percent}%`);
        console.log(`EPS YoY: ${stock.tv.eps_yoy_growth}% | Rev YoY: ${stock.tv.rev_yoy_growth}%`);
        if (stock.tv.forward_pe) console.log(`Fwd PE: ${stock.tv.forward_pe}`);
    } else {
        console.log(`\n--- ${sym} (No TV data) ---`);
    }
});