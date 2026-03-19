import json, sys

file = sys.argv[1]
with open(file) as f:
    data = json.load(f)
chain = json.loads(data[0]['text'])

put_strikes  = [115,120,125,130,135,140,145]
call_strikes = [140,145,150,155,160,165,170]

puts  = [o for o in chain['options']['option'] if o['option_type']=='put'  and o['strike'] in put_strikes]
calls = [o for o in chain['options']['option'] if o['option_type']=='call' and o['strike'] in call_strikes]

print('=== PUTS ===')
for p in sorted(puts, key=lambda x: x['strike']):
    g = p.get('greeks') or {}
    mid = round((p['bid']+p['ask'])/2,2)
    iv  = round(g.get('mid_iv',0)*100,1)
    print(f"${p['strike']:.0f} | bid ${p['bid']} ask ${p['ask']} mid ${mid} | delta {round(g.get('delta',0),3)} | iv {iv}% | oi {p['open_interest']} vol {p['volume']}")

print()
print('=== CALLS ===')
for c in sorted(calls, key=lambda x: x['strike']):
    g = c.get('greeks') or {}
    mid = round((c['bid']+c['ask'])/2,2)
    iv  = round(g.get('mid_iv',0)*100,1)
    print(f"${c['strike']:.0f} | bid ${c['bid']} ask ${c['ask']} mid ${mid} | delta {round(g.get('delta',0),3)} | iv {iv}% | oi {c['open_interest']} vol {c['volume']}")
