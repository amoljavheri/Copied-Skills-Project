import json

with open(r'C:/Users/amolj/.claude/projects/C--Claude-Projects-Copied-Skills-Project/12d75365-0921-435a-b21c-548965fd74f7/tool-results/mcp-61adfe15-70ba-4e95-8525-09f2b5b94fe1-get_options_chain-1773868202633.txt') as f:
    data = json.load(f)
chain = json.loads(data[0]['text'])

call_strikes = [140, 145, 150, 155, 160]
put_strikes  = [120, 125, 130, 135, 140]

calls = [o for o in chain['options']['option'] if o['option_type'] == 'call' and o['strike'] in call_strikes]
puts  = [o for o in chain['options']['option'] if o['option_type'] == 'put'  and o['strike'] in put_strikes]

print('=== MAR 20 CALLS (2 DTE) ===')
for c in sorted(calls, key=lambda x: x['strike']):
    g = c.get('greeks') or {}
    mid = round((c['bid'] + c['ask']) / 2, 2)
    iv  = round(g.get('mid_iv', 0) * 100, 1)
    delta = round(g.get('delta', 0), 3)
    print(f"${c['strike']:.0f} | bid ${c['bid']} ask ${c['ask']} mid ${mid} | delta {delta} | iv {iv}% | oi {c['open_interest']} vol {c['volume']}")

print()
print('=== MAR 20 PUTS (2 DTE) ===')
for p in sorted(puts, key=lambda x: x['strike']):
    g = p.get('greeks') or {}
    mid = round((p['bid'] + p['ask']) / 2, 2)
    iv  = round(g.get('mid_iv', 0) * 100, 1)
    delta = round(g.get('delta', 0), 3)
    print(f"${p['strike']:.0f} | bid ${p['bid']} ask ${p['ask']} mid ${mid} | delta {delta} | iv {iv}% | oi {p['open_interest']} vol {p['volume']}")
