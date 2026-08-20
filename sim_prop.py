import random
import numpy as np

def simulate_prop_firm(win_rate, r_value, target, max_dd, trades_per_day_range, num_simulations=10000):
    pass_count = 0
    fail_count = 0
    days_to_pass = []
    
    for _ in range(num_simulations):
        current_pnl = 0
        peak_pnl = 0
        days = 0
        trades = 0
        status = None # 'PASS' or 'FAIL'
        
        while status is None:
            days += 1
            num_trades = random.choice(trades_per_day_range)
            
            for _ in range(num_trades):
                trades += 1
                if random.random() < win_rate:
                    current_pnl += r_value
                else:
                    current_pnl -= r_value
                    
                if current_pnl > peak_pnl:
                    peak_pnl = current_pnl
                    
                # Trailing DD or absolute DD? Let's assume absolute DD from start or simple peak-based trailing DD.
                # Prop firms usually use trailing DD intraday or end-of-day. Let's use simple trailing DD.
                drawdown = peak_pnl - current_pnl
                
                if drawdown >= max_dd:
                    status = 'FAIL'
                    break
                    
                if current_pnl >= target:
                    status = 'PASS'
                    break
                    
        if status == 'PASS':
            pass_count += 1
            days_to_pass.append(days)
        else:
            fail_count += 1
            
    prob_pass = pass_count / num_simulations
    avg_days = np.mean(days_to_pass) if days_to_pass else 0
    p25_days = np.percentile(days_to_pass, 25) if days_to_pass else 0
    p75_days = np.percentile(days_to_pass, 75) if days_to_pass else 0
    
    return prob_pass, avg_days, p25_days, p75_days

print("65% Win Rate, Target $3000, Max Trailing DD $2500, 1-2 Trades/Day")
print(f"{'Risk (R)':<10} | {'Pass Prob':<12} | {'Avg Days':<10} | {'Days (P25-P75)':<15}")
print("-" * 55)

for r in [100, 200, 300, 400, 500, 800, 1000, 1500]:
    prob, avg_d, p25, p75 = simulate_prop_firm(0.65, r, 3000, 2500, [1, 1, 2], 10000)
    print(f"${r:<9} | {prob:.1%}       | {avg_d:<10.1f} | {p25:.0f} - {p75:.0f}")
